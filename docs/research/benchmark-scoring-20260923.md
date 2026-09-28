# 模型与 Harness 榜单怎样评分

核对日期：2026-09-23。依据发布者论文、方法页与公开代码。用户截图只作来源线索，未据此认可截图中的模型名、价格、分值或排序。不同版本、发布者子集和运行协议不能混用。

## 调研结论

没有一种既不需要任务要求、又能准确评判所有产物的通用评分器。可以通用的是**执行与留证框架**：冻结输入和环境、运行候选方案、独立验收、保存原始输出、统计重复尝试。具体正确性仍须来自测试、答案、专家标准或人的偏好。

有些榜单纯程序判分，有些明确使用 AI；“另派一个 AI”本身并非错误。问题是有没有可审计的量表、证据、裁判配置、重复运行和人类校准。引用存在只能证明模型确实引用了这段材料，不能证明模型解释正确。

编码 Agent 榜单往往已经评测模型＋Harness，不能一概称为裸模型榜。本项目的差异是固定使用 Codex 桌面工作流，比较个人可配置的 AGENTS、Skills、工具和交互层。题库成绩与日常使用感受可能不同，不能据用户体验案例推断某模型普遍优劣。

## 截图八项来源逐一核对

### 1. SWE-Atlas-QnA

仓库问答，考查代码追踪和解释，不是提交修复补丁。公开集含固定仓库版本、问题、参考材料及专家标准；主要指标 Task Resolve Rate 要求一题全部标准通过。AI 裁判逐项判断，不能理解成裁判随意给一个“63 分”。原始包有 124 题、11 个仓库，可查看题目与评分结构。需要保留回答、条目判定、引用、裁判版本和仓库差异；修改受跟踪文件会违反问答任务规则。

借鉴：专家标准→逐条证据→整题结论。不可照搬：用问答解决率衡量前端美观。

