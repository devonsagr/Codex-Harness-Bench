# 公开题库、运行环境与评分方法

## 当前结论 · 2026-09-21（U27）

本项目固定正式执行入口为Codex桌面，研究模型与个人可配置Harness的交付表现。编码榜单通常也使用指定Agent/Harness，不能把所有榜单都描述成“裸模型分数”。Gemini仅提供前端起点，不决定本项目题库、评分或功能范围。下列是公开源码研究，不是本项目运行成绩；后附早期调研保留为历史依据，产品决策以主架构为准。

### DRadar：准备、执行与判分是不同环节

核对用户附件指定的公开客户端版本 `39e7567dc4e76db12748bb17a0ea9b12d6c68294`，而非执行附件命令。来源：[README](https://github.com/codex-radar/dradar/blob/39e7567dc4e76db12748bb17a0ea9b12d6c68294/README.md)、[runner.py](https://github.com/codex-radar/dradar/blob/39e7567dc4e76db12748bb17a0ea9b12d6c68294/src/dradar/runner.py)。

1. 用户贴的说明是启动协议：网页保存运行范围，短期运行码关联本次计划；CLI处理版本、环境、执行、上传与恢复。它不是具体题面，也不是评分标准。运行码和私人计划不进入项目文档或Git。
2. 客户端准备任务仓库，按服务端指定版本建立托管快照，再经Pier/Docker启动Agent。该版本默认任务仓库指向 `SecurityMind/deep-swe`，与下面索引的官方 `datacurve-ai/deep-swe` 需区分；不能声称二者每道题和分数完全一致。
3. runner实际传入 `--disable-verification`，客户端负责Agent执行和采集补丁/轨迹等产物；README明确服务端使用题目自带verifier重新运行补丁并独立判分，评分与排行榜由服务端处理。不能从客户端推断服务端用了某个AI裁判、全部权重或所有判分规则。
4. `doctor` 不是纯静态说明：其流程涉及运行工具、依赖、任务仓库及环境探测。用户明确“只看、不跑”，因此本轮没有执行安装、doctor、登录、领题、恢复或模型任务，也没有访问认证文件。

可复用的设计是固定题包版本、预检、开发输入与隐藏验收分离、保存实际补丁和可恢复进度；正式执行仍保留桌面，不能把CLI结果写成桌面成绩。

### DeepSWE：源码、依赖、隐藏测试都有独立落点

官方仓库 [datacurve-ai/deep-swe](https://github.com/datacurve-ai/deep-swe/tree/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea)，本次固定版本 `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`。逐项读取113份task.toml，提取任务名、语言、目标仓库、base commit与原文件链接，保存在 `catalog/public-task-sources.json`。这是来源索引，尚未转为本项目可执行题包。

以 `aiomonitor-task-snapshots-diff` 为例：

|材料|作用|
|---|---|
|[task.toml](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/tasks/aiomonitor-task-snapshots-diff/task.toml)|声明目标aiomonitor仓库、base commit `b73fea2e0682803bda7531c93cd1dfb360839175`、独立验收与补丁收集|
|[environment/Dockerfile](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/tasks/aiomonitor-task-snapshots-diff/environment/Dockerfile)|安装系统和Python依赖，准备固定源码起点；测试与参考解不混入开发环境|
|[tests/test.sh](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/tasks/aiomonitor-task-snapshots-diff/tests/test.sh)|应用候选补丁和验收测试，执行pytest，生成JUnit结果并调用grader|
|[tests/grader.py](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/tasks/aiomonitor-task-snapshots-diff/tests/grader.py)|按固定测试集合计算reward和诊断指标|

这个样例的reward为1，要求存在F2P用例、全部F2P通过且全部P2P通过。F2P检查应修复/新增的行为，P2P检查原功能不回归；还保存两类通过比例和partial比例，缺失指定用例不能当通过。整题解决率可以汇总成连续的百分比，但不能由此推断界面美观或全部工程质量。此样例用程序测试判分，不需要另一个模型印象打分；不能据此声称DRadar私有服务端完整实现相同。

任务定义采用Apache-2.0，目标工程保留各自许可；索引附上游许可证与修改说明。上游[PROVENANCE](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/PROVENANCE.md)需在后续分发目标工程时继续核对。未下载113套目标工程、镜像或参考解，未运行样题。

### 其他方案与通用性的边界

|一手来源|可以通用的部分|仍需逐题明确的部分|
|---|---|---|
|[SWE-bench](https://www.swebench.com/SWE-bench/api/harness/)|固定源码/补丁/隔离验收及结果汇总|Issue、测试集合与安装环境|
|[Harbor](https://github.com/harbor-framework/harbor/tree/main/docs/content/docs/tasks)|instruction、environment、tests的任务格式与调度|任务环境和verifier|
|[DesignBench](https://github.com/WebPAI/DesignBench)|前端生成、编辑、修复的专项执行与评价方法|页面要求、参照和对应任务；尚未导入，许可和条件仍须逐项核对|
|[Agent-as-a-Judge](https://github.com/metauto-ai/agent-as-a-judge)|让独立裁判主动读工程和调用工具取证|具体需求、评分量表与正确性校准|
|[Inspect scorers](https://inspect.aisi.org.uk/scorers.html)|程序/模型评分器的统一接口和日志|具体正确答案、判定准则或模型评分模板|

**本项目采用的分工：**固定工程题保留原生验收指标；开放需求复用工具取证与机器量表，人工处理分歧。共同基础设施可以通用，成功定义不可能与题目无关。已有隐藏测试不交给开发任务；裁判补写的测试标注来源，不能冒充原题验收器。视觉与交互需要浏览器操作/截图等证据，单读源码不等于已验证。

Docker是这些题包实现环境复现的常见方式，不是评测定义本身。改用本机必须明确依赖、OS与差异，重新验证后标注适配版本；不能删掉Docker要求就声称复现了原榜单。

## 历史调研记录

### 2026-09-12 底座选择

查阅日期：2026-09-12。结论来自官方文档、GitHub README、API 元数据和 Harbor 本地安装源码；“支持”与本项目运行验收分开。此前原文明确未联网，本文件补上实际调查。

## 最接近的项目

|项目与一手来源|查阅版本 / 许可|与本项目的关系和缺口|
|---|---|---|
|[Harbor](https://github.com/harbor-framework/harbor)、[agent 文档](https://www.harborframework.com/docs/agents)|本机安装 0.23.0；源码 main `d8cfe6b6fd463fc1f2a84abf8f1406f46e70c621`；Apache-2.0|Codex adapter 有原生配置、skills、认证文件注入、轨迹和 resume；单独验收环境与网络控制可复用。采用其执行层；项目补全局指令装载、配置快照与对比报告。|
|[SkillsBench](https://github.com/benchflow-ai/skillsbench)|`9a1f4dd5f7659f75707435da3ce854b6e48321d1`；Apache-2.0|直接研究 skills 对任务表现的影响，提供任务和确定性验收。适合作为方法和未来题源；本项目强调个人 Codex 配置历史、恢复及工程迭代。未复制数据集。|
|[SunChJ/skillbench](https://github.com/SunChJ/skillbench)|`d05557e1370704fda56aebf587bd7ca51cc8571f`；未发现仓库声明许可证|高度接近：冻结 Codex skill、隔离会话、保存轨迹/产物/验收/用量、本地文件。要求 POSIX shell 和 Rust；README 将验收命令放工作区，独立验收边界仍需审查。参考产品设计，不复制未明确授权源码。|
|[helloJamest/SkillBench](https://github.com/helloJamest/SkillBench)|`c6ab19aaf7fd1623b987f590707ae6aee0f2a82b`；MIT|提供 Codex skill 评测、judge/full-agent 路径、报告和自动改进。覆盖面较大；不将其主观评审流程作为本项目交付正确性的唯一依据。|
|[eth-sri/agentbench](https://github.com/eth-sri/agentbench)|`da299c4c6b14a9abad2ceef8c751f6c45c543656`；MIT|与仓库上下文/AGENTS.md 有关的研究实现，适合调查指令影响的实验方法。未在本机执行。|
|[SWE-bench](https://github.com/SWE-bench/SWE-bench)|main 文档；MIT（工具）|真实修复题和 Docker 验收基础。公开 Lite 子集为后续接入项，先逐题验证与记录许可证，不能把自选子集冒充官方全量分数。|
|[Terminal-Bench](https://www.tbench.ai/)、[论文](https://arxiv.org/abs/2601.11868)|官方 2.0 资料|终端任务与独立验收设计可借鉴，Harbor 为其评测底座。不是本项目首轮小题，也不直接替代配置历史管理。|
|[Inspect AI](https://inspect.aisi.org.uk/)、[源码](https://github.com/UKGovernmentBEIS/inspect_ai)|官方文档 / main；MIT|通用 task/solver/scorer 与日志工具。首版不同时引入第二个编排框架；没有完成其 Codex 实测。|
|[Stet 方法](https://www.stet.sh/methodology)|2026-09-12 网页；未核实开源许可|明确支持真实仓库回放和配置/指令变化的比较，证明该需求已有产品重叠。未据此声称提供可直接复用的开源 runner。|

上述活跃度只核对 GitHub archived=false 与最近推送，不能据此推断成熟度。SkillsBench/SunChJ/helloJamest 名称相近，不能混为同一项目。

## 未确认项

- SWE-Skills-Bench 论文搜索结果提到 `GeniusHTX/SWE-Skills-Bench`，本次 GitHub API 返回 404。仅作为待核实线索，不给出虚假的 commit 或许可，也不采用为依赖。
- [众测雷达](https://deng.codexradar.com/)已打开查看。其视觉任务不能当作软件工程题；本项目不宣称使用“同款 DeepSWE 题库”。
- 没有穷尽所有 GitHub 项目，不能宣称市场空白。

## 为什么选 Harbor

安装的 0.23.0 源码可确认：`Codex._load_base_config` 读原生配置，`_build_effective_config` 合并运行输入，`_upload_effective_config` 上传配置；`_resolve_auth_json_path` 允许显式注入认证文件；`_build_register_skills_command` 向独立 HOME 注册 skills；Trial 的 artifact handler 支持将完整候选目录送入 separate verifier。

固定执行依赖一个框架，可直接继承容器回收、超时、日志、异常和验收。新增 adapter 只做 profile 装载与证据，不拷贝上游 1,400 多行 Codex 实现。

本机 Linux Docker 引擎初始未运行，已通过 Docker Desktop 启动。Harbor 安装在项目 `.venv`，不替换全局 Codex。后续实测结果只写入 [当前交接](../当前交接.md)，不在调研表提前宣称通过。

## 头脑风暴结论

最清晰的产品入口是“比较我改前和改后的配置”。首页优先展示变化项、是否生效、验收证据和全部失败；配置收藏/恢复比早期总榜更实用。

长远可以建立两条分开的题库：公开维护题负责可比性，公开多轮替换题负责用户最关心的遗留清理。新增严肃能力之前先做好可信的实验记录；不要以一个单题冠军驱动配置推荐。

## 2026-09-17：桌面配置与 Harness 评测补充

本轮读取项目原始README/官方说明，不把搜索排名、示例成绩或仓库名称当验证依据。

|项目/原始来源|可以借鉴|不能直接照搬|
|---|---|---|
|[SWE-bench](https://github.com/SWE-bench/SWE-bench)|修复结果由可执行测试核对，保存版本/补丁|修Bug成功率不能覆盖从零构建与桌面协作|
|[Terminal-Bench](https://github.com/laude-institute/terminal-bench)|真实任务、环境与产物验收|终端执行底座和桌面底座不是同一条件|
|[τ-bench](https://github.com/sierra-research/tau-bench)|重复试验可靠性pass^k；原库已提示新任务转tau2-bench|不将一次成功或多轮对话算重复可靠性|
|[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai)|任务和评分器分开，可按任务组织评价|框架没有替本项目证明统一人工维度/权重|
|[OSWorld](https://github.com/xlang-ai/OSWorld)|真实桌面环境的任务结果与执行式评价|它测试操作电脑的Agent，不能直接当Codex桌面个人配置排行|
|[TheLime1/harness-bench](https://github.com/TheLime1/harness-bench)|固定模型条件，记录配置、时间/Token/费用、人工IDE协议和证据等级|README自称early v1，种子含fixtures与公开参考，不当已完成实测排行榜|

结论是本项目的设计取舍：同时呈现结果、质量、过程、效率、可靠性，分清证据来源；采用可编辑人工量表，保留具体任务脚本。桌面版本、模型、题目/起点、预算、宿主工具状态和介入协议影响可比性。当前未找到可以不经适配就覆盖“Codex桌面固有Harness + 个人配置”的现成统一标准；不声称市场完全不存在类似项目。

[Superpowers](https://github.com/obra/superpowers#codex-app)当前说明通过Codex插件市场安装，插件不等同于Skills目录；应记录插件可用性与启用状态，不能用复制技能代替完整安装。

## 2026-09-19：通用机器评分（U20）

用户要求机器先给分，人工只修正；不能要求每题手写专用脚本。下列一手资料已查阅，参考方法和本项目实际接入分开。

|开源项目与评分资料|评分方式|本项目采用或保留的边界|
|---|---|---|
|[Harbor Rewardkit](https://docs.harborframework.com/core-concepts/rewardkit/judge-criteria)、[内置准则](https://docs.harborframework.com/core-concepts/rewardkit/built-in-criteria)|程序、模型和Agent准则组合，按要求评估产物|复用既有Harbor执行层，让裁判读取/运行副本；本轮未安装独立Rewardkit或宣称已经接入其全部准则|
|[Promptfoo agent-rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/agent-rubric/)|有工具的裁判按照量表检查实际结果|借鉴主动取证，避免只读交付说明；不另引入第二套Agent runner|
|[Agent-as-a-Judge](https://github.com/metauto-ai/agent-as-a-judge)|围绕需求使用工具检查工程与证据|用冻结需求作为裁判输入；通用工具流程仍需要具体任务的成功定义|
|[Inspect AI](https://inspect.aisi.org.uk/model-graded.html)|模型评分器、模板与可追溯记录|保留裁判模型/版本、量表和引用，不能把框架支持等同评分已校准|
|[DeepEval Task Completion](https://deepeval.com/docs/metrics-task-completion)|根据任务、工具调用与结果判断完成情况|借鉴结果和轨迹联合评价；缺失轨迹不编造过程分|
|[SWE-bench harness](https://www.swebench.com/SWE-bench/api/harness/)、[Terminal-Bench](https://www.tbench.ai/news/announcement)|明确环境和可执行任务验证器|适合严肃回归和固定题榜单，但新业务项目通常仍需专门测试或Agent补充验证|

**可泛化的是评分流程，不是所有任务共用一个成功断言。** 通用流程为冻结题面/要求 → 自动运行已有构建与测试 → 独立裁判探索产物并尝试实际操作 → 每个量表项返回分数、方法、理由和可核对引用 → 人工按项修正。没有专用脚本也能调用该流程；强业务约束仍应逐步增加可靠验证器。

机器分不是客观真值。裁判可能偏好自身风格、受材料中的提示影响或执行不足；[LLM-as-a-Judge研究](https://arxiv.org/abs/2306.05685)讨论偏差，[Terminal-Bench榜单完整性说明](https://www.tbench.ai/news/leaderboard-integrity-update)说明验证器本身也需要审计。本项目校验引用真实存在，但未证明结论正确；未知项为空，保留机器覆盖率、原分和人工修正记录。

当前实现采用arena-machine-v1，具体协议见[评分合同](../architecture/EVALUATION.md)。默认需求50、健壮性20、交互15、交付10、维护5是可编辑的产品起点，不是行业公认权重。新需求自动生成结构化量表、校准集、多裁判一致性仍未实现；真实机器裁判镜像与项目运行验证受本机Docker启动失败阻塞，不能以单元测试替代真实验收。

## 2026-09-20：运行环境与前端评分补查（U22）

|一手资料|能复用的方式|不能据此宣称|
|---|---|---|
|[SWE-bench evaluation](https://www.swebench.com/SWE-bench/guides/evaluation/)|固定仓库/版本/测试环境，以可执行测试确认修复|程序通过率不是视觉或开放需求的统一质量分|
|[Inspect scorers](https://inspect.aisi.org.uk/scorers.html)|确定性与模型评分器组合，支持不同评分类型和记录|框架不能消除逐题成功标准差异|
|[DesignBench](https://github.com/WebPAI/DesignBench)|覆盖前端生成、编辑和修复，结合可运行工程与视觉评估|尚未作为本项目依赖接入，不能冒充已完成其基准|
|[WebArena Verified](https://github.com/ServiceNow/webarena-verified)|基于轨迹/状态验证网页任务结果|任务成功不等于审美优秀|

推导出的实现选择：程序提供执行事实，独立AI针对原始需求主动操作产物并按量表连续打分，人类修正争议。交互验证结合页面状态、键盘/点击、控制台；视觉判断需要截图，而非读取源码后猜分。通用的是工具和取证流程，业务含义仍由每题需求决定。固定题榜单常采用Docker提高可复现性；Docker不是模型评分的理论必要条件。U22本机裁判使用原生沙箱，代价是环境差异更大，暂不纳入严格比较。最新实跑与失败记录见当前交接，不沿用U20的Docker阻塞作为所有评分的前提。
