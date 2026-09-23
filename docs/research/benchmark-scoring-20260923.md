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
