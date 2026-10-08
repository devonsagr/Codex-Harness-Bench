# GitHub 开源评测：前端验收、裁判校准与过度工程化

核对日期：2026-10-08。U78 调研；仅静态阅读公开源码、题目与数据索引，没有执行外部仓库或调用付费裁判。每个仓库版本见文末。题目摘要由本项目重新表述，完整题面与评分代码保留原来源链接。

## 结论与本项目的缺口

开源项目没有统一的“好用分”。最能借鉴的是先固定每题的操作/预期，再实际走流程，保存各状态画面，把画面直接提供给视觉裁判，并用已知好坏的页面验证裁判。复杂度须结合持续修改和回归观察，不能靠源码量或大架构加分。

- Vision2Web 的完整用户流程，比基础烟检更接近本项目。功能 Pass/Fail/Blocked 与视觉对照分开，但其榜单汇总将阻断/缺结果计0；我们的环境故障仍须单列。
- ArtifactsBench 已把真实图片放进模型请求；现有 CHB 截图文件存在门槛只证明保存了图，视觉通道尚未核实。它的公开截图函数也没有通用点击流程，不能替代任务验收。
- WebDevJudge Unit 专门测裁判对502个已标注任务的判断，表明应先验证裁判，而不是只验证 JSON/引用格式。作者特定GUI裁判两次公布的accuracy分别75.1%和71.7%（2025-09-18、2025-11-16），不是我们当前模型的准确率。
- SlopCodeBench 用逐轮需求与旧功能回归观察复杂度恶化；这比一次源码评分更贴合用户对过度工程化的关注。
- 有参考图的视觉还原题，与允许自由设计的交付题须分开；“像原图”不能被解释为“好看好用”。

## 标准、题型和公式对照

### 1. Vision2Web

