"""prism 评审器。

调 `prism review --path <repo> --base <base> --head <head> --json-out <file>`
评审 base..head 的全量 diff，并把结果**写成 harness 的统一形状**：

    {
      "instance_id": …,
      "duration_seconds": …,
      "review": {
        "summary": {"input_tokens": …, "output_tokens": …},
        "comments": [{"content": …, "path": …, "start_line": …, "end_line": …}]
      },
      "prism": {…原始 JSON 全量…}          # 供后续分析，评测不用它
    }

**为什么是这个形状**：`_extract_usage_from_result` 的默认分支读
`review.summary.{input,output}_tokens` —— 写成一模一样，用量与耗时就不用改评测代码。

**但评论不走默认分支**：`build_target_comments_from_ocr` 把每条评论的 `side`
硬编码成 `"right"`（那三个评审器都只报右侧），而 **prism 真的会报左侧**（删除行）。
所以 `evaluate.py` 里注册了一个 prism 专属的构造器，直接从 `prism.comments`
读原始 JSON（那里有准确的 `side` 与 `locate_level`）。

环境变量（全部可选）：

    PRISM_BIN          prism 可执行文件（默认走 PATH 上的 prism）
    PRISM_TRACE_DIR    把 OTel trace 写到这个目录（不设则不开追踪）
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import config
from repo_utils import clean_worktree, log, prepare_repo, run_command
from schema import ReviewInstance

# 结果里 `side` 的取值：harness 用**小写**的 left/right（数据集口径），
# 而 prism 内部照抄 GitHub 的 PR 模型用大写（RIGHT/LEFT）—— 在这一层转
_SIDE_MAP = {"RIGHT": "right", "LEFT": "left"}

# prism 自己的 JSON 里，没有行号的评论 `start_line` 是 0；harness 认 `None`
# （判据是 `all(x is not None …)`，0 会被当成「第 0 行」参与行号匹配）
_NO_LINE = 0


def ensure_prism_installed(prism_command: str = "prism") -> None:
    """确认 prism 可用（版本号打出来，便于把结果与版本对上）。

    Args:
        prism_command: prism 可执行文件

    Raises:
        SystemExit: 找不到可执行文件
    """
    result = run_command([prism_command, "--version"])
    if result.returncode != 0:
        raise SystemExit(
            f"prism CLI not found at '{prism_command}'. Install it with:\n"
            "    uv tool install git+https://github.com/bytejf/prism\n"
            "或用 PRISM_COMMAND 指定一个别的可执行文件路径"
        )
    first_line = result.stdout.strip().splitlines()[0] if result.stdout else "ok"
    log(f"prism available ({prism_command}): {first_line}")


def review_instance(
    instance: ReviewInstance,
    repo_dir: Path,
    results_dir: Path,
    timeout_minutes: int = 30,
    preview: bool = False,
    prism_command: str = "prism",
) -> Dict[str, Any]:
    """对单条样本执行 prism 评审，返回状态摘要。

    Args:
        instance: 待评审样本
        repo_dir: 仓库克隆缓存目录
        results_dir: 结果输出目录
        timeout_minutes: 单样本超时（分钟）
        preview: 只准备仓库、不真调模型（用于验证流程）
        prism_command: prism 可执行文件

    Returns:
        状态摘要（instance_id / status / exit_code / result_path）
    """
    log(f"=== [prism] Processing {instance.instance_id} ===")

    repo_path = prepare_repo(
        repo_dir=repo_dir,
        clone_url=instance.resolved_clone_url,
        repo_full_name=instance.repo,
        base_commit=instance.base_commit,
        head_commit=instance.head_commit,
    )
    if preview:
        clean_worktree(repo_path)
        return {"instance_id": instance.instance_id, "status": "preview", "exit_code": 0}

    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{instance.safe_id}.prism.json"
    # trace 写在**本次 run 的目录**里（results/<benchmark>/<reviewer>/<run_id>/），
    # 文件名即样本 id —— 设计 §4.1 想要的是「一个测试用例一个文件」，但那个文件名
    # 不带 run id：同一个样本跑第二次（重试、对照实验）会**追加进同一个文件**，
    # 两条 trace 的 span 混在一起（实测踩到：一个文件里 3 个根 span）
    trace_path = results_dir / f"{instance.safe_id}.trace.jsonl"
    env = _child_env(instance, trace_path)
    # prism 自己会读 base/head 算 merge-base —— 与数据集给的 commit 一一对应
    command = [
        prism_command,
        "review",
        "--path",
        str(repo_path),
        "--base",
        instance.base_commit,
        "--head",
        instance.head_commit,
        "--json-out",
        str(json_path),
        # 这两个只有驱动知道，挂到根 span 上（trace 里才认得出这是哪个 PR）
        # 这两个只有驱动知道，挂到根 span 上（trace 里才认得出这是哪条样本）。
        # **别把 instance_id 叫成 pr_url** —— 它不是 URL，而数据集里也没带 PR URL
        "--trace-attr",
        f"instance_id={instance.instance_id}",
        "--trace-attr",
        f"repo={instance.repo}",
    ]

    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.monotonic()
    process = _run_prism(command, repo_path, timeout_minutes * 60, env)
    duration_seconds = time.monotonic() - start_time

    out_path = _save_result(
        results_dir=results_dir,
        instance=instance,
        process=process,
        json_path=json_path,
        started_at=started_at,
        duration_seconds=duration_seconds,
    )
    # 完整 stderr 另存一份：JSON 里只留尾部（够看报错），但**排查要全量** ——
    # 第一版只存了尾部 4000 字符，结果「模型这 8 轮到底在干什么」就看不出来了
    stderr_path = results_dir / f"{instance.safe_id}.stderr.log"
    stderr_path.write_text(process.stderr or "", encoding="utf-8")
    # 丢掉 prism 在仓库里留下的临时文件（静态分析用的是临时 worktree，本来就会自己清）
    clean_worktree(repo_path)

    status = "ok" if process.returncode == 0 else "failed"
    log(f"--- [prism] {instance.instance_id} {status} (exit={process.returncode}) -> {out_path}")
    return {
        "instance_id": instance.instance_id,
        "status": status,
        "exit_code": process.returncode,
        "result_path": str(out_path),
        "stderr_path": str(stderr_path),
        "trace_path": str(trace_path),
    }


def _run_prism(
    command: List[str],
    repo_path: Path,
    timeout_seconds: int,
    env: Dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """跑 `prism review`，**超时算失败样本而不是崩掉评测**。

    直接 `subprocess.run` 而不是 `repo_utils.run_command`：后者不收 `env`
    （我们得往里塞 PRISM_TRACE_FILE），也不处理超时。超时转成一个 returncode=-1
    的 CompletedProcess —— 一个样本超时不该中断整批。

    Args:
        command: 命令行
        repo_path: 工作目录（被审查仓库）
        timeout_seconds: 超时（秒）
        env: 子进程环境变量

    Returns:
        子进程结果
    """
    log(f"$ {' '.join(command)}  (cwd={repo_path})")
    try:
        return subprocess.run(
            command,
            cwd=str(repo_path),
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as timeout_error:
        log(f"TIMEOUT: prism 超过 {timeout_seconds}s —— 记为失败样本")
        return subprocess.CompletedProcess(
            args=command,
            returncode=-1,
            stdout=timeout_error.stdout or "",
            stderr=f"Process timed out after {timeout_seconds} seconds",
        )


def _child_env(instance: ReviewInstance, trace_path: Path) -> Dict[str, str]:
    """给子进程的环境变量。

    显式传 `env` 会替换掉整个环境（`subprocess.run` 的语义），所以这里必须从
    `os.environ` 拷一份 —— 尤其是 `DEEPSEEK_API_KEY`：它只从环境变量读，漏掉的话
    prism 会以「密钥缺失」失败，而报错信息看着像配置问题。

    `PRISM_TRACE_FILE` 指到本次 run 目录下、以样本 id 命名的文件：**不设的话
    prism 就完全不初始化追踪**（零开销），所以这里设了就等于「评测永远留 trace」。

    Args:
        instance: 待评审样本
        trace_path: trace 目标文件

    Returns:
        环境变量字典
    """
    env = dict(os.environ)
    env["PRISM_TRACE_FILE"] = str(trace_path)
    return env


def _save_result(
    results_dir: Path,
    instance: ReviewInstance,
    process: subprocess.CompletedProcess[str],
    json_path: Path,
    started_at: str,
    duration_seconds: float,
) -> Path:
    """把结果写成 harness 的统一形状。

    Args:
        results_dir: 结果目录
        instance: 待评审样本
        process: prism 子进程的结果
        json_path: prism 写出的 JSON 路径
        started_at: 开始时刻（ISO 格式）
        duration_seconds: 耗时

    Returns:
        写出的结果文件路径
    """
    out_path = config.result_path(results_dir, instance.instance_id)
    prism_report = _load_json(json_path)
    review = _to_review(prism_report) if prism_report else {}

    payload: Dict[str, Any] = {
        "instance_id": instance.instance_id,
        "repo": instance.repo,
        "base_commit": instance.base_commit,
        "head_commit": instance.head_commit,
        "started_at": started_at,
        "duration_seconds": duration_seconds,
        "prism_exit_code": process.returncode,
        # 评测侧只读 review.summary 与 review.comments（与 ocr 同一形状）
        "review": review,
        # 我们自己的完整 JSON 原样带上：评测不用，但分析（花费、闸门分布、
        # 定位层级）全靠它，重跑一次要花钱
        "prism": prism_report,
        # 尾部够看报错；全量在 <safe_id>.stderr.log
        "stderr_tail": process.stderr[-4000:] if process.stderr else "",
    }
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return out_path


def _load_json(path: Path) -> Dict[str, Any] | None:
    """读 prism 的 JSON 报告；读不出来返回 None。

    Args:
        path: 报告路径

    Returns:
        报告字典；文件不存在或不是合法 JSON 时返回 None
    """
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        log(f"WARNING: prism 的 JSON 报告读不出来（{path.name}）：{error}")
        return None
    return data if isinstance(data, dict) else None


def _to_review(report: Dict[str, Any]) -> Dict[str, Any]:
    """prism 报告 → harness 的 review 形状。

    Args:
        report: prism 的 JSON 报告

    Returns:
        `{"summary": {...}, "comments": [...]}`
    """
    usage = report.get("usage") or {}
    comments: List[Dict[str, Any]] = []
    for item in report.get("comments") or []:
        note = str(item.get("content") or "").strip()
        if not note:
            continue
        comments.append(
            {
                "content": note,
                "path": item.get("path") or "",
                "start_line": _line(item.get("start_line")),
                "end_line": _line(item.get("end_line")),
            }
        )
    return {
        "summary": {
            # 口径对齐：harness 的 else 分支把 input_tokens 当「完整输入」用，
            # 所以这里给**总输入**（含缓存命中），不是未命中的那一部分
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "comments": comments,
    }


def _line(value: Any) -> int | None:
    """行号：prism 用 0 表示「没定位到」，harness 认 None。

    0 会被 harness 的行号匹配当成「第 0 行」而不是「没有行号」
    （判据是 `all(x is not None …)`），语义完全不同。

    Args:
        value: prism 给的行号

    Returns:
        行号；未定位时 None
    """
    if isinstance(value, int) and value > _NO_LINE:
        return value
    return None
