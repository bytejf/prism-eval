"""把「没命中的参考评论」导成一份可逐条读、可打标签的清单。

    python analysis/ref_audit.py
    # 换一局：REF_AUDIT_BENCH=<批次> REF_AUDIT_RUN=<run_id> python analysis/ref_audit.py
    # 默认取那个批次**最近的一局**；harness 位置用 PRISM_EVAL_HARNESS 覆盖

输出：`<harness>/missed_references.md`

**为什么要有这份清单**：跑了 22 个 PR 之后手上只有一个聚合数字（召回 0.132），
而「该改什么」取决于漏掉的那些**分别属于哪一类**。所以每条参考都要回答一个问题：
**那个位置，我们到底有没有机会看到？** 判据是确定的 —— 参考行落在我们审过的
某个 hunk 的区间里没有。

四类（`semantic_match` 为真的不进清单）：

- **(c) 说了，但不是一个角度** —— 行号命中了、语义没命中。裁判手里有我们的原话
- **(a) 看到了，没看出来** —— 位置落在我们审过的 hunk 里，那条线附近一条评论都没有
- **(b) 根本没看到** —— 位置不在我们审过的任何 hunk 里（文件被过滤、hunk 被丢弃、
  或那几行没进 diff）
- **(d) 结构上不可达** —— 非 `.go` 或在测试文件上，V1 只审 `.go` 且排除测试

两份数据来源：`metrics/` 给逐条判定与参考原文，`results/` 的 `.prism.json` 给
我们自己报的评论。"在不在 hunk 里"由 **prism 自己的流水线**现算（diff → 过滤 →
映射 → 分组，零 token）—— 不另写一套判据，否则这份清单会和真实行为漂开。
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

# 「某个位置进没进过审查范围」要借 **prism 自己的流水线**现算 —— 复刻一套
# 判据一定会漂，而这份清单的全部价值就在于它与真实行为一致
try:
    from prism.core.ast.mapper import map_hunks_to_symbols
    from prism.core.diff.loader import load_diffs
    from prism.core.filter.rules import filter_files
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "需要先装上 prism —— 例如：\n"
        "    pip install git+https://github.com/bytejf/prism\n"
        "或从源码装：pip install -e <prism 源码目录>"
    ) from exc

# 上游 harness 的 `evaluation/` 目录 —— `results/` `metrics/` `repo/` `data/`
# 都在它下面（见 setup.sh）
ROOT = Path(
    os.getenv(
        "PRISM_EVAL_HARNESS",
        Path(__file__).resolve().parent.parent / "aacr-bench" / "evaluation",
    )
).resolve()

BENCH = os.getenv("REF_AUDIT_BENCH", "prism-go-all")


def _latest_run(bench: str) -> str:
    """取这个批次最近的一局。

    不给默认 run id —— 那个值是机器相关的，写进代码只会在别人那里指到不存在的
    目录。

    Args:
        bench: 批次名

    Returns:
        run 目录名

    Raises:
        SystemExit: 那个批次一局都还没跑过
    """
    base = ROOT / "results" / bench / "prism"
    runs = sorted(path.name for path in base.iterdir() if path.is_dir()) if base.is_dir() else []
    if not runs:
        raise SystemExit(f"{base} 下没有任何一局 —— 先用 pipeline 跑一局，或设 REF_AUDIT_RUN")
    return runs[-1]


RUN = os.getenv("REF_AUDIT_RUN") or _latest_run(BENCH)
REPO_CACHE = ROOT / "repo"
DATASET = ROOT / "data" / os.getenv("REF_AUDIT_DATASET", "prism-go-all.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    """读标准格式的数据集。

    Args:
        path: jsonl 路径

    Returns:
        记录列表
    """
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def covered_lines(inst: dict) -> dict[str, list[tuple[int, int, str]]]:
    """跑前半段流水线，得到「每个文件里哪些行属于某个被审过的 hunk」。

    零 token。**复用的是生产代码**（`filter_files` / `map_hunks_to_symbols`），
    所以这份清单里的 (a)/(b) 判定与真实审查行为同源。

    Args:
        inst: 数据集记录

    Returns:
        文件路径 → [(起始行, 结束行, hunk_id)]，新侧与旧侧各一条记录
    """
    repo = REPO_CACHE / str(inst["repo"]).replace("/", "__")
    base, head = inst["base_commit"], inst["head_commit"]
    reviewable = filter_files(load_diffs(repo, base, head)).reviewable
    mapped = map_hunks_to_symbols(repo, base, head, reviewable)

    spans: dict[str, list[tuple[int, int, str]]] = {}
    for item in mapped:
        part, path = item.part, item.file_path
        if part.new_lines > 0:
            spans.setdefault(path, []).append(
                (part.new_start, part.new_start + part.new_lines - 1, item.hunk_id)
            )
        if part.old_lines > 0:
            spans.setdefault(path, []).append(
                (part.old_start, part.old_start + part.old_lines - 1, f"{item.hunk_id}(旧侧)")
            )
    return spans


def located(spans: dict[str, list[tuple[int, int, str]]], path: str, lo: int, hi: int) -> str:
    """判这条参考落在哪个 hunk 里。

    Args:
        spans: `covered_lines` 的产出
        path: 参考的文件
        lo: 起始行
        hi: 结束行

    Returns:
        hunk 编号；不在任何 hunk 区间里时返回空串
    """
    for start, end, hunk_id in spans.get(path, []):
        if start <= lo <= end or start <= hi <= end:
            return hunk_id
    return ""


def our_comments(instance_id: str) -> list[dict]:
    """读我们自己报的评论。

    Args:
        instance_id: 样本编号

    Returns:
        评论列表；这一局没跑或没产出时返回空列表
    """
    path = ROOT / "results" / BENCH / "prism" / RUN / f"{instance_id}.prism.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("comments") or []


def main() -> int:
    """生成清单。

    Returns:
        退出码（总为 0）
    """
    metrics = sorted((ROOT / "metrics" / BENCH / "prism" / RUN).glob("metrics_*.json"))
    if not metrics:
        print(f"找不到指标文件：{ROOT / 'metrics' / BENCH / 'prism' / RUN}")
        return 0
    judged = {item["instance_id"]: item for item in json.loads(
        metrics[-1].read_text(encoding="utf-8"))["eval_res"]}

    instances = load_jsonl(DATASET)
    buckets: Counter[str] = Counter()
    sections: list[str] = []
    index: list[str] = []

    for inst in instances:
        item = judged.get(inst["instance_id"])
        if item is None:
            continue
        spans = covered_lines(inst)
        mine = our_comments(inst["instance_id"])
        by_file: dict[str, list[dict]] = {}
        for comment in mine:
            by_file.setdefault(comment.get("path", ""), []).append(comment)

        entries: list[tuple[str, str, dict, str]] = []
        for ref in item.get("comments") or []:
            if ref.get("semantic_match"):
                continue
            path = str(ref.get("path") or "")
            lo = int(ref.get("from_line") or 0)
            hi = int(ref.get("to_line") or lo)
            if not path.endswith(".go") or "_test.go" in path:
                kind = "d"
                where = "非 .go 或在测试文件上 —— V1 结构上不可达"
            else:
                hunk_id = located(spans, path, lo, hi)
                if ref.get("line_match"):
                    kind, where = "c", "行号命中了，但裁判判为「不是同一件事」"
                elif hunk_id:
                    kind, where = "a", f"落在我们审过的 {hunk_id} 里"
                else:
                    kind, where = "b", "不在我们审过的任何 hunk 里"
            buckets[kind] += 1
            entries.append((kind, where, ref, path))

        if not entries:
            continue
        sections.append(_render_pr(inst, entries, by_file))
        index.extend(
            f"- `{inst['instance_id']}` `{path}:{ref.get('from_line')}`"
            f" — {_flat(str(ref.get('note') or ''))[:88]}"
            for kind, _, ref, path in entries if kind == "c"
        )

    _write(buckets, sections, index)
    print(f"已写 missed_references.md（{sum(buckets.values())} 条，{len(sections)} 个 PR）")
    for kind, note in (
        ("c", "说了，但不是一个角度（**先看这 16 条**：话已经说了，差的是角度）"),
        ("a", "看到了，没看出来（提示词/维度的问题）"),
        ("b", "根本没看到（检索/分组的问题）"),
        ("d", "结构上不可达（不是我们的问题）"),
    ):
        print(f"  ({kind}) {note}：{buckets[kind]}")
    return 0


def _render_pr(inst: dict, entries: list[tuple[str, str, dict, str]],
               by_file: dict[str, list[dict]]) -> str:
    """渲染一个 PR 的段落。

    Args:
        inst: 数据集记录
        entries: (类别, 位置判定, 参考, 路径)
        by_file: 我们在该 PR 上报的评论，按文件分组

    Returns:
        markdown 段落
    """
    order = {"c": 0, "a": 1, "b": 2, "d": 3}
    tally = " / ".join(
        f"{k} {sum(1 for e in entries if e[0] == k)}" for k in "cabd"
        if any(e[0] == k for e in entries)
    )
    lines = [f"\n## {inst['instance_id']}（{len(entries)} 条未命中：{tally}）\n"]
    for kind, where, ref, path in sorted(entries, key=lambda e: (order[e[0]], e[3])):
        lines.append(
            f"### ⬜ ({kind}) `{path}:{ref.get('from_line')}-{ref.get('to_line')}`"
            f"（{ref.get('side')}）"
        )
        lines.append("")
        lines.append(f"- **为什么在这个桶**：{where}")
        lines.append(f"- **参考原文**：{_flat(str(ref.get('note') or ''))}")
        if ref.get("matched_note"):
            lines.append(f"- **我们说的（裁判判为不同）**：{_flat(str(ref['matched_note']))}")
        ours = by_file.get(path) or []
        if ours:
            lines.append(f"- **我们在同一个文件里的评论（{len(ours)} 条）**：")
            for comment in ours[:4]:
                text = _flat(str(comment.get("content") or ""))[:260]
                lines.append(f"    - `{comment.get('start_line')}` {text}")
        else:
            lines.append("- **我们在同一个文件里的评论**：一条都没有")
        lines.append("")
    return "\n".join(lines)


def _flat(text: str) -> str:
    """把多行文本压成一行（清单要能一行一条地读）。

    Args:
        text: 原文

    Returns:
        单行文本
    """
    return " ".join(text.split())


def _write(buckets: Counter[str], sections: list[str], index: list[str]) -> None:
    """写出清单。

    Args:
        buckets: 各桶计数
        sections: 逐 PR 的段落
        index: (c) 桶的索引（只有 16 条，先从这一类看）
    """
    head = [
        "# 未命中的参考评论清单（可逐条读、可打标签）\n",
        f"数据：`{BENCH}` 的 `{RUN}` 那一局。**每条参考一个问题：那个位置，我们有没有机会看到？**\n",
        "| 桶 | 含义 | 条数 |",
        "|---|---|---|",
        f"| (c) | 行号命中了但裁判判为「不是同一件事」 | {buckets['c']} |",
        f"| (a) | 位置落在我们审过的 hunk 里，附近一条评论都没有 | {buckets['a']} |",
        f"| (b) | 位置不在我们审过的任何 hunk 里 | {buckets['b']} |",
        f"| (d) | 结构上不可达（非 `.go` / 测试文件） | {buckets['d']} |",
        "",
        "**怎么用**：把 `⬜` 改成 `✅`，觉得分错桶就直接改括号里的字母。",
        "判 (a)/(b) 的判据是**确定算出来的**（参考行落没落在我们审过的 hunk 区间里），",
        "所以 (b) 基本不用怀疑。",
        "",
        "> ⚠️ **(a) 里必然混着一批其实属于 (c) 的**：判桶只看「参考行在不在我们审过的 hunk 里」，",
        "> 分不出「同一件事说在别的行」。下面这个例子就是 —— 参考在 `config.go:14`、",
        "> 我们说的是同一件事、但写在 `:36`：",
        ">",
        "> - 参考：`LogDisableProbes` 该用 bool 而不是 string",
        "> - 我们（第 36 行）：`LogDisableProbes` 用 `GetOrDefault(..., \"false\")` 取值后",
        ">   与 `== \"true\"` 严格比较，`TRUE`/`True` 会被判为关闭 —— **同一个问题**",
        ">",
        "> 所以读 (a) 时先扫一眼「同一个文件里的评论」，像上面那种直接改成 (c)。",
        "",
        "## (c) 的 16 条（先从这一桶看：话已经说了，差的是角度）",
        "",
        *index,
        "",
    ]
    (ROOT / "missed_references.md").write_text(
        "\n".join(head) + "\n".join(sections) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
