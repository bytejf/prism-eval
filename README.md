# prism-eval

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**Prism 的评测接入层与分析工具** —— 建在 [AACR-Bench](https://github.com/alibaba/aacr-bench) 官方 harness 之上。

这个仓库回答的不是「Prism 好不好」，而是**「怎么知道它好不好」**：
怎么判分、分母是什么、提升是不是噪声、漏检卡在哪一层。

---

## 这是什么 / 不是什么

**是**：一组接入件与分析方法，让官方 harness 能跑 Prism，并把结果拆开看。

**不是**：一个自成一体的评测框架。评测的**执行、判分、数据**都来自上游
AACR-Bench —— 本仓库不复制它，只用 `setup.sh` 把它检出到本地、打上补丁、
再接上适配层。

不复制的原因是**可复现性**：判分规则与数据集都在上游演进，复制一份进来就会与
上游漂开，而「这次跑的是哪一版判分」必须答得出来。

```
prism-eval  ← 本仓库：适配层 + 分析工具 + 补丁 + 文档
    │
    └── 接进 → aacr-bench（上游，Apache-2.0）：数据集 + judge + pipeline
```

## 快速开始

```bash
# 1. 装上 Prism（两个分析工具借它的流水线算「哪些行进过审查范围」）
pip install git+https://github.com/bytejf/prism

# 2. 检出上游 harness、打补丁、接上适配层
./setup.sh

# 3. 跑一批
cd aacr-bench/evaluation
JUDGE_BASE_URL=https://api.deepseek.com JUDGE_API_KEY="$DEEPSEEK_API_KEY" \
JUDGE_MODEL=deepseek-flash JUDGE_USE_MOCK=false \
.venv/bin/python -m pipeline run --stage all --reviewer prism \
  --dataset data/prism-vs-ocr.jsonl

# 4. 看结果（prism_report 要吃一个 run 目录）
python ../../analysis/prism_report.py results/prism-vs-ocr/prism/<run_id>
```

### 跑对照工具（OCR）时的四条约束

**① 必须显式设 `OCR_LLM_PROTOCOL=openai`。**

OCR 的协议**默认是 Anthropic**（`internal/llm/resolver.go`：`useAnthropic := true // default true`）。
只设 `OCR_LLM_URL/TOKEN/MODEL` 的话，它会拿 Anthropic 协议去打 `https://api.deepseek.com` ——
**立即失败且消耗 0 token**，报错只有一句 `check your LLM configuration and API key`，
看不出真正的原因。

**② `HOME` 要指向一个没有 `.opencodereview/config.json` 的目录。**

OCR 的解析顺序是「配置文件 > OCR 环境变量 > Claude Code 环境 > shell rc」，
而**配置策略在文件存在但 provider 没配时会直接报错**，不会回落到环境变量。

```bash
mkdir -p /tmp/ocr-home            # 空目录即可
cd aacr-bench/evaluation
HOME=/tmp/ocr-home \
OCR_LLM_URL=https://api.deepseek.com \
OCR_LLM_TOKEN="$DEEPSEEK_API_KEY" \
OCR_LLM_MODEL=deepseek-flash \
OCR_LLM_PROTOCOL=openai \
JUDGE_BASE_URL=https://api.deepseek.com JUDGE_API_KEY="$DEEPSEEK_API_KEY" \
JUDGE_MODEL=deepseek-flash JUDGE_USE_MOCK=false \
.venv/bin/python -m pipeline run --stage all --reviewer ocr \
  --dataset data/prism-vs-ocr.jsonl --eval-rounds 5 \
  --ocr-command /path/to/opencodereview
```

**③ 不要传 `--max-tools`。** OCR 的默认是 100，且有一个硬下限：**低于 50 会被静默夹到 50**。
传 30 实际生效的是 50，等于给对照对象降档（那一局会出 `status=partial`）。省略该参数即可。

**④ `--effort` 同样不要传** —— 默认 medium（2 轮），与它官方 benchmark 的口径一致。

## 三个工具

| 工具 | 干什么 | 需要 Prism 吗 |
|---|---|---|
| `analysis/prism_report.py` | 把一局结果汇总成**逐 PR 画像 + 总计**，两套分母都报 | 否（纯标准库） |
| `analysis/ref_audit.py` | 把**没命中的参考**导成可逐条读的清单，按「有没有机会看到」分四类 | 是 |
| `analysis/ref_reach.py` | 可达性拆账：多少条参考从一开始就没被送进模型 | 是 |

`ref_audit.py` 是这三个里最有用的一个。跑完一批之后手上只有一个聚合数字
（比如召回 0.132），而「该改什么」取决于漏掉的那些**分别属于哪一类**。

它把每条没命中的参考分成四类，判据是确定的 —— **参考所在的行，落没落在我们
审过的 hunk 区间里**：

| 桶 | 含义 | 该怎么办 |
|---|---|---|
| **(a) 看到了，没看出来** | 位置在我们审过的 hunk 里，那条线附近一条评论都没有 | 判断力问题 |
| **(b) 根本没看到** | 位置不在我们审过的任何 hunk 里 | 检索 / 范围界定问题 |
| **(c) 说了，但不是一个角度** | 行号命中、语义没命中 | 措辞 / 判分口径问题 |
| **(d) 结构上不可达** | 非 `.go`、或在被排除的测试文件上 | 审查范围问题 |

**这个分类把改进方向从「猜」变成了「读」。** 实测 151 条未命中里
**(a) 占 81%** —— 瓶颈不在「没看到」，在「看到了没形成判断」。
一条把资源投在检索上的改进路线，会在这一步被否掉。

## 评测口径

数字不带上这些口径就是误导 —— 本节与结果同等重要。

### 判分走四段匹配

对**每条参考**扫过**全部**生成评论，四段都要过：

```
路径 → 侧（LEFT / RIGHT）→ 行号（容差 ±1）→ LLM 语义
```

只有语义命中才 `break`。而且**一条生成评论最多兑一条参考**（两个额度各自只兑
一次）—— 所以**产出条数就是召回的天花板**：想兑上 143 条参考，至少要报 143 条。

### 三件必须一起报的事

| 口径 | 为什么 |
|---|---|
| **分母只含审查范围内的标注** | 数据集里有一批标注落在非 Go 文件上（`.mts` / `.cpp` / `.js` …），本工具不审那些文件，**它们不进分母** —— 否则是拿工具明确不做的部分扣它的分 |
| **ground truth 是抽样不是全集** | 官方标注只收「这条有价值」，没收「这条是错的」。所以专家没标的问题和真正的幻觉在**精确率**里无法区分 —— **精确率被系统性低估** |
| **裁判会抖** | judge 的 temperature 是 0.7。报任何提升之前，必须把**同一批输出重判 5 次**取区间，否则分不清提升和抖动 |

第三条来自实测：某个 PR 上，同一份输出重判 5 轮的 F1 是
`0.363 / 0.545 / 0.363 / 0.363 / 0.363` —— **那一次 0.545 是裁判抖动**。
6 条参考的分母太小，一条评论翻面就是 0.167 的召回摆动。

### 复现命令

```bash
# 同一批输出重判 5 轮
.venv/bin/python -m pipeline run --stage eval --reviewer prism \
  --dataset data/prism-vs-ocr.jsonl --run-id <run> --eval-rounds 5
```

## 实测结论

**全量：6 个仓库 / 22 个真实 PR / 143 条标注**（AACR-Bench Go 子集）

| 口径 | 精确率 | 召回率 | F1 | 命中 |
|---|---|---|---|---|
| **语义**（裁判 LLM） | 0.243 | 0.235 | **0.239** | 33.6 / 143 |
| **行号**（确定性） | 0.391 | 0.378 | **0.384** | 54 / 143 |

语义指标取同批输出重判 5 次的均值（本次 5 轮 `0.228 ~ 0.249`）；
**行号指标不重判** —— 那一段不调 LLM，5 轮必然一致。

| 规模 | 值 |
|---|---|
| 单 PR 平均耗时 | 242 秒 |
| 评论定位成功率 | **100%**（138/138，其中 135 条一次命中本 hunk） |

**一次提示词迭代**（6 个 PR / 30 条专家标注）

| | 语义 F1 |
|---|---|
| 迭代前 | 0.229 |
| 迭代后 | **0.414** |
| **生成方差** | 同一配置重复跑：**0.421 / 0.281** |

**该提升不可外推**：那 6 个是**小 PR**。同一批改动放到 22 个 PR 全量上，
净效果是 **0.201 → 0.239（+0.038）**，且一半的增量来自一个仓库。
小样本与全量量的是不同对象，两者的差异不构成矛盾。

**末尾两行不可省略** —— 同一配置重复跑出来的差距，**比要证明的那个提升还大**。
任何单次运行的数字都不构成结论。

## 目录

```
adapters/prism_reviewer.py     接进上游 harness 的 reviewer 插件
                               （要被拷到 aacr-bench/evaluation/reviewers/）
patches/upstream-adaptations.patch
                               我们对上游 harness 的 3 处改动，共 47 行
benchmarks/*.jsonl             我们挑的批次（从数据集中选出的 PR 子集）
analysis/*.py                  三个分析工具
docs/missed_references*.md     归因分析的产物，可逐条读
setup.sh                       检出上游 → 打补丁 → 接适配层
```

### 我们对上游做了什么（`patches/`）

一共 47 行，三处，都是「让 harness 能报告我们关心的东西」：

- `evaluate.py` —— 把**行号命中**与**语义命中**分开统计（上游只报一套）
- `pipeline.py` —— 支撑 `--eval-rounds`（同一批输出重判多轮，用于量裁判抖动）
- `positive_samples.meta.json` —— 数据集下载元信息

三处都只改**报告粒度**，不改**判据**。

## 归属与许可

- **本仓库自己的代码**：MIT（见 `LICENSE`）
- **AACR-Bench**（数据集 + judge + pipeline）：[Apache-2.0](https://github.com/alibaba/aacr-bench)，
  以依赖形式使用，未复制其源码 —— 见 `NOTICE`
- 上游被固定在一个提交上（见 `setup.sh` 的 `UPSTREAM_REF`）：
  「跑的是哪个版本」必须可复现
