#!/usr/bin/env bash
#
# 把本仓库的适配层接到上游 AACR-Bench harness 上。
#
#   1. 检出上游到 ./aacr-bench（固定在 UPSTREAM_REF 那个提交）
#   2. 打上 patches/ 里的补丁（已应用则跳过）
#   3. 把 adapters/prism_reviewer.py 接到 reviewers/prism.py
#   4. 把 benchmarks/*.jsonl 放进 harness 的 data/
#
# 幂等：可以重复跑。
#
# 环境变量：
#   UPSTREAM_URL       上游仓库地址（默认 alibaba/aacr-bench）
#   UPSTREAM_REF       固定到哪个提交（默认见下 —— 换它意味着换了评测环境）
#   PRISM_EVAL_CLONE   检出到哪（默认 ./aacr-bench）
#   PRISM_EVAL_HARNESS harness 的 evaluation 目录（默认 <clone>/evaluation）
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/alibaba/aacr-bench.git}"
# **固定提交，不用分支**：跑的是哪个版本必须可复现，否则「上次还好好的」会变成悬案
UPSTREAM_REF="${UPSTREAM_REF:-68a569759289a83654a59d06db2a72910edf0a4a}"
CLONE="${PRISM_EVAL_CLONE:-$REPO_ROOT/aacr-bench}"
HARNESS="${PRISM_EVAL_HARNESS:-$CLONE/evaluation}"
PATCH="$REPO_ROOT/patches/upstream-adaptations.patch"

say() { printf '\033[1m→\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------- 1. 检出
if [ ! -d "$CLONE/.git" ]; then
  say "检出上游 $UPSTREAM_URL"
  git clone --quiet "$UPSTREAM_URL" "$CLONE"
fi

say "切到 $UPSTREAM_REF"
# 上游 clone 出来的是默认分支，要的那个提交可能还不在本地（浅克隆 / 新提交）
if ! git -C "$CLONE" cat-file -e "${UPSTREAM_REF}^{commit}" 2>/dev/null; then
  git -C "$CLONE" fetch --quiet origin "$UPSTREAM_REF"
fi
git -C "$CLONE" checkout --quiet "$UPSTREAM_REF"

# ---------------------------------------------------------------- 2. 补丁
if git -C "$CLONE" apply --check -p1 "$PATCH" 2>/dev/null; then
  git -C "$CLONE" apply -p1 "$PATCH"
  say "补丁已应用（$(grep -c '^diff --git' "$PATCH") 个文件）"
else
  say "补丁已应用过，跳过"
fi

# ------------------------------------------------------------ 3. 适配层
mkdir -p "$HARNESS/reviewers"
cp "$REPO_ROOT/adapters/prism_reviewer.py" "$HARNESS/reviewers/prism.py"
say "适配层已接到 reviewers/prism.py"

# ------------------------------------------------------------ 4. 批次
mkdir -p "$HARNESS/data"
cp "$REPO_ROOT"/benchmarks/*.jsonl "$HARNESS/data/"
say "批次已放进 data/（$(ls "$REPO_ROOT"/benchmarks/*.jsonl | wc -l | tr -d ' ') 个）"

# ---------------------------------------------------------------- 收尾
if [ ! -d "$HARNESS/.venv" ]; then
  say "还没建虚拟环境 —— 接下来："
  printf '\n    cd %s\n    uv venv && uv pip install -r requirements.txt\n\n' "$HARNESS"
fi

cat <<EOF

准备好了。跑一批：

    cd $HARNESS
    JUDGE_BASE_URL=https://api.deepseek.com JUDGE_API_KEY="\$DEEPSEEK_API_KEY" \\
    JUDGE_MODEL=deepseek-flash JUDGE_USE_MOCK=false \\
    .venv/bin/python -m pipeline run --stage all --reviewer prism \\
      --dataset data/prism-vs-ocr.jsonl

看结果：

    python $REPO_ROOT/analysis/prism_report.py

EOF
