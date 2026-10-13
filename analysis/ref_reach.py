"""量一件事：174 条参考里，有多少条**从一开始就没被送进模型**。

分三类：非 .go（我们只审 Go）/ 是 .go 但被过滤器排除 / 真的进了审查范围。
"""
import collections
import json
import os
import subprocess
from pathlib import Path

try:
    from prism.core.diff.loader import load_diffs
    from prism.core.filter.rules import filter_files
except ImportError as exc:  # pragma: no cover
    raise SystemExit("需要先装上 prism（pip install git+https://github.com/bytejf/prism）") from exc

ROOT = Path(
    os.getenv(
        "PRISM_EVAL_HARNESS",
        Path(__file__).resolve().parent.parent / "aacr-bench" / "evaluation",
    )
).resolve()
CACHE = ROOT / "repo"
rows = [json.loads(line) for line in open(ROOT / "data" / "prism-go-all.jsonl")]
kind = collections.Counter()
detail = collections.Counter()

for row in rows:
    repo = CACHE / row["repo"].replace("/", "__")
    base, head = row["base_commit"], row["head_commit"]
    for sha in (base, head):
        subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
                       capture_output=True, check=False)
    try:
        reviewable = filter_files(load_diffs(repo, base, head)).reviewable
    except Exception as exc:  # noqa: BLE001
        print(f"跳过 {row['instance_id']}：{exc}")
        continue
    paths = {d.path for d in reviewable}
    for ref in row["reference_comments"]:
        p = ref["path"]
        if not p.endswith(".go"):
            kind["非 .go（结构上不可达）"] += 1
        elif p in paths:
            kind["进了审查范围"] += 1
        else:
            kind["是 .go 但被过滤排除"] += 1
            detail[p.split("/")[-1]] += 1

total = sum(kind.values())
print(f"参考合计 {total}")
for k, v in kind.most_common():
    print(f"  {k:<24}{v:>4}  {v / total * 100:5.1f}%")
print()
print("被过滤排除的文件名：", dict(detail.most_common(8)))