- 范围：193 题 · 1,255 个功能用例。
- 标准：分成静态页面、交互前端、完整网站。功能裁判按预写的动作和验证条件操作浏览器；视觉裁判对照原型与实际截图。
- 评分：功能 FS：Pass 记 1，其余记 0；视觉 VS：组件按 0 / 0.25 / 0.5 / 0.75 / 1 分档后取均值。总榜按三个任务层级的均值计算，交互/全栈层内 VS 与 FS 等权。
- 证据：保存每条流程的 Pass / Fail / Blocked、原因和状态截图；视觉图片直接作为模型输入。
- 局限：视觉分主要衡量像不像参考图。代码汇总把 Blocked / 缺结果记 0；不能照搬为我们的环境失败判分。仓库 README 的许可声明与 HF 数据卡标注不一致，复用须先核清。
- 对本项目：借鉴完整流程、状态截图和功能/视觉分存；自由设计题不能强行按参考图逐像素打分。
- 原题与数据：[Vision2Web 题源](https://huggingface.co/datasets/zai-org/Vision2Web)；[评分代码](https://github.com/zai-org/Vision2Web/blob/d80a4a3d0ea7326541ad87314294269a633789e4/vision2web/evaluation/prompts.py)；[项目展示](https://vision2web-bench.github.io/)。

样题（摘要）：

- [OneDay Cloud · 交互前端](https://huggingface.co/datasets/zai-org/Vision2Web/viewer/frontend/test?row=0)（frontend/1daycloud）：从主页进入应用商店、指定应用、课程、服务与联系页面；核对页面导航和各状态。公开索引列出 6 个功能用例与 6 张原型图。 核对：按用户导航路径逐步检查结果，同时保存对应状态画面。
- [401 Trucksource · 卡车服务网站](https://huggingface.co/datasets/zai-org/Vision2Web/viewer/frontend/test?row=1)（frontend/401trucksource）：新车与二手车列表、维修服务、配件和车身维修入口；首页轮播与服务按钮应引向对应页面。公开索引列出 6 个用例。 核对：不是按钮有反应即可；要到达正确页面与正确状态。

### 2. WebGen-Bench

- 范围：101 题 · 647 条功能条件。
- 标准：每题有网站需求，另列操作 task 与 expected_result。浏览器评估者执行动作并判断完成程度；外观裁判单独看页面截图。
- 评分：功能项 YES = 1、PARTIAL = 0.5、NO = 0，按固定 647 条条件汇总。外观另给 1–5 级，不直接和功能分混成同一个万能分。
- 证据：逐次浏览器交互消息、条件结果和外观截图。
- 局限：部分汇总脚本按自由文本关键词提取结果；缺结果在固定分母下贡献 0。评分输出的解析不能原样搬过来，功能部分仍依赖 AI 判断。
- 对本项目：最值得借鉴的是每题提前写清“做什么操作、应得到什么结果”。
- 原题与数据：[WebGen-Bench 题源](https://github.com/mnluzimu/WebGen-Bench/blob/c89e0743438e458d617cebaf7a682e0e66e41049/data/test.jsonl)；[评分代码](https://github.com/mnluzimu/WebGen-Bench/blob/c89e0743438e458d617cebaf7a682e0e66e41049/src/ui_test_webgen/compute_acc.py)；[项目展示](https://huggingface.co/datasets/luzimu/WebGen-Bench)。

样题（摘要）：

- [股票报告生成器](https://github.com/mnluzimu/WebGen-Bench/blob/c89e0743438e458d617cebaf7a682e0e66e41049/data/test.jsonl)（000001）：输入股票代码或名称，选择报告内容和格式，再生成对应的报告。共有 7 条操作/预期结果条件。 核对：搜索是否返回对应信息，报告定制是否真的改变输出。
- [社区数据比较地图](https://github.com/mnluzimu/WebGen-Bench/blob/c89e0743438e458d617cebaf7a682e0e66e41049/data/test.jsonl)（000002）：比较不同区域的人口、经济与犯罪数据，配有交互图表和可调整的仪表盘布局。共有 5 条功能条件。 核对：切换区域后的数据、比较结果和图表状态是否正确。

### 3. ArtifactsBench

- 范围：1,825 题 · 逐题检查清单。
- 标准：网页、游戏、工具、SVG 等题型各有 checklist，每项写检查内容、分档和 maxScore。裁判接收题目、代码和真实渲染图片。
- 评分：每项有最大分；核对的样题清单上限合计 100。裁判输出分项和 Overall Score，后处理主要提取模型给出的总分。
- 证据：真实截图以图片内容进入多模态请求，而不只是提供图片文件路径；保存原始裁判结果。
- 局限：公开截图函数主要按时间截取画面，没有通用点击工作流。一些样题清单奖励原题未要求的动画/音效；不能照抄成额外工程要求。作者的人类一致性结果不等于每条验收都正确。
- 对本项目：借鉴明确分档、真实图像输入与裁判校准；清单必须严格追溯原题，避免奖励题外功能。
- 原题与数据：[ArtifactsBench 题源](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark/blob/88c968b87e150e63de7660937e6dcfb8e7d643cf/dataset/artifacts_bench.json)；[评分代码](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark/blob/88c968b87e150e63de7660937e6dcfb8e7d643cf/src/infer_gemini.py)；[项目展示](https://artifactsbenchmark.github.io/)。

样题（摘要）：

- [拖动与旋转方块的路径谜题](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark/blob/88c968b87e150e63de7660937e6dcfb8e7d643cf/dataset/artifacts_bench.json)（1）：通过拖动和旋转方块铺出通路，使角色到达目标；关卡之间有不同布局与挑战。 核对：拖动、旋转、路径判断及关卡进度分别检查。
- [角色升级与技能树](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark/blob/88c968b87e150e63de7660937e6dcfb8e7d643cf/dataset/artifacts_bench.json)（2）：收集经验升级，解锁技能或加强属性，使用简单经验与技能树结构。 核对：经验累计、等级与解锁依赖。注意其清单额外奖励动画/音效，超出了原题简要要求。

### 4. SlopCodeBench

- 范围：多轮需求 · 独立回归与代码质量。
- 标准：每道题由 checkpoint 逐轮加需求，后续实现要保留旧行为。功能测试分 CORE / FUNCTIONALITY / REGRESSION / ERROR；代码健康另量测。
- 评分：测试通过率与 checkpoint 通过策略分开。复杂度、verbosity、erosion 等单列，代码健康分越高通常越差，不直接当作好用总分。
- 证据：每轮冻结代码、测试结果、结构指标、资源数据；问题包与 runner 分开版本化。
- 局限：结构复杂度是线索，不能直接证明某个抽象多余。不能按文件数或行数一刀切扣分；必须结合本轮需求与功能回归。
- 对本项目：最贴近“避免过度工程化”；让功能演进和修改负担成为观察对象。
- 原题与数据：[SlopCodeBench 题源](https://github.com/gabeorlanski/scb-problems)；[评分代码](https://github.com/SprocketLab/slop-code-bench/blob/31ceea3add480edb33431e70475c4c70597e6b31/docs/metrics/interpreting-results.md)；[项目展示](https://www.scbench.ai)。

样题（摘要）：

- [备份调度器 · 第一轮](https://github.com/gabeorlanski/scb-problems/blob/9cd9ca3a51c3d3e2a99d2488a25baf73a2204451/file_backup/checkpoint_1.md)（file_backup/checkpoint_1）：读取 YAML 计划，判断指定时间哪些任务应执行，先模拟备份并输出 JSONL 事件。 核对：时间、排除规则、到期判断与输出事件。
- [备份调度器 · 第二轮](https://github.com/gabeorlanski/scb-problems/blob/9cd9ca3a51c3d3e2a99d2488a25baf73a2204451/file_backup/checkpoint_2.md)（file_backup/checkpoint_2）：在原调度器上增加完整备份、归档和校验策略；未设置策略时保持第一轮行为。 核对：新增能力与旧行为一起过测试，观察是否因改动引入回归和额外复杂度。

### 5. WebDevJudge

- 范围：Unit：502 例 · 279 正例 / 223 负例。
- 标准：将用户需求拆成目标、静态内容、基础交互、复杂交互的可验证叶子。用静态代码评估与 GUI 操作评估两条路线检验裁判。
- 评分：每个叶子按实现/未实现判定，四类完成比例取平均；Unit 用已标注能完成/不能完成的任务计算 precision、recall、F1 和 accuracy。
- 证据：已知标签、错误类型、预期结果，以及公开 GUI 轨迹。
- 局限：能输出完整报告不代表判得对。作者公布的特定 GUI 裁判在两个日期的 Unit accuracy 为 75.1% / 71.7%，不能外推为我们当前裁判或所有模型的准确率。
- 对本项目：先用已知好坏验证裁判，避免只检查它有没有返回 JSON 和分数。
- 原题与数据：[WebDevJudge 题源](https://github.com/lcy2723/WebDevJudge/blob/2d93e5af4e65ddba47704497adacc5d3c1e52b69/webdevjudge_unit/README.md)；[评分代码](https://github.com/lcy2723/WebDevJudge/blob/2d93e5af4e65ddba47704497adacc5d3c1e52b69/evaluator/rubric.py)；[项目展示](https://github.com/lcy2723/WebDevJudge)。

样题（摘要）：

- [已有按钮，点击无响应](https://github.com/lcy2723/WebDevJudge/blob/2d93e5af4e65ddba47704497adacc5d3c1e52b69/webdevjudge_unit/data/webdevjudge_unit.jsonl)（web_0/task_1）：点击免费试用入口，预期显示注册表单或说明弹窗。作者标签为不可完成，原因是按钮没反应。 核对：裁判能否识别“元素存在但功能不成立”。
- [点击图表出现对应详情](https://github.com/lcy2723/WebDevJudge/blob/2d93e5af4e65ddba47704497adacc5d3c1e52b69/webdevjudge_unit/data/webdevjudge_unit.jsonl)（web_0/task_2）：点击状态环图某部分，应显示该部分的详情或弹窗；作者标签为可以完成。 核对：裁判是否既能拒绝坏页面，也能正确接受好页面。

### 6. DesignBench

- 范围：900 个网页样本 · 四种前端技术。
- 标准：图到代码、已有页面编辑、UI 修复与编译错误修复分开。覆盖原生 HTML、React、Vue、Angular。
- 评分：编译/渲染结果、截图相似性、问题修复与代码改动相似性等指标分别计算。
- 证据：原始画面、目标画面、源码、修改要求与生成后的真实截图。
- 局限：像参考图不等于好用；代码相似性可能不利于不同但有效的实现。数据和依赖须另行准备，当前仅展示来源。
- 对本项目：借鉴编辑/修复题，避免题库全是从零生成和同一种 SVG。
- 原题与数据：[DesignBench 题源](https://huggingface.co/datasets/whale99/DesignBench)；[评分代码](https://github.com/WebPAI/DesignBench/blob/a1e58d66ecbf1f77848bc5529ee7bbbe33bc25ba/code/evaluator/main.py)；[项目展示](https://github.com/WebPAI/DesignBench)。

样题（摘要）：

- [图到前端实现](https://github.com/WebPAI/DesignBench)（Generation）：给定一张 UI 图，在指定前端技术中重建该页面。 核对：能编译、能渲染，组件布局与画面是否接近。
- [已有 UI 编辑或局部修复](https://github.com/WebPAI/DesignBench)（Edit / Repair）：给原页面、源码或标注区域，按修改要求编辑或修复页面。 核对：目标区域改善，其他内容是否保留；分别核对视觉和改动。

### 7. Design2Code

- 范围：484 个网页 · 视觉还原。
- 标准：输入网页截图，生成前端；对参考与实际画面做细粒度匹配。
- 评分：CLIP、文字块覆盖、内容、位置、颜色等视觉指标；用人工偏好研究核对视觉指标的意义。
- 证据：参考截图和实际渲染截图，匹配到的文字块。
- 局限：专门测视觉还原，没有完整业务流验收，不能用来证明自由设计作品的体验好。代码与数据许可分开。
- 对本项目：用于有参考图的对照与视觉缺陷例，不强加到自由创作题。
- 原题与数据：[Design2Code 题源](https://huggingface.co/datasets/SALT-NLP/Design2Code)；[评分代码](https://github.com/NoviScl/Design2Code/blob/7a575e4c33f417c4be5c64072b8f5798de0d0f99/Design2Code/metrics/README.md)；[项目展示](https://salt-nlp.github.io/Design2Code/)。

样题（摘要）：

- [从真实网页截图还原页面](https://huggingface.co/datasets/SALT-NLP/Design2Code)（Design2Code test set）：参照固定网页截图重建布局、文字与颜色，检查真实浏览器中的输出画面。 核对：文字块与布局位置匹配；并不检查完整业务成功。

### 8. Interaction2Code

- 范围：127 个页面 · 374 个交互。
- 标准：给交互原型图和 action.json，要求实现不同状态和操作。静态页面和交互区域分别观察。
- 评分：用动作后的页面/区域视觉结果对照参考，保留人工对功能可用性的判断；不是完整后端验收分。
- 证据：交互前后画面、动作描述、人工失败分类。
- 局限：只靠交互区域像不像仍可能漏掉业务错误；菜单、弹窗等单步交互不等于完整流程。
- 对本项目：借鉴动作和预期状态的配套题面，检查真正操作结果。
- 原题与数据：[Interaction2Code 题源](https://huggingface.co/datasets/whale99/Interaction2Code)；[评分代码](https://github.com/WebPAI/Interaction2Code/blob/29d8af1572888d33b028ef001dc8452f9e88497b/code/metric/calculate_metric.py)；[项目展示](https://webpai.github.io/Interaction2Code/)。

样题（摘要）：

- [选择项控制表单内容](https://github.com/WebPAI/Interaction2Code#benchmark-examples)（公开失败案例：Wrong interactive element）：选择以机构身份操作后，正确表单区域应出现；检查动作是否绑定在正确控件上。 核对：不能在别的按钮上实现相似变化来算成功。
- [菜单或弹窗交互](https://github.com/WebPAI/Interaction2Code#benchmark-examples)（交互原型 + action.json）：从原型的初始状态和操作说明实现菜单、弹窗、选择状态及返回行为。 核对：相关区域状态正确，既不漏交互，也不把业务信息藏在不能访问的状态中。

### 9. One-shot app benchmarks

- 范围：4 类完整应用 · 公开作品图库。
- 标准：完整需求冻结后开发；作者的独立浏览器流程、实际截图与匿名审查包组成证据。保留模型/配置、时间和资源条件。
- 评分：CAD 案例用三位独立裁判与十项预先声明的权重；产品 60 / 工程 40，分数由原始分项算回总分。
- 证据：可运行源码、原始题面、截图、盲评票与计算、资源记录和同模型不同方案的案例。
- 局限：个人案例研究，不是普遍排名；题目很大且有技术约束，不能直接代表我们的日常小任务。权重不应照搬。
- 对本项目：借鉴独立操作验收、匿名包和可看作品的题库入口；结论限定于同题同条件。
- 原题与数据：[One-shot app benchmarks 题源](https://github.com/VSBDev/one-shot-app-benchmarks/tree/1cd72911872cb3d789f7825866e79875130c2de3/prompts)；[评分代码](https://github.com/VSBDev/one-shot-app-benchmarks/blob/1cd72911872cb3d789f7825866e79875130c2de3/harness/README.md)；[项目展示](https://vsbdev.github.io/one-shot-app-benchmarks/)。

样题（摘要）：

- [像素图片编辑器](https://github.com/VSBDev/one-shot-app-benchmarks/blob/1cd72911872cb3d789f7825866e79875130c2de3/prompts/pixel-image-editor-one-shot-prompt.md)（pixel-image-editor-one-shot-prompt）：真实绘制、图层、撤销/重做、导出、窄屏使用与键盘操作，要求操作实际有效。 核对：绘制结果改变、撤销恢复、下载内容正确；不只检查按钮是否存在。
- [轻量室内平面规划工具](https://github.com/VSBDev/one-shot-app-benchmarks/blob/1cd72911872cb3d789f7825866e79875130c2de3/prompts/interior-floor-plan-cad-one-shot-prompt.md)（interior-floor-plan-cad-one-shot-prompt）：绘制房间与墙、门窗、尺寸、对象调整、保存和导出，窄屏也能做核心操作。 核对：几何/面积正确，操作一致且产物可交付。

## 出题与评价怎样接到本项目（建议，不是已实施的新评分卡）

1. 按四类分题：自由设计、小应用流程、已有前端编辑/修复、逐轮演进。已有程序SWE结果继续独立；不拿SWE通过率代替前端体验或个人Harness收益。
2. 每题先冻结核心用户目标、输入/起点、关键操作、明确预期与边界。条件只来自开发者看到的需求；不能生成一套会奖励题外动画、服务或架构的隐藏标准。
3. 功能取证与主观设计判断分开。任务验收记录可用1/0.5/0的预定义条件或二元测试，但原题reward遵循原协议；未测/环境阻断不伪装成作品失败。
4. 页面进入关键状态后采集截图、错误、DOM/URL/业务输出并冻结。确认视觉图片作为裁判输入，保留图像内容hash和视图/状态回执；仅图片路径不够。
5. 校准集应同时含好页、坏页与合理边界：小正文/元数据、截字/合理缩略、无响应/正确反馈、丢状态/正确恢复、必要复杂度/多余抽象。评估误报、漏报和重复稳定性，再决定可信范围。校准不是让用户每次代验。
6. Harness用同模型、同题、同预算对照，看真实纠正、额外操作、回归与资源。多模型多产品混跑只能解释为组合对比。不会把各仓库的总分或权重直接合成一张雷达。

## 需要特别避免的照搬

ArtifactsBench 样题2的原始要求是经验升级和技能树，其第一项清单会奖励动画/音效；这是本轮从题面与清单核对出的扩张，不能加到我们未要求这些内容的题里。Vision2Web 的缺结果/Blocked计0是发布者的全题集计分约定，不能用来消除本项目环境错误与失败的区别。WebGen关键词式结果解析应替换成严格结构与行为核对。引用存在、多个裁判或模型排行一致都不证明每条验收正确。

## 浏览入口与范围

[只读项目与17条样题目录](opensource-benchmark-catalog-20261008.html)。页面展示标准、公式、局限、样题摘要、原题及展示入口；没有运行按钮、假成绩或本地可执行题数。没有导入新题包、改变当前权重、重评旧成绩或改写宿主设置。

FullStack-Agent 的入口仓库也已查看，具体开发框架位于其外链 FullStack-Dev；本轮没有把系统介绍当作已核验的一套新评分实现。FrontendBench 的论文公开说明已找到，但本轮没有确认其独立官方GitHub题包，未把它计作已核对仓库。

## 来源版本与许可

许可仅记录发布者标注，不把仓库公开等同可任意再分发。ArtifactsBench 的LICENSE写CC BY 4.0；SlopCodeBench与One-shot源码MIT；Design2Code代码MIT、数据ODC-By。Vision2Web仓库README写CC-BY-NC-SA-4.0/仅学术，而HF数据卡写Apache-2.0，存在实际标注冲突；接入前须核清，当前只提供摘要和链接。DesignBench、WebGen、Interaction2Code、WebDevJudge本轮未确认统一顶层许可，未再分发题包。

|仓库|核对commit|主要代码|
|---|---|---|
|[zai-org/Vision2Web](https://github.com/zai-org/Vision2Web)|d80a4a3d0ea7326541ad87314294269a633789e4|[原版本代码](https://github.com/zai-org/Vision2Web/blob/d80a4a3d0ea7326541ad87314294269a633789e4/vision2web/evaluation/prompts.py)|
|[mnluzimu/WebGen-Bench](https://github.com/mnluzimu/WebGen-Bench)|c89e0743438e458d617cebaf7a682e0e66e41049|[原版本代码](https://github.com/mnluzimu/WebGen-Bench/blob/c89e0743438e458d617cebaf7a682e0e66e41049/src/ui_test_webgen/compute_acc.py)|
|[Tencent-Hunyuan/ArtifactsBenchmark](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark)|88c968b87e150e63de7660937e6dcfb8e7d643cf|[原版本代码](https://github.com/Tencent-Hunyuan/ArtifactsBenchmark/blob/88c968b87e150e63de7660937e6dcfb8e7d643cf/src/infer_gemini.py)|
|[SprocketLab/slop-code-bench](https://github.com/SprocketLab/slop-code-bench)|31ceea3add480edb33431e70475c4c70597e6b31|[原版本代码](https://github.com/SprocketLab/slop-code-bench/blob/31ceea3add480edb33431e70475c4c70597e6b31/docs/metrics/interpreting-results.md)|
|[lcy2723/WebDevJudge](https://github.com/lcy2723/WebDevJudge)|2d93e5af4e65ddba47704497adacc5d3c1e52b69|[原版本代码](https://github.com/lcy2723/WebDevJudge/blob/2d93e5af4e65ddba47704497adacc5d3c1e52b69/evaluator/rubric.py)|
|[WebPAI/DesignBench](https://github.com/WebPAI/DesignBench)|a1e58d66ecbf1f77848bc5529ee7bbbe33bc25ba|[原版本代码](https://github.com/WebPAI/DesignBench/blob/a1e58d66ecbf1f77848bc5529ee7bbbe33bc25ba/code/evaluator/main.py)|
|[NoviScl/Design2Code](https://github.com/NoviScl/Design2Code)|7a575e4c33f417c4be5c64072b8f5798de0d0f99|[原版本代码](https://github.com/NoviScl/Design2Code/blob/7a575e4c33f417c4be5c64072b8f5798de0d0f99/Design2Code/metrics/README.md)|
|[WebPAI/Interaction2Code](https://github.com/WebPAI/Interaction2Code)|29d8af1572888d33b028ef001dc8452f9e88497b|[原版本代码](https://github.com/WebPAI/Interaction2Code/blob/29d8af1572888d33b028ef001dc8452f9e88497b/code/metric/calculate_metric.py)|
|[VSBDev/one-shot-app-benchmarks](https://github.com/VSBDev/one-shot-app-benchmarks)|1cd72911872cb3d789f7825866e79875130c2de3|[原版本代码](https://github.com/VSBDev/one-shot-app-benchmarks/blob/1cd72911872cb3d789f7825866e79875130c2de3/harness/README.md)|

SlopCodeBench题包：[9cd9ca3a51c3d3e2a99d2488a25baf73a2204451](https://github.com/gabeorlanski/scb-problems/tree/9cd9ca3a51c3d3e2a99d2488a25baf73a2204451)；Vision2Web HF索引：[8f03299d92b9bd852e93852d0c21e8a4848ab661](https://huggingface.co/datasets/zai-org/Vision2Web/tree/8f03299d92b9bd852e93852d0c21e8a4848ab661)。原始公开来源缓存位于忽略的.local/qa/u78，不提交。