来源：[Scale 官方仓库](https://github.com/scaleapi/SWE-Atlas)、[数据集与评分协议](https://huggingface.co/datasets/ScaleAI/SWE-Atlas-QnA/blob/main/README.md)。

### 2. CursorBench 4.0

来自真实开发工作的任务，覆盖修改、调查、重构、意图理解和设计。Cursor 公开介绍自动 Agent 裁判与线上验证，并关注完成质量及效率。但当前可查资料没有公开完整 4.0 私有题包与每题评分器，较早的详细博客不能冒充 4.0 的完整协议。截图百分比无法仅靠该介绍独立复算。

借鉴：真实上下文、简短意图、线上与离线结果交叉验证；不能声称我们已经复现 CursorBench。

来源：[版本入口](https://cursor.com/cursorbench)、[方法背景及其发布时间](https://cursor.com/blog/cursorbench)。

### 3. DeepSWE v1.1

已有仓库上的工程任务，不只修 Bug。AA 的当前协议为 113 题，提交补丁交给独立程序验收器，按单次通过/失败计分；每题三次尝试先平均，再对题目平均，即估计 pass@1，**不是三次挑最好**。执行阶段限制网络。证据应包含提交、固定环境、验收器版本、测试输出和退出状态。

本项目已有按题源码准备及少量 Windows 原测试适配；不是全套上游 Linux 环境，也不能把 AI 质量分冒充 DeepSWE 成绩。

来源：[AA Coding Agent Index v1.5 方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)、[原始题库](https://github.com/datacurve-ai/deep-swe)。

### 4. EEBench

电气工程设计，以构建、电路仿真、隐藏工况和物料成本验证，官方明确不使用人类或 LLM 裁判。分数结合 65% 技术表现和 35% 成本效率，成本奖励以有效工作的电路为前提。波形、设计文件和 BOM 是实证。私有保留题不等于可完整下载复现的题包。它与名称相近的 EEE-Bench 不是同一来源。

借鉴：明确可执行的领域验收、边界工况和成本目标。不能把电路量表直接迁移为通用项目质量分。

来源：[EEBench 原始方法](https://www.eebench.org/methodology.html)。

### 5. AA-Briefcase v1.1

面向多小时办公交付，91 道任务来自四个私有业务场景；另有公开 Lite 场景。交付文件同时接受逐条标准检查、分析质量比较、呈现质量比较。v1.1 用 CrowdBT 汇总，千分制数值是相对排名尺度，不是通过百分比。

AI 参与评分。方法描述不同类型的裁判池；每个条目或比较分配一个裁判，并非所有模型每题投票。查看文件解析内容与图片，要求结论扎根材料。可借鉴匿名成对比较，减少“绝对 85 分”的随意性；本项目尚未实现此算法。

来源：[评测介绍](https://artificialanalysis.ai/evaluations/aa-briefcase)、[详细方法中 AA-Briefcase 段](https://artificialanalysis.ai/methodology/intelligence-benchmarking)、[公开 Lite 示例](https://huggingface.co/datasets/ArtificialAnalysis/AA-Briefcase-Lite)。

### 6. Terminal-Bench 4.0

在终端环境完成任务，由测试套件验收。4.0 更新任务、验收器、算力和时限，长任务允许八小时执行；资源分配与环境本身是比较条件。这里的**被测 Agent 执行预算**与我们给产物审查器的预算是两件事。

借鉴：固定镜像/依赖、程序验收、区分执行失败与环境异常，并版本化资源和判分规则。AA 当前统计为 66 题，每题三次尝试取平均单次成功率。正式协议可能将执行超时计零；我们裁判没完成只表示尚无审查结论，不能混用两个超时含义。

来源：[Terminal-Bench 4.0 发布方法](https://www.tbench.ai/news/terminal-bench-4-0)、[AA 运行协议](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)。

### 7. Harvey Legal Agent Benchmark

给出任务与客户文件，产出法律工作材料，依据专家编写、关联具体文件的原子标准判断。不是只检查关键词，也不是人逐份手工给总分；公开方法使用 AI 对专家标准判定。初始发布描述多模型裁判，AA 等使用者可能另选题目子集及判分协议，不能混为截图唯一来源。

可借鉴文件级凭证、条目可判定性、专业人员标注。开源评测材料不代表可以无条件复算每个第三方榜单；法律量表不适合作为软件通用评分。

来源：[Harvey 方法介绍](https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark)、[初始结果方法](https://www.harvey.ai/blog/legal-agent-benchmark-initial-results)、[公开仓库](https://github.com/harveyai/harvey-labs)。

### 8. HealthBench Professional

医生编写专业场景和加权标准，包含应满足的正项及需惩罚的负项，AI 判断各条是否满足。基础分按满足项权重之和除以正项总权重；发布指标另做长度校正，并检验裁判与专家的一致性。因此表中的百分数不是临床正确率或安全保证。原 HealthBench 的公开代码不能不加说明就当成 Professional 的相同版本。

借鉴：遗漏与错误分别处理、量表和专家复核结合。不能迁移医学标准为前端审美，也不能据此宣称我们的 AI 裁判已校准。

来源：[OpenAI 原始论文](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf)。

截图前两行输入/输出 Token 价格是成本信息，不是第九、第十项能力评测。模型预算、长上下文、缓存和供应商规则可能改变费用，不能反推订阅额度。

## 2026-09-25 补充：其余截图与跨榜单读法

- **Artificial Analysis Intelligence Index v4.3.2**：十项评测按发布者公开的固定权重组成指数。当前列表含 AA-Briefcase、GDPval-AA、AutomationBench-AA、Terminal-Bench 4.0、SciCode、AA-LCR、AA-Omniscience、Humanity's Last Exam、GDP.pdf、CritPt。原始项目单位不同；例如 GDPval-AA 和 AA-Briefcase 的 Elo 经固定范围归一后再纳入指数。截图中的指数 58 并非“58% 软件任务完成率”。具体权重和版本以[官方方法页](https://artificialanalysis.ai/methodology/intelligence-benchmarking)为准。
- **GDPval-AA v2.1**：220 道专业交付任务，产出文件后进行同题盲评，使用 Crowd-BT 汇总成相对 Elo；锚点为 DeepSeek V4.1 Flash (max) 1600。截图中的 1846、1994 这种数不是百分比，也不能与本项目 0–100 项目质量分直接相加。见[评测页](https://artificialanalysis.ai/evaluations/gdpval-aa)与[方法页](https://artificialanalysis.ai/methodology/intelligence-benchmarking)。
- **AutomationBench-AA**：657 道模拟 SaaS 跨应用流程。主指标为每题达成的目标比例，触发约束违规时该题记零；“Tasks Completed”另指全部目标完成且无违规的任务比例。与 Zapier 原榜单的全题完成率口径不同。见[官方评测页](https://artificialanalysis.ai/evaluations/automationbench-aa)。这特别值得借鉴用于项目经理式需求：目标完成率和不可违反的边界同时报告，不能让界面观感掩盖错误写入。
- **Code Arena WebDev**：用户在同题两份实际网页间盲选，成对胜负由 Bradley–Terry 模型估计相对强度；Pareto 图把质量尺度和成本并列展示，不把价格混入质量分。见[Arena 方法介绍](https://arena.ai/blog/webdev-arena)。
- **厂商模型对照表**：每一行引用不同第三方或自有评测（包括 CursorBench、Terminal-Bench、HealthBench、EEBench 等），单位可能是 pass@1、Elo、长度校正得分或费用。表格只是并排展示，并无共同分母；厂商所选子集和执行 Harness 要逐项核对。CursorBench 4.0 完整私有逐题验收器未公开，不能从截图复算它的百分比。见[CursorBench](https://cursor.com/cursorbench)。

本工作台可借鉴“先定义任务和验收、报告覆盖率、固定环境、逐题留证、重复运行、把质量与成本并列”的方法。现有桌面流程不能据此宣称复现任何外部排行榜。项目经理式开放任务应冻结用户目标和必要验收条目：需求达成与实际运行是主轴，健壮性、规则遵守、交互、交付和维护按适用性评价；安全与性能只有任务要求且能实际取证时才计入。缺项不作零分，也不把其余已评分项重标为整题总分。

## 可借鉴的开源 Harness 评测项目

|项目|可复用部分|仍需自己定义|
|---|---|---|
|[Harbor](https://github.com/harbor-framework/harbor)|任务包、环境、Agent 适配、验收输出、轨迹查看|每题验收器与运行条件|
|[SWE-bench](https://github.com/SWE-bench/SWE-bench)|固定仓库补丁评测、目标修复与原功能回归|适用任务及测试环境；不评前端审美|
|[Inspect AI](https://inspect.aisi.org.uk/scoring.html)|程序/模型评分器、多评分、重评分；[评测日志](https://inspect.aisi.org.uk/eval-logs.html)|评分函数、参考答案、错误处理与统计协议|
|[SWE-Atlas](https://github.com/scaleapi/SWE-Atlas)|仓库证据问答、条目标准与裁判|新任务的专家标准|
|[Harvey Labs](https://github.com/harveyai/harvey-labs)|文件产物与专业条目判定|领域内容与专家校准|
|[Stirrup](https://github.com/ArtificialAnalysis/Stirrup)|Agent 执行和工具框架，可研究办公任务运行|它本身不是万能评分器，也不是本项目桌面入口的替代品|

## 本项目采用的两种解释方式

|方向|输入和主要成绩|AI / 人的角色|当前实现边界|
|---|---|---|---|
|基准验证|固定任务、起点、原题验收；程序通过结果独立展示|解释证据、辅助代码质量审查|依据公开题源/已声明检查识别；尚未适配原验收器就明确未接通，不能改用 AI 冒充|
|真实项目交付|产品意图与使用场景，可有多种合理实现；按交付质量量表评价|AI 收集运行/文件证据；人实际操作界面和复核|当前支持 AI 参考评分、逐项人工修正及独立人工评价；Windows 自动浏览器取证未打通|

这与“新建项目 / Bug 修复”是不同维度：已有工程功能开发也可以是基准任务，真实产品项目也可以有程序测试。当前分类是展示主要判分依据的推断，不改变历史冻结政策；更精细的显式评测协议选择留在主架构路线。

人工入口：评测→评分→查看产物与复核。文件与图片取自校验过的回收版本；运行项目时先创建独立 `human-inspections/.../workspace`，查看 README / scripts，打开目录或复制启动说明到 Codex。启动后打开独立本机地址体验，再保存观察与分数。不会自动运行任意项目命令。未实际体验的 UX 项留空。独立人工参考分与程序、AI、既有人工修正分存；缺项显示覆盖率。

统一声明：**分数仅供特定条件下的参考，不代表全面能力或每次真实表现。** 不同题类、裁判、环境与预算不直接横比。AI 会波动，人也有偏好。下一阶段的校准、盲评配对、多次重复和统计区间见主架构，不能把本轮的 UI 和留证能力称为已完成科学校准。

## 2026-09-26 补充：四张新截图的来源、指标与适用范围

用户提供的四张视频截帧是**研究线索**，不是本项目的运行结果，也不承载操作指令。已核对发布方的 [GPT-6 Astra 页面](https://openai.com/index/gpt-6-astra/)、[Claude Fable 5.1 页面](https://www.anthropic.com/claude-fable-and-mythos-5-1)、[Kimi K3 技术博客](https://www.kimi.com/en/blog/kimi-k3)及 [DeepSeek V4.1 Flash 发布记录](https://api-docs.deepseek.com/updates/)。它们把若干不同单位、不同题库、不同工具/思考预算的成绩并排放在模型宣传表中；不能将表格行当作一题内部的打分维度，也不能拿百分数、Elo、Codeforces rating 和 API 价格求平均。页面随版本更新；下表只归纳截至核对日可以从发布方或题库方确认的**测量对象与对本项目的启发**，不复制供应商对照数值。

|截图中出现的题库/指标|测量对象和原始口径（依题库版本）|能借鉴到本项目什么|是否进入普通项目单题总分|
|---|---|---|---|
|DeepSWE v1.1、Terminal-Bench 2.1/3.0/4.0|真实仓库补丁或终端任务；固定任务验收器汇成解决率，DeepSWE 单次原生 reward 为通过/失败；[AA Coding Agent 方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)|独立验证环境、源码/镜像版本、失败与环境异常分开、重复试次|只有该题适用的原测试是证据；原榜单通过率另列，不冒充连续本地质量分|
|Terminal-Bench-Science 0.1|科学研究工作流，交付分析、仿真、证明、代码或数据；任务专属可复现实验验收；[题库方说明](https://www.tbench.ai/news/terminal-bench-science-0-1)|真实长任务、领域专家定义可检验产物、任务预算|仅当题目确属科研工作时适用|
|CursorBench 3.2.0/4.0、ProgramBench、NL2Repo-Bench|软件工程/仓库任务的不同测试集；完整细节和可获取性各异；[CursorBench](https://cursor.com/cursorbench)、[DeepSeek 发布方列表](https://api-docs.deepseek.com/updates/)|混合新功能、修复、重构和仓库理解，不只刷一种 Bug|作为选题类别；无公开逐题验收器时不宣称复现其榜单|
|Code Arena WebDev / WebDev Arena、OSWorld 2.0|真实网页交互的人工成对偏好；桌面跨应用流程的 strict 完成与 partial 进度是两种口径；[Arena 方法](https://arena.ai/blog/webdev-arena)、[OSWorld 2.0 论文](https://arxiv.org/abs/2606.29537)|可运行网页、键盘/视觉取证、同题盲评；长流程要同时给进度和最终完成|仅前端/电脑操作题按相关验收计分；人工偏好与任务绝对分分存|
|AutomationBench / AutomationBench-AA|多应用业务流程的目标完成率，违规约束可令该题记零；AA 另列整题完成率；[AA 方法](https://artificialanalysis.ai/evaluations/automationbench-aa)|模糊业务需求分解成目标和禁止动作；部分目标给分并保留硬约束|项目经理式流程题高度相关，但不能直接套其题库权重|
|GDPval-AA v2.1、AA-Briefcase v1.1、APEX-Agents|专业交付文件、跨周或跨应用工作；GDPval 用同题盲评 Elo，AA-Briefcase 结合逐条标准、分析质量与呈现质量；[GDPval](https://artificialanalysis.ai/evaluations/gdpval-aa)、[AA-Briefcase](https://artificialanalysis.ai/evaluations/aa-briefcase)、[APEX-Agents](https://artificialanalysis.ai/evaluations)|长项目阶段产物、质量与呈现分离、同题成对比较；这是开放项目评分的重要参考|可借方法，不能把相对 Elo 当某一交付的 0–100 绝对分|
|OfficeQA Pro、SpreadsheetBench 2、DECK-Bench (Internal)|前者为文件检索与数值推理，后者为跨表格的生成/调试/可视化；DECK 是厂商内部集合、公开复算方法不足；[OfficeQA 仓库](https://github.com/databricks/officeqa)、[SpreadsheetBench 2](https://spreadsheetbench.github.io/)、[Kimi 说明](https://www.kimi.com/en/blog/kimi-k3)|若未来纳入办公项目，须检查文件可打开、公式与跨表引用正确、视觉交付可用|软件项目不默认计入办公专门指标；内部题库不称可复现|
|SWE-Atlas-QnA、GPQA Diamond、HLE/HLE with tools、Agents' Last Exam|仓库问答、学科知识与复杂推理/工具使用等不同题型；[SWE-Atlas](https://github.com/scaleapi/SWE-Atlas)、[AA 方法](https://artificialanalysis.ai/methodology/intelligence-benchmarking)|多步论证、引用与事实核查、工具条件需同一版本|可以选择为独立能力题，不用知识题正确率代替真实软件交付|
|FrontierMath、MathArena Apex、Codeforces rating、SciCode|数学证明/竞赛/科研代码，单位可能是通过率或 rating；[OpenAI 发布方表](https://openai.com/index/gpt-6-astra/)、[AA 指数方法](https://artificialanalysis.ai/methodology/intelligence-benchmarking)|逻辑、代码推理可作为专项题组；评分需原题答案或可验证程序|不因一项目需要“逻辑”就塞数学竞赛分|
|HealthBench Professional、GeneBench Pro、MedChemBench、LifeSciBench|临床/生命科学/化学专业任务；HealthBench Professional 的发布数值还做长度校正；[原始论文](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf)、[OpenAI 页面](https://openai.com/index/gpt-6-astra/)|提醒专业领域须有专家标准与风险项|本项目普通软件题不适用，不拿医疗分评价人情味|
|MMMU-Pro、CharXiv、MathVision、BabyVision、ZeroBench、Chartography|多模态、图表、视觉或视觉推理；有的区分是否调用 Python/工具或 pass@5；[Kimi 方法说明](https://www.kimi.com/en/blog/kimi-k3)|截图/图表读取、视觉事实核对须记录工具和实际样本|只对题目明确含视觉输入/输出的项目适用|
|CyberGym、SEC-Bench Pro、ExploitGym|网络安全、漏洞查找或利用能力；[DeepSeek 发布方列表](https://api-docs.deepseek.com/updates/)|独立安全题与禁止越权的负面验收|不能把攻击题得分当一般工程安全评分|
|Artificial Analysis Intelligence Index|若干不同评测先各按自身协议求值，再按发布方权重聚合；[指数方法](https://artificialanalysis.ai/methodology/intelligence-benchmarking)|跨题集必须先固定集合、单位、版本、权重和适用条件|不能直接抄其权重或用一个指数声称 Harness 的微小改动有效|

上表未逐项审计所有厂商二次引用的运行条件；尤其 `DECK-Bench (Internal)`、私有 CursorBench 版本和某些供应商自行复跑行不具公开完整验收器。若要导入其中的任务，先核对许可证、题目可获取性、版本、参考解污染风险、执行预算、是否允许 Codex 桌面运行；这些检查通过前仅当选题线索。截图中的模型名和分数不写入产品成绩。

### 从榜单名称提炼成真正可操作的测量指标

|专业指标/单位|发布方常见做法与依据|本项目采用或保留的位置|人工能否调整|
|---|---|---|---|
|整题解决率、pass@1（%）|DeepSWE、Terminal-Bench等以整题验收器给单次0/1，再跨题和重复汇总；[AA方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)|原题 reward、同协议题级解决率；不把0/1改写成连续质量分|不能改原始结果；可对验收器申诉/复跑|
|目标测试与旧功能回归（通过数/总数）|F2P/P2P各反映不同目标，数量本身不是语义权重；[DeepSWE方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)|每题证据和故障定位，映射预先声明的语义目标|不能滑条改命令输出；可指出测试未覆盖或误判|
|部分目标完成（%）与整题完成（%）|AutomationBench-AA区分目标进度与Tasks Completed，OSWorld 2.0区分partial与strict；[AA](https://artificialanalysis.ai/evaluations/automationbench-aa)、[OSWorld论文](https://arxiv.org/abs/2606.29537)|开放业务需求按目标贡献给连续分，必要项另列|目标解释/体验可复核，硬约束结果不可直接改|
|约束违规/越权（次数、是否触发）|业务与电脑操作任务可能有禁令/guardrail；[AA AutomationBench](https://artificialanalysis.ai/evaluations/automationbench-aa)|项目约束、范围控制、未经授权操作；不与礼貌口吻混为一栏|人工判断是否真正违规；原始轨迹只读|
|质量量表（逐项锚点分）|AA-Briefcase等检查产物的分析与呈现质量；[AA-Briefcase](https://artificialanalysis.ai/evaluations/aa-briefcase)|需求、工程、维护、界面、交付按题适用，需证据和评分卡版本|允许有理由的主观复核，保留原分|
|成对偏好、Elo/胜率|WebDev Arena与GDPval在同题候选间比较；[Arena](https://arena.ai/blog/webdev-arena)、[GDPval-AA](https://artificialanalysis.ai/evaluations/gdpval-aa)|用于微差盲评的辅助比较，不是单题绝对0–100|评审者投票不可回写程序成绩；分歧要显示|
|浏览器功能与视觉体验|WebDev/OSWorld需要实际界面或电脑操作；[Arena](https://arena.ai/blog/webdev-arena)、[OSWorld](https://arxiv.org/abs/2606.29537)|网页任务看主路径、窄屏、键盘、视觉、可访问性；无网页题不适用|实际体验与视觉可调整；截图/操作回执只读|
|长时任务连续性|科学/专业任务跨步骤、跨工具与多次修订；[Terminal-Bench Science](https://www.tbench.ai/news/terminal-bench-science-0-1)、[AA-Briefcase](https://artificialanalysis.ai/evaluations/aa-briefcase)|里程碑、要求变更、返工与最终回归；仍按一个项目一题|主观交接质量可复核，版本和时间戳不可改|
|稳定性/可靠性（有效重复、失败率、分布）|Coding Agent Index报告任务级尝试与reliability；[AA方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)|配置层按相同题目/条件展示重复分布和失败，中断与环境故障另列|不能凭感觉改次数；可复核故障归因|
|成本、Token、完成时间（不同单位）|AA同时报告token、cost、execution time；厂商曲线还展示质量—成本取舍；[AA方法](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)|结果主卡单列被测用量和时长、价格假设与裁判开销；默认不进入质量分|原生日志只读；人可标注等待和计费解释，不能造账单|
|知识、逻辑、视觉、安全专项成绩|GPQA、HLE、FrontierMath、MMMU、CyberGym等测不同域；[OpenAI](https://openai.com/index/gpt-6-astra/)、[Kimi](https://www.kimi.com/en/blog/kimi-k3)、[DeepSeek](https://api-docs.deepseek.com/updates/)|需要时形成单独的专项题或题内可检验目标，不当作所有工程题的固定维度|按各专项协议；专家意见与程序结果分存|

该表的“采用位置”是 U46 **待审设计**。测量单位不能因为都写成百分数而直接相加；能否人工复核取决于证据性质，而非哪个厂商使用了 AI 裁判。默认只展示少量当前题适用的指标，全部指标库留在方法页查询。

### 可迁移的方法，不可迁移的数字

1. **目标进度与整题完成分列**：AutomationBench-AA 的部分目标进度、OSWorld 2.0 的 partial/strict 说明二元完成指标不是唯一信号；但部分进度要按预先声明的用户目标和重要性计，而不是把大量回归用例当目标。[AutomationBench-AA](https://artificialanalysis.ai/evaluations/automationbench-aa)、[OSWorld 2.0](https://arxiv.org/abs/2606.29537)。
2. **交付质量和相对偏好并列**：GDPval-AA、AA-Briefcase、WebDev Arena 会对实际交付或可用页面作比较；同题盲评可帮助发现小差异，但 Elo/胜率是相对统计量，不能直接塞进一个任务的绝对百分分。[GDPval-AA](https://artificialanalysis.ai/evaluations/gdpval-aa)、[AA-Briefcase](https://artificialanalysis.ai/evaluations/aa-briefcase)、[WebDev Arena](https://arena.ai/blog/webdev-arena)。
3. **成本和时间同屏，默认不兑换质量分**：厂商曲线用质量—成本 Pareto 关系说明“更便宜但未完成”不能当更好；本项目要展示被测执行 Token、活动/总时长和有条件的 API 等值估算，复审开销另列。实际订阅扣额未知时不可标“实际花费”。
4. **低预算不等于零重复**：固定少量锚题、同题配对、分批扩展、记录所有失败与中断。小差异在有限样本里可能无法判断，UI 应显示原始每题差值与不确定性，而不是多保留一位小数假装精确。长期项目可保留少数深入案例，不假装五个阶段是五个独立样本。

本研究表不直接决定本站新的单题/配置总分公式。目标合同、人工调整边界和实施状态分别由 [评分合同](../architecture/EVALUATION.md)、[主架构第8节](../PROJECT_SPEC.md#8-唯一实施路线与完成标准)和 [当前交接](../当前交接.md)维护。2026-09-26 新评分方案仍待用户审查；研究结论本身不构成执行授权。
