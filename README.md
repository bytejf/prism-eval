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
再把适配层接进去。

这样分开的理由很实际：**上游的 `judge.py` 是裁判**。把它抄一份进自己的仓库，
「我们改过判分规则」就永远说不清了。

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

**这节比结果重要。** 数字不带上这些口径就是误导。

### 判分走四段匹配

对**每条参考**扫过**全部**生成评论，四段都要过：

```
路径 → 侧（LEFT / RIGHT）→ 行号（容差 ±1）→ LLM 语义
```

只有语义命中才 `break`。而且**一条生成评论最多兑一条参考**（两个额度各自只兑
一次）—— 所以**产出条数就是召回的天花板**：想兑上 37 条参考，至少得报 37 条。

### 三件必须一起报的事

| 口径 | 为什么 |
|---|---|
| **两套分母** | 官方参考里有一批**不在 `.go` 上**（`.mts` / `.cpp` / `.mod` / `.js` …）—— Prism 只审 Go，召回上限天然低于 100%，有效分母要单独算 |
| **ground truth 是抽样不是全集** | 官方标注只收「这条有价值」，没收「这条是错的」。所以专家没标的问题和真正的幻觉在**精确率**里长得一模一样 —— **精确率被系统性低估** |
| **裁判会抖** | judge 的 temperature 是 0.7。报任何提升之前，必须把**同一批输出重判 5 次**取区间，否则分不清提升和抖动 |

第三条不是理论：某个 PR 上，同一份输出重判 5 轮的 F1 是
`0.363 / 0.545 / 0.363 / 0.363 / 0.363` —— **那一次 0.545 是裁判抖动**。
6 条参考的分母太小，一条评论翻面就是 0.167 的召回摆动。

### 复现命令

```bash
# 同一批输出重判 5 轮
.venv/bin/python -m pipeline run --stage eval --reviewer prism \
  --dataset data/prism-vs-ocr.jsonl --run-id <run> --eval-rounds 5
```

## 实测结论

**五 PR 横向对照批次**（AACR-Bench Go 子集）

| 指标 | 值 |
|---|---|
| 语义 F1 | **0.237** |
| 精确率 / 召回率 | 0.231 / 0.243 |
| 单 PR 平均耗时 / 花费 | 196 秒 / 1.04 元 |
| 评论定位成功率 | **100%**（40/40） |

**一次提示词迭代**

| | 语义 F1 |
|---|---|
| 迭代前 | 0.211 |
| 迭代后 | **0.387**（同批重判 5 次，新旧区间不重叠） |
| **生成方差（这一行不能省）** | 同一配置重复跑：**0.393 / 0.254** |

最后一行是必须报的：**同一配置重复跑出来的差距，比要证明的那个提升还大。**
任何单次运行的数字都不该被当成结论。

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

**判分规则本身一行没改。**

## 归属与许可

- **本仓库自己的代码**：MIT（见 `LICENSE`）
- **AACR-Bench**（数据集 + judge + pipeline）：[Apache-2.0](https://github.com/alibaba/aacr-bench)，
  以依赖形式使用，未复制其源码 —— 见 `NOTICE`
- 上游被固定在一个提交上（见 `setup.sh` 的 `UPSTREAM_REF`）：
  「跑的是哪个版本」必须可复现
