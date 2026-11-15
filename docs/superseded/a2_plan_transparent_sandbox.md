> **Superseded (15 Nov 2026).** This plan describes an earlier idea for Assignment 2, a
> *Transparent Sandbox* recommender interface. It was replaced by LitLens, the evidence-first
> Q&A system in this repository, because the Q&A format keeps the Assignment 1 concern
> (users cannot inspect or correct a model's reasoning) while staying inside the time available
> and the assignment's scope. Kept as a record of that decision; nothing here is implemented.
# A2 Project Report — 执行计划
**项目**：Transparent Sandbox（承 A1 文献综述）
**截止**：2026-11-20 21:00（Europe/London）｜**编制日**：2026-11-15
**技术栈**：Python 3.11 + Streamlit + Plotly ｜**报告交付**：Word .docx + 独立 PNG 图

---

## 0. 先定死的一句话定位

> 一个**本地可运行的 Streamlit 单页沙盒**：用户拖动三个推荐权重滑块（观点多样性 / 话题新颖度 / 来源权威性），左侧看「如果立刻生效，接下来的信息流长什么样」，右侧看「未来 20 条曝光累计后的多样性拓扑」，并配有软下限护栏防止用户把自己锁进更窄的茧房。

这句话同时决定了：实现了什么（滑块 + 重排 + 指标 + 投影 + 护栏）、模拟了什么（语料与用户画像）、计划了什么（接真实平台、LLM 生成解释）。

---

## 1. 范围三分（报告和 README 都要这么标）

| 状态 | 内容 | 交付里怎么体现 |
|---|---|---|
| **Implemented** | 合成语料（≥120 条带 topic/viewpoint/authority 标注的条目）；加权打分重排；4 个多样性指标；What-If 未来曝光投影；护栏告警；交互日志 CSV；参数预设 | 可跑 + 截图 + 提交号 |
| **Simulated** | 条目语料是脚本生成的（非真实平台抓取）；用户画像由固定 seed 合成；"未来曝光"是蒙特卡洛模拟而非线上 A/B | 界面上打 `Simulated corpus` 徽标；README 明说 |
| **Planned** | 接真实 feed API；LLM 生成自然语言解释（当前为模板解释）；多用户与长周期真实轨迹回放 | 系统图里用虚线框 + `PLANNED` 标签 |

> 红线：任何地方都不要写「已验证」「已提升用户多样性」这类没做过的因果断言。没跑用户研究就只写「设计依据来自文献与自查」，不要编 SUS 分数。

---

## 2. 系统架构（先画图，再写代码）

### 2.1 组件清单

| # | 组件 | 职责 | Streamlit 落点 |
|---|---|---|---|
| C1 | Corpus Loader | 读 `data/items.csv`，字段：id, title, topic, viewpoint(-1/0/+1), authority(0-1), embedding(8 维) | `@st.cache_data` |
| C2 | User Model | 固定 seed 的兴趣向量 + 历史点击序列 + 立场分布 | `session_state.user` |
| C3 | Scorer | `score = w_rel·rel + w_nov·novelty + w_auth·authority`，softmax 采样出 top-20 | 纯函数 `rank_feed()` |
| C4 | Diversity Metrics | 话题熵（归一化）、对立观点曝光率、来源权威均值、新颖度 | 纯函数 `metrics()` |
| C5 | What-If Projector | 用当前权重跑 N 轮（默认 20）曝光模拟，产出累计分布 | 纯函数 `project()` |
| C6 | Guardrail | 若投影对立观点曝光率 < 0.20 → 告警并把该权重抬回软下限 | 纯函数 `guardrail()` |
| C7 | Explainer | 模板生成「为什么这条排第一」（引用命中的最高分量） | 纯函数 `explain()`，**标 simulated** |
| C8 | Interaction Log | 每次滑块变更 / 预设点击 / 告警触发 → 追加 CSV | `logs/session_<ts>.csv` |
| C9 | UI Shell | 双面板布局 + 滑块 + 指标卡 + 预设按钮 | `app.py` |

### 2.2 数据流（画图时照这个连线，箭头方向别反）

```
[items.csv] → C1 → C3 ← C2(user model)
                     ↓
              C7 explain ──→ UI 左面板（Current feed, 20 条）
                     ↓
              C5 project ← 滑块权重（C9）
                     ↓
              C4 metrics → UI 右面板（Projected topology + 4 指标卡）
                     ↓
              C6 guardrail → 告警条 / 抬回权重 → 回到 C3
C8 日志 ← 所有 UI 事件
```

**AI 行为要单独画一个框**（评分项明确要求）：C3 的加权重排 + C5 的预测模型就是「AI 行为」；框内注明 `heuristic re-ranker (implemented)` 与 `template explainer (simulated)`。如果最后加了 LLM，再补一条虚线 `LLM explainer — PLANNED`。

### 2.3 指标定义（写进 README，评审者能复核）

- 话题熵：`H = -Σ p_i·log p_i`，再除以 `log K` 归一化到 0–1
- 对立观点曝光率：`share(items where viewpoint = -sign(user_majority))`
- 来源权威均值：`mean(authority)`
- 新颖度：`mean(1 - cosine(item_emb, user_history_centroid))`

### 2.4 Streamlit 的三个坑（这几个坑就是报告里「技术权衡」的素材）

1. **每次 widget 变化整脚本重跑** → 所有计算必须走 `@st.cache_data`，目标单次重排 < 150ms；把「重跑整页」写进报告，作为放弃动画式实时预览的理由。
2. **`st.slider` 拖动过程中不触发**，松手才触发 → 交互模型变成「调参 → 松手 → 立刻看到结果」，报告里老实写成 trade-off，不要声称是连续流式反馈。
3. **会话状态会被 rerun 清掉** → 权重、日志句柄、历史序列一律进 `st.session_state`，否则预设按钮和护栏抬回会互相打架。

---

## 3. 报告结构与字数预算（合计 1,310）

首页顶部写：`Total report word count: X,XXX (abstract 2XX + main XXX)`。**表格内文字计入**。

| 章节 | 目标字数 | 要点 |
|---|---|---|
| Abstract | ≤300（目标 260） | 问题 → 方法 → 做出了什么 → 当前范围（明确写 implemented/simulated/planned 各是什么） |
| 1. Problem and scope | 120 | 承接 A1：filter bubble + 后端去偏研究多、前端可审计界面少；本项目的范围边界 |
| 2. Design rationale（表格） | 550 | 6 行，每行 = 选择 / 为何适合 / 证据·文献 / 状态 |
| 3. Interaction walkthrough | 150 | 用文字把 storyboard 串起来，只写「用户做什么 → 系统给什么反馈 → 用户如何收回控制」 |
| 4. Architecture and technical reasoning | 120 | 三个 Streamlit 约束如何塑造设计（见 2.4） |
| 5. What I learned / reflection | 60 | 认知负荷与护栏的张力：给了自主权又用软下限限制它，这个矛盾怎么处理 |

### 3.1 设计理由表（直接填，每格别写成段落）

| 设计选择 | 为什么适合问题 | 支持证据 / 引用 | 状态 |
|---|---|---|---|
| 单页双面板：当前 feed ‖ 投影 feed 并置 | 让「执行」与「评估」的沟壑（gulf of execution / of evaluation）在同一屏闭合，用户不用在脑内模拟后果 | Norman (1988); A1 指出的缺口：现有界面只给局部即时调整 | Implemented |
| 三个语义化权重滑块 + 命名预设（Balanced / Exploratory / Focused） | 直接操作（direct manipulation）优于输入参数；预设降低高维控制的认知负荷，给了新手一个安全起点 | Shneiderman (1983); A1 的已知局限「高维参数控制风险导致认知疲劳」 | Implemented |
| What-If 累计曝光投影（20 轮）而非事后解释 | 把反馈从「解释过去」推到「预览未来」，正对 A1 提出的 gap | Tintarev & Masthoff (2015) 的解释是单向的；He et al. (2016) 的认知过载警告 | Implemented |
| 指标卡 + 阈值告警（可见的系统状态） | 用户需要知道操作是否生效、是否越界，而不是靠猜 | Nielsen 启发式 #1 visibility of system status；#3 user control and freedom | Implemented |
| 软下限护栏（对立曝光 <20% 时告警并抬回） | 回应「自主权反过来强化确认偏误」的伦理风险：保留控制感但设失败安全 | Lee & See (2004) 的适当信赖；A1 的 fail-safe 承诺 | Implemented |
| LLM 生成个性化解释 | 模板解释生硬，自然语言能提升可理解性 | Tintarev & Masthoff (2015) | **Planned** |

> 写法提醒：评分明确要求「点名概念并说明它如何影响了决策，而不是罗列术语」。合格句式是「因为 **visibility of system status** 要求系统状态持续可见，所以我把四个指标做成常驻卡片，而不是折叠进设置页」。不合格是「本项目运用了 Nielsen 启发式和 direct manipulation」。
>
> **周次归属必须自己核**：上面这些概念（Norman 的执行/评估沟壑、Shneiderman 直接操作、Nielsen 启发式、Horvitz 混合主动、Amershi 等人的 HAI 指南、Lee & See 信赖校准）都是 HCI/HCAI 的标准内容，但**哪一周讲了什么以你自己的 lecture 手稿为准**，报告里写错周次比不写更糟。

### 3.2 摘要骨架（260 词，自己重写一遍再计数）

问题（60）→ A1 识别的缺口（40）→ 本系统做了什么、怎么工作（90）→ 范围与状态（40）→ 学到什么（30）。

---

## 4. 图与故事板清单（图注不计字数，别在图里塞段落）

| 编号 | 内容 | 工具 | 耗时 |
|---|---|---|---|
| Fig 1 | 系统图（组件 + 箭头 + 实现/模拟/计划三色边框） | draw.io 或 Lucidchart | 60 min |
| Fig 2–4 | 三个 storyboard（4 格/个：动作 → 系统响应 → 反馈 → 收回控制） | 截图 + draw.io 拼格 | 90 min |
| Fig 5 | 界面全景截图（双面板 + 指标卡 + 告警态） | `st.screenshot` 或系统截图 | 10 min |
| Fig 6 | 日志 CSV 的可视化（一次会话的权重轨迹 vs 多样性） | Plotly 导出 PNG | 30 min |

**三个故事板建议这样分工**（覆盖三类交互，别重复）：
1. **新手用预设**：点 `Exploratory` → feed 立刻变多样 → 指标卡熵值升 → 用户理解预设含义。
2. **手动调到极端**：把观点多样性拉满 → 投影显示对立曝光 42% → 触发「已超出你的历史阅读习惯」提示 → 用户回调一格。
3. **触发护栏**：刻意把多样性拉到 0 → 投影 <20% → 告警条出现 + 权重被抬回 → 用户看到系统在保护他，日志记录该事件。

图里只放短标签（≤6 词），解释写进报告正文的 150 词 walkthrough。

---

## 5. 仓库与开发记录

### 5.1 目录

```
A2/
├─ app.py                  # UI 与事件绑定
├─ sandbox/
│  ├─ corpus.py            # C1 语料加载 + 生成脚本
│  ├─ scoring.py           # C3
│  ├─ metrics.py           # C4
│  ├─ project.py           # C5 + C6
│  ├─ explain.py           # C7
│  └─ logging.py           # C8
├─ data/items.csv          # 合成语料（提交进仓库，保证可复现）
├─ scripts/make_corpus.py  # 固定 seed 生成器
├─ logs/.gitkeep
├─ docs/                   # Fig1-6 PNG + report.docx
├─ tests/test_metrics.py   # 3-4 个纯函数断言，撑起技术可信度
├─ requirements.txt        # streamlit, plotly, pandas, numpy
└─ README.md
```

### 5.2 Commit 计划（每条对应 README 开发记录的一行，作者必须是你自己的 git 身份）

| 时间 | commit message | 对应 README 记录 |
|---|---|---|
| D0 | `chore: scaffold streamlit app and synthetic corpus generator` | 选定 Streamlit；为何合成语料 |
| D1 | `feat: weighted re-ranker with three semantic weight sliders` | 从「参数输入」改为「语义滑块 + 预设」 |
| D2 | `feat: what-if projection over 20 impressions with diversity metrics` | What-If 取代事后解释的原因 |
| D2 | `feat: guardrail soft floor for opposing-view exposure` | 护栏回应确认偏误风险 |
| D3 | `feat: interaction logging and template explainer` | 解释器降级为模板（诚实标注） |
| D3 | `fix: cache ranking to keep rerun under 150ms` | Streamlit 重跑模型的实测与修复 |
| D4 | `docs: system diagram, storyboards, report draft` | — |
| D5 | `docs: finalise README and release v1.0` + tag `v1.0` | 报告里写明提交的 release |

> 提交历史不是评分点，但「每个决策有对应提交」能让 20 分的证据项无争议。别在最后一天一条 `final` 提交全部代码。

### 5.3 README 骨架（开头标 prose 字数，代码/命令不计）

```markdown
# Transparent Sandbox
Prose word count: XXX (excluding code and commands)

## Project status
Implemented: … / Simulated: … / Unfinished: …

## Technology stack
Python 3.11, Streamlit, Plotly, pandas, numpy. LLM explainer: not used yet (template-based), planned.

## Running the work
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
No API keys required. Corpus is committed at data/items.csv (seed 42).

## Development record
- 2026-11-15 scaffold … (commit abc1234) — why / what I checked
- …

## AI assistance
Tool: <name>. Asked it to: <…>. Changed / rejected: <…>. Checked by: <…>.

## Additional files
docs/ holds Fig 1–6 and the submitted report.
```

`AI assistance` 别写空话，写 2–3 个具体例子 + 你改了什么 + 你用什么验证的（例如「AI 给的熵公式漏了归一化，我补了 log K 分母并用 tests/test_metrics.py 断言」）。

---

## 6. 五天排期（约 15 小时，按可用时间可压到 12）

| 日 | 时段 | 任务 | 产出 |
|---|---|---|---|
| **D0 11/15 晚** | 1.5h | 建仓、venv、`make_corpus.py` 出 120 条语料、空 app 能跑 | 首个 commit |
| **D1 11/16** | 3h | C1–C3 + 三个滑块 + 左面板 feed；跑通重排 | commit ×1–2 |
| **D2 11/17** | 3h | C4 指标卡 + C5 投影 + C6 护栏 + 右面板 | commit ×2 |
| **D3 11/18** | 3h | C7 模板解释 + C8 日志 + 性能修复 + 三组 storyboard 实录截图 | commit ×2 + 截图 |
| **D4 11/19** | 3h | Fig1 系统图 + Fig2–4 拼图 + **报告正文初稿 + 字数审计** | commit docs |
| **D5 11/20 白天** | 2h | 摘要重写、README 定稿、tag `v1.0`、导出 PDF 核对、**21:00 前提交** | 交付 |

**留 3 小时缓冲**：D5 不要排满，Canvas 上传失败和 LibreOffice 转 PDF 字体错位都很常见。

---

## 7. 风险与对策

| 风险 | 触发条件 | 对策 |
|---|---|---|
| 字数超限 | 表格里写成长段落 | D4 就审计；超了先砍 §3 walkthrough 和 §5，**绝不砍表格里的「证据」列**（那列是 30 分的主体） |
| 只有功能清单、没有交互证据 | 报告全在讲功能 | 每个 storyboard 必须在正文被引用一次，并写出「系统响应了什么」 |
| 概念只罗列 | 「本项目运用了 direct manipulation 等原则」 | 每个概念后面必须跟「因此我做了 X」；不会写就套 3.1 的句式 |
| Streamlit 拖动卡顿 | 语料 >500 条或 embedding 维度过高 | 锁 120 条 × 8 维；超时就写进报告当作设计约束 |
| 护栏被当成「功能缺陷」 | 用户觉得系统不听话 | 报告和界面文案都把它表述为 fail-safe，并引用 A1 自己的伦理讨论 |
| 评审者跑不起来 | 硬编码 Windows 路径 / 缺 `data/` | 全部用 `pathlib.Path(__file__).parent`；`data/` 提交进仓库 |
| 公开仓库里泄露 key | 后续接 LLM 时 | 用 `.env` + `.gitignore`，README 说明评审者自备 key 的方式 |

---

## 8. 开工前必须自己确认的三件事

1. **lecture 周次对应**：Weeks 1–4 具体讲了哪些概念？报告里的「第 N 周」必须对得上，这个我无法替你确认。
2. **GitHub 账号与仓库名**：先在 GitHub 建 public repo，再 `git remote add origin`，否则最后一天补推会丢作者信息。
3. **A1 的反馈**：如果有 tutor 对 A1 的评语，直接写进 rationale 的「supporting evidence」列，这是 brief 明确鼓励的来源。

