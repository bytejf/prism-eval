"""写下一局的「运行档案」—— 这个数是什么版本、什么配置、花多少跑出来的。

**为什么需要它**：`summary_<reviewer>.json` 只记 status/exit_code，而每份报告里的
`prism_version` 是**包版本号**（一直是 `0.1.0`）—— 于是**两次不同提示词的运行在
产物里长得一模一样**。半年后回看「F1 0.237」那一行，得能答出「哪个 commit、
什么思考档、什么预算」，否则那个数不可复现，也就不能叫证据。

跑一次要花钱，所以这份档案分两段写：**开跑前**落版本 + 配置 + 数据集指纹
（那时它们才是确定的），**跑完**再补结果汇总。两段合并进同一个文件。

用法：
    python analysis/run_manifest.py <run_dir> --dataset <jsonl> --start   # 开跑前
    python analysis/run_manifest.py <run_dir>                             # 跑完后
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Prism 的源码仓库 —— 档案要记的是**它的 git SHA**，不是包版本号
DEFAULT_PRISM_REPO = Path.home() / "Projects/python/prism"


def _now() -> str:
    """本地时间的 ISO 字符串（人读的档案，不用 UTC）。"""
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _run(repo: Path, *args: str) -> str:
    """在仓库里跑一条 git 命令，失败返回空串（档案不该因为 git 抽风写不出来）。

    Args:
        repo: 仓库路径
        args: git 子命令与参数

    Returns:
        stdout（已 strip），失败时为空串
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _sha256(path: Path) -> str:
    """文件的 sha256（数据集指纹 —— 换了数据但同名时靠它区分）。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataset(path: Path) -> dict[str, Any]:
    """数据集的指纹与规模。

    Args:
        path: jsonl 路径

    Returns:
        路径 / 条数 / sha256
    """
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"path": str(path), "samples": len(lines), "sha256": _sha256(path)}


def _prism_identity(repo: Path) -> dict[str, Any]:
    """Prism 的身份：git SHA + 有没有未提交改动 + 实际调的是哪个可执行文件。

    `dirty` 很重要 —— 提示词改动如果还没提交，SHA 就代表不了跑的是什么。

    Args:
        repo: Prism 源码仓库

    Returns:
        身份字典
    """
    porcelain = _run(repo, "status", "--porcelain")
    exe = shutil.which("prism") or ""
    return {
        "repo": str(repo),
        "commit": _run(repo, "rev-parse", "HEAD"),
        "commit_subject": _run(repo, "log", "-1", "--format=%s"),
        "commit_date": _run(repo, "log", "-1", "--format=%cI"),
        "dirty": bool(porcelain),
        "dirty_files": porcelain.splitlines() if porcelain else [],
        "executable": exe,
        "executable_target": str(Path(exe).resolve()) if exe else "",
        "package_version": _run(repo, "describe", "--tags", "--always"),
    }


def _config(repo: Path) -> dict[str, Any]:
    """跑这一局时生效的配置。

    **整份 `default.toml` 抄进来**，不做字段挑选：它就是「旋钮有哪些」的契约，
    挑字段等于在这里再维护一份会漂的清单。

    Args:
        repo: Prism 源码仓库

    Returns:
        配置字典
    """
    path = repo / "src/prism/config/default.toml"
    if not path.exists():
        return {"source": str(path), "text": None}
    return {"source": str(path), "sha256": _sha256(path), "text": path.read_text(encoding="utf-8")}


def _summarize(run_dir: Path) -> dict[str, Any]:
    """把各样本的 `.prism.json` 汇总成这一局的总账。

    Args:
        run_dir: `results/<bench>/prism/<run_id>`

    Returns:
        条数 / 用量 / 缺口 / 失败面
    """
    reports = sorted(p for p in run_dir.glob("*.prism.json") if not p.name.startswith("summary"))
    totals: dict[str, Any] = {
        "samples_reported": len(reports),
        "comments": 0,
        "calls": 0,
        "input_tokens": 0,
        "cache_hit_tokens": 0,
        "cache_miss_tokens": 0,
        "output_tokens": 0,
        "cost_yuan": 0.0,
        "pending_hunks": 0,
        "duration_seconds": 0.0,
        "missing_usage_calls": 0,
        "prism_versions": [],
    }
    # `prism_version` 是包版本号（一直是 0.1.0），单靠它区分不了两次运行 ——
    # 收进来只是为了让「产物与档案对得上」，真正的身份在 `prism.commit`
    versions: set[str] = set()
    for path in reports:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        versions.add(str(data.get("prism_version", "?")))
        usage = data.get("usage") or {}
        stats = data.get("stats") or {}
        for key in ("calls", "input_tokens", "cache_hit_tokens", "cache_miss_tokens", "output_tokens"):
            totals[key] += int(usage.get(key, 0) or 0)
        totals["missing_usage_calls"] += int(usage.get("missing_usage_calls", 0) or 0)
        totals["cost_yuan"] = round(totals["cost_yuan"] + float(usage.get("cost_yuan", 0.0) or 0.0), 4)
        totals["comments"] += int(stats.get("comments_count", 0) or 0)
        totals["pending_hunks"] += int(stats.get("pending_hunks", 0) or 0)
        totals["duration_seconds"] = round(
            totals["duration_seconds"] + float(stats.get("duration_seconds", 0.0) or 0.0), 1
        )
    totals["prism_versions"] = sorted(versions)
    return totals


def main() -> int:
    """写 / 更新一局的运行档案。

    Returns:
        退出码
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, help="results/<bench>/<reviewer>/<run_id>")
    parser.add_argument("--dataset", type=Path, help="数据集 jsonl（--start 时必填）")
    parser.add_argument("--start", action="store_true", help="开跑前：记版本 + 配置 + 数据集指纹")
    parser.add_argument("--prism-repo", type=Path, default=DEFAULT_PRISM_REPO, help="Prism 源码仓库")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的档案")
    args = parser.parse_args()

    manifest_path = args.run_dir / "run_manifest.json"
    if args.start and manifest_path.exists() and not args.force:
        # 换个名字重跑，或者在跑之前就把旧档案挪走 —— 别让两局混进同一份档案
        print(f"档案已存在：{manifest_path}\n换一个 --run-id，或者加 --force", file=sys.stderr)
        return 1
    if args.start and args.dataset is None:
        print("--start 需要 --dataset", file=sys.stderr)
        return 1

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if args.start:
        args.run_dir.mkdir(parents=True, exist_ok=True)
        manifest.update(
            {
                "run_id": args.run_dir.name,
                "started_at": _now(),
                "dataset": _dataset(args.dataset),
                "prism": _prism_identity(args.prism_repo),
                "config": _config(args.prism_repo),
            }
        )
        print(f"开跑前：{manifest['prism']['commit'][:8]}（dirty={manifest['prism']['dirty']}）")
    else:
        manifest["finished_at"] = _now()
        manifest["result"] = _summarize(args.run_dir)
        # **配置可能在跑的过程中被改过**（实测：闸的标定值中途上调，于是同一批里
        # 20 个样本跑在旧闸下、2 个跑在新闸下）。开跑前那份快照代表不了全程，
        # 而看档案的人是拿它当「这一批是什么配置跑的」用的 —— 不对比就是记录失真
        current = _config(args.prism_repo)
        if manifest.get("config", {}).get("sha256") != current.get("sha256"):
            manifest["config_changed_during_run"] = current
        result = manifest["result"]
        print(
            f"跑完：{result['samples_reported']} 个样本 / {result['comments']} 条评论 / "
            f"{result['input_tokens']:,} 输入 + {result['output_tokens']:,} 输出 / "
            f"{result['cost_yuan']:.3f} 元"
        )

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"档案：{manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
