"""把一次 prism 评测的结果汇总成一张表（逐 PR + 总计）。

    python prism_report.py results/<benchmark>/prism/<run_id>

数据来源三处，各管一段：

- `results/…/<样本>.json`     harness 结果（评论、耗时、我们自己的 JSON 报告）
- `metrics/…/metrics_*.json`  裁判的逐条判定（哪条参考被行号/语义命中）
- `results/…/<样本>.stderr.log`  审查全量日志（退出原因、轮次、收尾闸、静态分析耗时）

**为什么要它**：harness 只打总指标，而「哪几条 PR 全军覆没、卡在哪一环」要看逐 PR 的
画像 —— 产出条数、退出原因、未审 hunk、是模型不报还是被闸停的。
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# 上游 harness 的 `evaluation/` 目录 —— `results/` `metrics/` 都在它下面。
# 一次运行的产物按 `<根>/results/<bench>/<reviewer>/<run_id>` 分层，
# `attach_matches` 靠这个结构反推 metrics 目录
ROOT = Path(
    os.getenv(
        "PRISM_EVAL_HARNESS",
        Path(__file__).resolve().parent.parent / "aacr-bench" / "evaluation",
    )
).resolve()


def load_run(run_dir: Path) -> list[dict[str, Any]]:
    """读一局的全部样本。

    Args:
        run_dir: `results/<benchmark>/<reviewer>/<run_id>`

    Returns:
        逐样本的记录
    """
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name.startswith("summary") or path.name.endswith(".prism.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "review" not in data:
            continue
        rows.append(_one_sample(path, data))
    return rows


def _one_sample(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """把一份样本结果压成汇总需要的那几个字段。

    Args:
        path: 结果文件路径
        data: harness 结果

    Returns:
        记录字典
    """
    raw = data.get("prism") or {}
    stats = raw.get("stats", {})
    usage = raw.get("usage", {})
    log = path.with_suffix("").with_suffix(".stderr.log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""

    exit_match = re.search(r"结束审查 \S+：exit_reason=(\w+)，轮次 (\d+)", text)
    static_match = re.search(r"静态分析完成：([\d.]+) 秒", text)
    return {
        "instance": data.get("instance_id", path.stem),
        "repo": data.get("repo", ""),
        "generated": len(data["review"].get("comments", []) or []),
        "exit_reason": exit_match.group(1) if exit_match else "?",
        "rounds": int(exit_match.group(2)) if exit_match else 0,
        "pending": stats.get("pending_hunks", 0),
        "comments_kept": stats.get("comments_count", 0),
        "cost": usage.get("cost_yuan", 0.0),
        "tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        "reasoning_share": _reasoning_share(path),
        "duration": data.get("duration_seconds", 0.0),
        "static_seconds": float(static_match.group(1)) if static_match else 0.0,
        "gated": "停用探索工具" in text,
        "refs": 0,
        "hit_semantic": 0,
        "hit_line": 0,
        # 只统计落在 `.go` 上的参考 —— 我们只审 Go，其余结构上不可达，
        # 所以要另有一套分母（两个口径都报，见 doc 23 附录 C）
        "refs_go": 0,
        "hit_semantic_go": 0,
        "hit_line_go": 0,
    }


def _reasoning_share(result_path: Path) -> float:
    """思考 token 占输出的比例。

    **报告里没有这个数**（我们的 JSON 只记三档用量），得从 OTel trace 的
    `llm_call` span 上读 `gen_ai.usage.reasoning.output_tokens` —— 它是最贵那一档
    里的大头（实测 low 档下占输出 45%~58%），回答「思考等级值不值」要看它。
    读不到（没开 trace）时返回 0。

    Args:
        result_path: `<样本>.json` 路径（trace 是它的同名兄弟）

    Returns:
        0~1 的比例
    """
    trace = result_path.with_name(f"{result_path.stem}.trace.jsonl")
    if not trace.exists():
        return 0.0
    out = reason = 0
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        for resource in json.loads(line).get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    if span.get("name") != "llm_call":
                        continue
                    attrs = {a["key"]: list(a["value"].values())[0] for a in span.get("attributes", [])}
                    out += int(attrs.get("gen_ai.usage.output_tokens", 0) or 0)
                    reason += int(attrs.get("gen_ai.usage.reasoning.output_tokens", 0) or 0)
    return round(reason / out, 3) if out else 0.0


def attach_matches(rows: list[dict[str, Any]], run_dir: Path) -> None:
    """把裁判的逐条判定贴到对应样本上（原地改）。

    Args:
        rows: 样本记录
        run_dir: 结果目录（用来反推 metrics 目录）
    """
    metrics_dir = ROOT / "metrics" / run_dir.parts[-3] / run_dir.parts[-2] / run_dir.name
    files = sorted(metrics_dir.glob("metrics_*.json"))
    if not files:
        print(f"（没找到指标文件：{metrics_dir} —— 只报产出与退出原因）")
        return
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    by_id = {item["instance_id"]: item for item in payload.get("eval_res", [])}
    for row in rows:
        item = by_id.get(row["instance"], {})
        comments = item.get("comments", []) or []
        row["refs"] = len(comments)
        row["hit_semantic"] = sum(1 for c in comments if c.get("semantic_match"))
        row["hit_line"] = sum(1 for c in comments if c.get("line_match"))
        go = [c for c in comments if str(c.get("path", "")).endswith(".go")]
        row["refs_go"] = len(go)
        row["hit_semantic_go"] = sum(1 for c in go if c.get("semantic_match"))
        row["hit_line_go"] = sum(1 for c in go if c.get("line_match"))


def main() -> int:
    """打印汇总表。

    Returns:
        退出码（总为 0）
    """
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    run_dir = Path(sys.argv[1])
    rows = load_run(run_dir)
    attach_matches(rows, run_dir)

    print(f"\n=== 逐 PR（{len(rows)} 条样本，{run_dir.name}）===")
    print(
        f"{'PR':<40}{'参考':>5}{'产出':>5}{'语义':>5}{'行号':>5}{'退出':>14}"
        f"{'轮次':>5}{'未审':>5}{'静态':>6}{'闸':>4}{'思考%':>6}{'花费':>8}"
    )
    for row in sorted(rows, key=lambda r: (r["hit_semantic"], r["generated"])):
        print(
            f"{row['instance']:<40}{row['refs']:>5}{row['generated']:>5}"
            f"{row['hit_semantic']:>5}{row['hit_line']:>5}{row['exit_reason']:>14}"
            f"{row['rounds']:>5}{row['pending']:>5}{row['static_seconds']:>5.0f}s"
            f"{'是' if row['gated'] else '—':>4}{row['reasoning_share'] * 100:>5.0f}%"
            f"{row['cost']:>8.3f}"
        )

    total = Counter()
    for row in rows:
        total["refs"] += row["refs"]
        total["generated"] += row["generated"]
        total["sem"] += row["hit_semantic"]
        total["line"] += row["hit_line"]
        total["pending"] += row["pending"]
        total["refs_go"] += row["refs_go"]
        total["sem_go"] += row["hit_semantic_go"]
        total["line_go"] += row["hit_line_go"]
        total[f"exit:{row['exit_reason']}"] += 1
    refs = max(total["refs"], 1)
    gen = max(total["generated"], 1)
    print("\n=== 总计 ===")
    print(f"  参考 {total['refs']} 条 | 产出 {total['generated']} 条 | "
          f"语义命中 {total['sem']} | 行号命中 {total['line']}")
    print(
        f"  语义 P={total['sem'] / gen:.3f} R={total['sem'] / refs:.3f} "
        f"F1={_f1(total['sem'] / gen, total['sem'] / refs):.3f} | "
        f"行号 P={total['line'] / gen:.3f} R={total['line'] / refs:.3f} "
        f"F1={_f1(total['line'] / gen, total['line'] / refs):.3f}"
    )
    # **两个口径都报**：官方分母是全部参考，但非 `.go` 的那些我们结构上审不到
    # （只审 .go），所以再报一套 Go-only 分母 —— 后者才是「能力范围内」的召回
    refs_go = max(total["refs_go"], 1)
    print(
        f"  仅 Go 口径（分母 {total['refs_go']}，另有 {refs - total['refs_go']} 条非 .go 不可达）："
        f"语义 P={total['sem_go'] / gen:.3f} R={total['sem_go'] / refs_go:.3f} | "
        f"行号 P={total['line_go'] / gen:.3f} R={total['line_go'] / refs_go:.3f}"
    )
    print(f"  未审 hunk 合计 {total['pending']} | 花费 {sum(r['cost'] for r in rows):.2f} 元 | "
          f"耗时合计 {sum(r['duration'] for r in rows) / 60:.1f} 分钟 | "
          f"静态分析合计 {sum(r['static_seconds'] for r in rows):.0f} 秒")
    print(f"  退出原因：{ {k.split(':')[1]: v for k, v in total.items() if k.startswith('exit:')} }")
    print(f"  收尾闸触发 {sum(1 for r in rows if r['gated'])}/{len(rows)} 条")
    shares = [r["reasoning_share"] for r in rows if r["reasoning_share"]]
    if shares:
        print(f"  思考 token 占输出：{' / '.join(f'{s * 100:.0f}%' for s in shares)}"
              f"（均值 {sum(shares) / len(shares) * 100:.0f}%）")
    print(f"  零产出的 PR：{[r['instance'] for r in rows if r['generated'] == 0] or '无'}")
    return 0


def _f1(precision: float, recall: float) -> float:
    """调和均值（分母为 0 时返回 0）。

    Args:
        precision: 精确率
        recall: 召回率

    Returns:
        F1
    """
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


if __name__ == "__main__":
    sys.exit(main())
