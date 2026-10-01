# 数据、接口、版本与恢复合同

负责 D15-05/14/17/20；主要工作包 B01/B02/B05/B06。先列现有协议，再列扩展提案，避免把未来接口写成现在就能调用。

## 1. 数据权威与分层

业务事实来自本机 SQLite 与冻结文件。React localStorage 只保存外观偏好。App 调 API 取得状态，成功写入后重新读取；服务断开不能回退随机数据。

现有链路：`App/Runner/Editors/Records → workbench/api.ts → webapp.py → arena/api.py → service/contracts/task_import/jobs/scoring/telemetry/files → Database/本地文件`。

继续开发时按能力分离校验与序列化，避免把项目契约、评分和生命周期继续全部塞进 service.py；仍保持单进程本机应用，不为拆模块引入微服务或新调度平台。

## 2. 现有数据库

|表|键|字段/作用|
|---|---|---|
|records|(kind,id)|revision、body(JSON)、archived；当前记录|
|revisions|(kind,id,revision)|body(JSON)、created；历次版本|

kind 包括 config、task、skill、baseline、run，以及题包导入幂等回执 task_import。Trial/Capture/Review/事件目前嵌在 Run JSON 中，并非各有独立 SQL 表。写入使用 SQLite 事务、BEGIN IMMEDIATE 和预期 revision；启用 WAL。不能在文档画出不存在的独立关系表后宣称已实现。

文件系统与数据库不是一个原子事务；当前先创建部分目录再保存记录，准备中途失败可能留下未登记目录。B05 要补可恢复的准备回执或临时目录提交策略，不能通过全局清理解决。

## 3. 现有实体字段

|实体|主要字段|不可变关系|
|---|---|---|
|Config|id/revision/name/agentsPrompt/baseModel/reasoning/interactiveMode/skills/customConstraints|Run 内保存选定版本完整正文|
|Task|id/revision/schemaVersion/title/taskParadigm/channel/difficulty/inputPrompt/projectSpec/fullstackScope/criteria/stages/checks/baselineId/hasFrontendUI/来源|版本2字段校验；Run 内保存完整转换结果和promptSnapshots/sourceSchemaVersion|
|Skill/Baseline|id/name/sourcePath/manifest/createdAt|manifest 对应本地冻结文件|
|Run|id/revision/requestId/requestFingerprint/configs/tasks/policy/hostFingerprint/executionMode/trials/events/notes|创建冻结输入；随后仅追加过程和版本|
|Trial|id/configId/taskId/state/stageIndex/workspacePath/baseline/captures/reviews/sessionId/usage/observations|每一配置×题目独立目录|
|Capture|id/stageIndex/at/manifest/facts/response/checks/checksConfigured/harnessUnchanged/hostUnchanged|文件不可改写；检查尝试保留并可重跑|
|CheckResult|id/label/weight/argv/imageId/status/exitCode/seconds/output|绑定 Capture；旧尝试在 checkAttempts 留存|
|Human Review|id/kind=human/captureId/at/scores/notes/readiness/constraints/criteria/constraintNotes/revisionReason/contractVersion|追加新版本，不覆盖 AI 或检查|
|AI Review|id/kind=ai/captureId/at/summary/findings/执行元数据；机器方案另有scoreSchema/ratings/criteria/commands/evidenceKey|按策略区分机器分与旧辅助意见，绑定回收哈希及模型|
|MachineCorrection|id/at/captureId/reviewId/evidenceKey/changes|逐项score和reason；null撤回，追加历史|
|Usage/TraceReceipt|sessionId/各累计Token/时间/models/reasoningLevels/errors，及原文hash和导入时间|同会话累计不回退，完整原文仅本地|

当前新方案为 `arena-machine-v1`，兼容旧 `arena-review-v1/v2`；历史算法不自动迁移。Run 的 state 由所有 Trial 是否 completed 派生；Trial 的 completed 不是 accepted=true。

## 4. 文件布局和恢复含义

```text
.local/arena/
  arena.sqlite3
  skills/<skill-id>/files/
  baselines/<baseline-id>/files/
  runs/<run-id>/<trial-id>/
    workspace/                       # 唯一交给桌面修改的候选目录
    baseline/                        # 起点 + 本次实际规则/技能
    captures/<capture-id>/files/      # 回收证据
    traces/<trace-id>.jsonl           # 私有原始日志
    reviews/job-.../                  # 本机/Harbor 审查材料与产物
```

恢复归档只改可见性；恢复历史配置创建新配置；计划中的“按历史条件新建评测”创建新 Run/Trial。三者均不直接覆盖原工作区。当前没有 ZIP 导入恢复协议，导出 ZIP 也不是已经实现的可移植全量备份。

现有 ZIP 包含 record.json、baseline 与 captures 文件；不含原生完整日志/认证。它含私有规则与候选产物；用户本地下载，不自动上传。需要完整机器备份时应在服务停止后保存整个 `.local/arena/`，并保留已有版本信息；这是本地文件备份操作，不是应用内导入功能。

## 5. 现有 HTTP 约定

- 同源入口 `http://127.0.0.1:8765`，仅监听回环地址；校验 Host。
- `/api/` 读取要求 X-CHB-Token；写入再要求匹配 Origin。首页 meta 注入随机令牌，不提供任意来源 CORS。
- JSON 写入通常限制1 MB；trace 路由 HTTP 限制20 MB，原文限制15 MB。Content-Type 为 application/json。
- 成功通常返回实体对象或操作结果，前端随后刷新 state；错误对象为 `{ "error": "说明" }`。现有错误主要是中文消息，没有稳定业务错误码，B05 要补可操作的分类。
- 后台 check/judge 先返回含运行状态的 Run；App 在有后台操作或待启动/执行中的桌面试次时约1.8秒轮询 state；服务端原生日志发现节流5秒。当前不是事件流，也没有独立分页任务列表。

### 读取路由（前缀 /api/arena）

|方法与路径|返回/用途|
|---|---|
|GET /state|活动/归档配置、题目、Run、导入清单、模型来源、默认策略、维度及旧 CLI 数量|
|GET /runs/{rid}|完整 Run 展示对象，分数按证据派生|
|GET /runs/{rid}/export|ZIP，先核对证据哈希|
|GET /runs/{rid}/trials/{tid}/files/{captureId}/{relativePath}|仅该快照清单内文件，受大小和路径限制|

### 管理与准备路由

|POST 路径|请求关键内容|结果|
|---|---|---|
|/configs/save|新配置字段；编辑带 id/revision|新 revision 的 Config|
|/configs/import-current|可选 name|仅规则/模型/推理档位的副本|
|/skills/import|path、可选 name|旧单目录入口，保留兼容|
|/skills/scan|scope: global/project/custom，后两者带 path|sources、candidates、15分钟 scanId；只读扫描|
|/skills/import-selected|scanId、candidateIds（1–30）|imported；核对扫描时哈希，整批事务写入，失败撤回本批文件|
|/configs/import-preview|scope: global/project，project 带 path|规则/模型/档位及 importSource；不存数据库|
|/configs/import-source|同预览，可带 expectedFiles|来源未变时创建 Config 副本|
|/baselines/import|path、可选 name|冻结 Baseline|
|/baselines/import-github|url、commit（完整40位SHA）、可选name|显式下载公开源码，返回含sourceUrl/sourceCommit/dependenciesReady=false的Baseline；不安装依赖|
|/tasks/save|题目字段；编辑带 id/revision|新 revision 的 Task|
|/tasks/import-originals|空对象|imported 数组；重复导入跳过已存在 ID|
|/tasks/import-preview|document：题目对象/数组/版本题包|valid/tasks/errors/warnings/fingerprint；不写入数据库|
|/tasks/import|document、fingerprint、requestId|receipt和imported；整个包与回执同一事务创建|
|/{configs\|tasks\|runs}/{id}/archive|revision、archived 布尔值|归档/恢复后的实体|
|/runs/prepare|requestId、configIds(1–2)、taskIds(1–10)、policy、notes、deliveryMode（默认single-delivery）、可选configOverrides|冻结后的 Run；相同请求内容可幂等返回|
|/runs/{rid}/restore-config|configId|历史配置的新副本|

相同 requestId 携带不同内容会拒绝；网络返回不确定时前端复用原 ID。正常“再测一次”必须用新 requestId。

### Trial 动作（POST /runs/{rid}/trials/{tid}/{action}）

|action|请求体|作用|
|---|---|---|
|open|{}|请求打开桌面目录，不发送提示词|
|start|settingsConfirmed:true|记录用户已核对并开始该轮|
|capture|可选 response|封存新 Capture|
|continue|{}|已回收后进入下一预定阶段，仍等待开始|
|complete|{}|机器策略任意回收后记录整题交付；旧v1/v2仍需最终阶段|
|interrupt|reason|外部中断记录，不停止桌面|
|trace|raw(JSONL 字符串)|归属校验后保存原文和累计用量|
|review|captureId、scores、notes、readiness、constraints；v2加criteria、constraintNotes、revisionReason|只接受最新回收；条目集合必须完整，修订已有复审须原因；始终新建版本|
|objective-review|captureId、evidenceKey、score(0–100或null撤回)、reason、evidence|最新回收且完整客观原分；拒绝后台运行和过期证据；追加人工裁定，不覆盖原分|
|check|captureId|异步运行该快照适用检查；可选历史阶段快照|
|judge|captureId、model、usageAcknowledged=true、可选environment: local/docker|每次显式确认使用当前 CLI 登录账号额度；缺少确认直接拒绝且不建作业。旧API省略环境仍为docker，界面题默认 Docker|
|stop|{}|返回 stopping:true / desktopStopped:false|

动作状态前提见 [执行合同](EXECUTION_AND_EVIDENCE.md)。接口列表不是统一保证所有动作在所有状态可调用。

## 6. 新契约已实现协议与剩余扩展

版本2的实际字段合同如下（与源类型/校验同步）：

```json
{
  "schemaVersion": 2,
  "projectSpec": {
    "userStories": ["新增任务"], "apiEndpoints": ["POST /tasks"],
    "dataModel": ["Task: id, title"], "acceptanceCriteria": ["刷新恢复"],
    "techStack": "SQLite"
  },
  "criteria": [{"id": "persist", "label": "刷新恢复", "description": "新增后刷新",
    "required": true, "dimension": "robustness", "source": "user-authored"}],
  "checks": [{"id": "check-persist", "label": "持久化", "image": "my-verifier:v1",
    "argv": ["python", "/tests/verify.py", "/app"], "weight": 1, "timeout": 120,
    "kind": "functional", "criterionIds": ["persist"], "stageIndex": 0, "runOnFinal": true}]
}
```

这只是字段示例，不存在名为my-verifier的已准备镜像。完整无脚本题包见任务合同链接。

- `projectSpec`每组最多80项、每项最多8000字符；criteria最多200项，id唯一且符合记录编号规则，dimension来自四维量表。旧rubric正文保留，legacyPoints不直接计分。
- `stages`仍为1–20项，新增稳定id；checks最多30项，id保存后不重排，kind为functional/build/rule/other，criterionIds须引用本题条目。stageIndex从0开始；省略在最终阶段；runOnFinal为布尔值。
- 新Run冻结`tasks[].promptSnapshots[]`的stageId/text/sha256和sourceSchemaVersion。`Trial.currentStage`额外返回executionPrompt/promptSha256/promptSource，前端直接复制服务端文本。旧Run返回legacy-text-only，不补写未采集的契约。
- GET state中旧题返回`contractUpgradePending=true`的兼容视图；无数据库写入。保存才升级题目revision，或准备新Run时只冻结新运行副本。
- review的`criteria`为`{条目ID:{status,notes,filePath?,checkId?}}`。非unverified需notes；引用文件必须属于当前manifest，引用检查必须已经在该capture执行。服务补入fileSha256和checkEvidence（执行元数据+outputSha256）。任何客户端自称的hash/检查证据都不信任。
- `constraintNotes`为个人约束ID到文本，已裁定的激活约束需依据；同一capture第二次起的人工复审需revisionReason。旧Run保持旧评分输入合同。
- `score.acceptance`含status/required/met/items，与objective/human/overall分开；状态语义见评分合同。
- 题包最多50题/900KB。预览逐题收集错误，valid=false时禁止提交。提交重新校验并比较规范化fingerprint；一事务写全部task、revision及task_import回执。相同requestId/fingerprint幂等，内容不同拒绝，所有ID生成新副本。
- 题包记录importSource.original（原id/revision）及原题sha256；baselineId仅引用已有本机快照。导入无自动克隆、镜像准备或命令执行。

|拟新增部分|输入/关系|兼容规则|
|---|---|---|

|AI 意见处理|reviewId、finding索引/稳定ID、处理决定、理由|保存新事件，不改原意见内容|
|版本浏览/恢复|实体ID+revision，新副本来源|旧 Run 仍只读；不能升级后重算覆盖历史|
|按历史重建|源 Run、选定试次、请求ID|新工作区与新 Run；先展示哪些条件可以复用|
|异常与恢复事件|source/kind/phase/recoverability/details|保留原始错误，未知分类保持 unknown|

表中仅列尚未实现的扩展，具体路径随工作包编码时补在现有路由中。迁移需有旧 fixture、新 fixture 和回滚后的只读策略，不能单凭 JSON 允许未知字段就宣称兼容。

## 7. 并发与失败细则

已有 revision 防止同一实体覆盖，Run 后台写入由锁串行化；仍需保证“选中的契约版本”和“提交评价的目标快照”没有变化。前端仅禁用按钮不构成服务端互斥合同。

目标中的错误至少区分：输入无效、版本冲突、状态不允许、证据不存在/变更、环境不可用、操作中断。每类带用户可做的动作；失败不得重置草稿或清除历史。当前中文 ValueError 足以提示基础错误，但不足以驱动完整恢复流程。

当资料规模增长，/state 全量返回所有 Run 和内嵌证据会变重。完成主要语义后，在 B06 评估摘要/详情与分页；不能为了分页先造远端数据库。

## 8. 验收案例

- **D-AC1**：旧 catalog 和旧 Run 升级后字段未丢、分数未被静默新算法覆盖。
- **D-AC2**：准备的文件写入失败时，不产生可操作但缺 baseline 的假 Run；恢复可定位残留目录。
- **D-AC3**：提交过期 revision/错误 captureId 被拒，既有记录不变。
- **D-AC4**：导出验证 hash，损坏时给出说明；不能读不在清单中的路径。
- **D-AC5**：恢复配置/归档/按历史重建三种动作有不同结果和来源回执。

配置新增 skillMode:auto/explicit，importSource由服务端写入（来源范围、文件/哈希、时间、缺省说明），普通编辑保留原来源。Skill 保存 name/description/scope/sourceLabel/sourcePath/manifest；有效扫描要求 name/description，旧手动导入继续兼容。新 Trial.executionPrompts 逐配置逐阶段冻结实际发送文本和哈希，包含选定技能路径与使用意图；旧 Trial 仍回退到原 Task 提示词，读历史不追加要求。

prepare.configOverrides为数组，每个所选配置至多一项：configId、revision、skills、skillMode；不可夹带模型/规则等字段。先匹配幂等请求，再校验来源revision和技能，保存到Run.configs而不写records/config。实际改变时记录preparationOverride.sourceRevision/sourceSkills/sourceSkillMode；省略该数组保持旧协议行为。

## Codex 应用与量表 v2

POST /codex/status读取白名单设置、已有MCP/插件ID及脱敏应用回执；/codex/apply按configId+revision显式备份写入；/codex/switch先撤销活动应用再应用目标；/codex/restore按applicationId校验并恢复。POST /runs/:rid/trials/:tid/apply-config只接受prepared态，使用本题冻结版本并保存appliedHostFingerprint。以上均沿用本机令牌、来源校验与服务锁，无任意命令执行入口。

Config新增nativeSettings（web_search/model_verbosity/model_reasoning_summary白名单）及integrations（mcp_servers/plugins中已有ID的布尔启用覆盖）。认证和工具命令不进入配置副本。prepare生成项目级原生配置并纳入baseline。

arena-review-v2保存dimensions权重和rubrics={id:{label,description}}，最多16项、0权重停用；服务端按冻结策略验证人工分。旧v1仍按原四项校验与计算。state提供rubricCatalog和新桌面默认策略，不迁移旧Run。

新准备页额外冻结dimensionUnit=percent（dimensions合计100）和requireDimensionEvidence=true。review请求增加dimensionEvidence={维度ID:实际依据}，集合须与适用计分维度一致，各项非空、最多3000字；旧策略未启用时不新增必填。

Trial.objectiveReviews保存id/at/captureId/evidenceKey/score/reason/evidence/originalScore。score新增objectiveEvidenceKey、adjudicatedObjective、adjudicatedOverall、objectiveReviewId；未裁定/撤回/失效时裁定值为null。evidenceKey由各阶段最新回收清单、检查回执及冻结检查定义生成，服务核对文件哈希后追加裁定。reason/evidence分别最多3000/5000字。归档只读、锁和版本控制沿用Trial动作约束。


/codex/status新增instructionsFile；活动applications项新增filesMatch与fileChecks=[{path,matches}]，按当前磁盘内容对应用后hash核对。历史status=applied只证明当时写入成功，不能替代当前匹配字段。响应不含备份/配置正文；撤销仍使用原有冲突保护，不依据前端核对结果越过后端校验。


U19：/codex/status活动回执在有变化时增加canPreserveChanges（只读预检）；/codex/restore增加可选preserveUnrelated:true，后端再次三方核对，不信任前端旧状态。/runs/:rid/trials/:tid/open接受draft:true，仅首轮使用服务端冻结的executionPrompts文本和本试次workspace生成codex://threads/new?path=...&prompt=...；不得由客户端传入任意目录/协议/命令。Windows调用注册协议，失败不回滚已准备工作区，不自动开始计时或发送任务。默认open旧目录方式继续兼容。

机器方案 POST `/runs/{rid}/trials/{tid}/judge` 请求captureId/model/usageAcknowledged=true及可选environment，Docker串联可用脚本与机器裁判，本机跳过容器脚本；无脚本允许启动。没有本次明确额度确认直接拒绝，不创建裁判作业。新报告标注judgeBlinding/judgePromptVersion/judgePromptSha256与可获得的judgeUsage累计计数；`judge-progress`也从旧事件或超时rollout读本作业累计用量，未知保持null，不当作免费。POST同试次`/machine-correction`请求reviewId/evidenceKey/changes，changes为维度到{score,reason}的映射；拒绝后台运行、过期证据或无理由。开放项目的score.machine/machineCoverage/machineRatings/machineOverrides/effectiveScores/overall由适用维度派生；machine是AI原分，overall含当前人工修正，缺项或未completed为null。**当前 arena-machine-v1 协议**：公开题的scoreSource=native-verifier，overall只由当前快照哈希匹配的原题程序reward生成100/0，未验收为null；AI维度仅作独立参考，人工修正不能改写程序结果。U46 拟另增本地连续任务分，不回写这一历史字段的意义。

### U24交付方式与引用状态

/runs/prepare新增deliveryMode：single-delivery（默认）/staged。仅转换新Run的执行副本，保留authoredStages/authoredChecks；expectedTurns为null，不由步骤推断回复次数。机器策略complete允许任意已回收版本，记录finalCaptureId；新回收清除它。早期结束后的整题报告须evaluationScope.kind=final，原阶段分不参与最终分。ratings/criteria引用失败仅降级对应项并返回validationWarnings；文件唯一原文定位保留reportedLine/anchor。旧记录只读兼容，不迁移或回填分数。

### U25 能力与裁判过程接口

state.models 增加 reasoningLevels、defaultReasoning、capabilitiesKnown，来自当前 CODEX_HOME 缓存；无记录时为空，不推测。/codex/status 新增当前全局文件 model/reasoning，不代表任务运行值。

POST /runs/{rid}/trials/{tid}/judge-progress 是经过现有同源/令牌保护的只读接口，返回 execution、commands、truncated、error。execution 为当前任务的 jobId/model/reasoning/environment/captureId/status/起止时间和本机 logDirectory；commands 仅真实命令事件，最多最近30条，单条命令6000字符、输出10000字符，最多读取日志末尾1MB。路径由所属试次生成并检查符号链接，不能指定任意文件。后台生命周期保存在 Trial.judgeExecution；重启中断明确标记，不改历史评分。

### U26 内置题与配置回收站

启动种子阶段自动安装缺失的original-search-notes-v1、original-storage-migration-v1、original-csv-catalog-v1及各自baseline；存在活动或归档记录时跳过，保留旧版本。POST /tasks/import-originals仅保留兼容。Task新增可选environmentNote文本（最多10000字符），保存、题包导入和冻结沿用现有校验。

删除配置仍使用POST /configs/{id}/archive，带当前revision与archived:true；恢复传false。接口不做永久删除、宿主撤销或历史Run更新。前端名称改为删除/回收站，存储语义不变。

Task.requiresBaseline为布尔值，项目类重构也可要求源码；旧perf-01-props-to-signals未声明时兼容为true。新Run在创建目录前拦截缺源码的必需起点题；旧Run不重写。


### U29 下载与数据管理接口

- POST `/sources/prepare`：taskIds为固定索引中的id，最多10个，空数组只下载全部定义；立即返回持久化source_job。state.sourceJobs提供进度/成功/逐项错误。单进程同时一个下载工作，不调用模型、安装脚本或官方验收器。
- POST `/storage/status`：返回本项目数据根、分类字节数、活动/归档评测工作区、快照与reviews占用、cleanup状态及canClean；工具发现只表示可执行文件可见，不代表环境已验证。
- POST `/storage/workspace`：runId/trialId/revision/action；trash还需desktopStopped=true，并核对最新快照与未回收改动；restore只恢复原位置；purge要求confirmation为“永久删除工作区”。仅completed且已有capture、无后台任务/容器时允许。所有路径由id推导，拒绝链接/联接。移动后DB失败回滚目录；purge先持久化deleting再删，故障后可重试。返回更新的storage状态。

三接口保持本机Host/Origin/令牌校验，不接受任意路径或命令。清理后open/start/capture/next受限；恢复后重新允许，历史查看与评分证据保留。清理试次不继续自动同步桌面日志。下载和裁判临时文件位于.local/arena；不改变用户全局认证目录。数据页不是通用文件管理器，当前不支持任意删除被引用的证据或源码。

### U30 本机测试接口

- `/sources/prepare`增加prepareEnvironment:true，仅允许固定适配白名单中的Tengo两题和Yaegi Embed；先准备源码、工具链并验证故障起点，再保存ready-windows新版本。未支持或归档题拒绝。
- POST `/runs/{rid}/trials/{tid}/native-check`：captureId指定冻结版本。后台checking，trial.nativeExecution保存jobId/阶段/状态/版本，支持既有stop。结果追加到capture.nativeVerifications，包含原生通过数、reward、manifest hash、工具链/来源版本、命令回执与日志目录；不覆盖checks或reviews。失败/取消不追加伪零分，重启标interrupted。
- POST 同路径`native-log`：suite为1–7，只读该试次最近测试任务末尾20KB日志；不接受路径/命令。各次完整日志保留native-checks。JSON导出包含结果回执；完整原生日志仍保存在本机，不随ZIP导出。

native-runtime/native-homes为每次临时副本和空CODEX_HOME，正常完成或取消清理；不复制认证，不调用模型。Windows命令沙箱允许root读取，写入限临时副本且禁网络，并非宿主读取隔离；不宣称无任何宿主可见信息。工具链准备按进程锁串行，超时/取消停止进程树。

### U31 创建时按需准备

- POST `/runs/prepare-async`：沿用prepare字段，必须提供requestId。立即返回preparation_job（id/status/phase/taskIds/runId/error/时间）；state.preparationJobs供轮询。running/completed同内容请求幂等，不同内容同编号拒绝；failed/interrupted可重试。单实例一次准备，网络不占主API锁；完成前核对配置和题目版本，改变则不创建Run。源码按固定索引获取，适配题自动准备环境，最后调用原prepare冻结。
- POST `/sources/preview`：taskId仅固定索引id，只下载并校验instruction.md，返回text。不能指定URL、路径或命令。
- 服务重启将未完成准备标为interrupted；若同requestId的Run已写入则恢复completed。保留缓存，不自动重复执行。下载文件重试一次后给出可重试错误。原同步prepare和sources/prepare保留兼容，主UI不再要求预下载。

## U33–U34 补充接口

- storage/delete-workspaces：第一项独立操作，runId/revision/desktopStopped/确认短语/精确关联的Codex会话ID清单。拒绝运行中的检查或裁判；按固定工作区cwd再次核对会话，通过Codex CLI删除并核实索引已消失，再删除本次所有工作区（含旧待删除区），保留快照、评分和记录。先持久化deletionPending与workspaceDeletion，文件占用或中断后可在同一步重试，已开始的删除不受旧revision阻断；成功后清除deletionPending，可继续对保留快照评分，但不能再打开被删除的开发工作区。只读Git对象按受限路径清除只读属性后重试；不跟随链接。
- storage/delete-run：第二步，仅workspaceDeletion=deleted后允许，runId/revision/确认短语。先保存recordDeletionPending，再删除owned运行目录、凭回执确认的裁判残留，最后事务删除records/revisions与准备任务、截断WAL。共享缓存/配置/宿主日志/手工导出不在范围；中断可继续第二步。Codex侧栏项目文件夹不属于会话，当前受支持接口不能删除项目索引，需在Codex项目菜单移除。
- state.initialConfig、codex/restore-initial：一次三文件备份与显式恢复，完整性校验，当前文件另存撤销回执；认证不进入初始配置备份。
- runs/{rid}/trials/{tid}/inspection-status|file|prepare|open|save：均受既有本机令牌/Origin保护。data.captureId必填；file.path必须在快照清单，文本只作为文本，PNG/JPEG/WebP惰性显示。prepare生成human-inspections/{id}/workspace，不执行命令；open只打开本次记录目录。save追加版本绑定参考评价，不改原评分。
- judge-progress新增实际instruction、公开agent messages、命令、elapsed与runtime目录；不返回reasoning事件。
- `POST runs/{rid}/trials/{tid}/judge-screenshots`：只读列出本题已保存裁判报告或当前失败作业的最多20张光栅截图；提交 `reviewId` 选择历史报告，不提交则使用当前 `judgeExecution.jobId`。再提交返回清单中的 `path` 才返回单张不超过2 MB的 PNG/JPEG/WebP data URL。服务端从本题 review 目录重建路径、逐段拒绝链接和越界、检查文件头；不提供 SVG/HTML/任意文件入口。图片供人工复核，存在不等于 AI 已看图。

人工副本位于run内，整评测删除包含它；仅workspace清理保留它。人工预览链接只接纳明确端口的本机HTTP地址，工作台不代理获取该URL、不自动运行项目脚本。

## U46–U47：评分卡、连续分与配置分的数据合同（v1 已接入，完整实体待补）

当前已有任务版本、冻结快照、原题验收、机器报告、人工记录与桌面用量。U47 增加 `trial.score.taskScorecard` 派生视图和前端 `configResults` 最近完整批次汇总；五题旧 CTRF 从本地报告只读追溯，原题 reward 不改。下表是**尚未完整实现**的持久化评分卡/具名题集/配置快照合同，不能把候选实体误读为现成请求协议。前端当前分已有真实 UI 回执，但后端统一聚合接口仍待补。

|候选实体|不可缺少的字段与关系|不允许的隐式行为|
|---|---|---|
|`taskScorecardRevision`|独立版本ID、taskId/taskRevision、适用条件、预先声明的条目ID/分值/锚点/必要程度/证据方式/人工权限、创建来源与hash|看过结果后覆盖旧权重；把原题通过用例逐个按数量计权|
|`trialScoreAssessment`|run/trial/captureId/captureHash、scorecardVersion、各条目证据引用、系数、贡献、未验证原因、最终本地分、原始与修正版本、追溯标记|覆盖原生reward、旧`overall`或原AI报告；把部分已评分项归一化为全题分|
|`nativeVerification`|现有上游镜像/源码/验收器版本、F2P/P2P/奖励、命令输出、时间和快照关联|用本地新增测试冒充发布方结果；环境错误写成失败0|
|`suiteRevision`|具名题集、题目/评分卡版本、执行预算、重复策略、预先声明的题权/领域及时间窗|批次结束后按哪套配置赢了来删题或改权|
|`configScoreSnapshot`|configId+revision、suiteRevision、截止时点、计划/有效/缺失/排除任务、同题重复均值、跨题均值、领域画像、聚合协议版本|把全部历史中题目覆盖不同的均值当通用排名；读取当前编辑器覆盖旧记录|
|`efficiencyEvidence`|被测与裁判用量分别记录；Token 分类、缓存、活动/等待/墙钟时长、价格来源/日期/假设、是否实际账单|估算成本当真实扣费；缺日志推断免费或速度更快|
|`comparisonSnapshot`|匹配题目、条件指纹、配对试次ID、逐题差值、顺序、失败/中断、样本数、评审协议与不确定性|单次 0.1 或 1 分差自动宣布配置胜出|

后续具名题集的数据读取路径应由**后端统一聚合**，历史页、批次页、配置成绩页共用同一已冻结解释，避免前端各自写不同的公式。目前单题分由后端派生，配置分由前端同一 `configResults` helper 汇总。持久化评分卡版本须先验证权重合计100、条目稳定ID、证据语义和适用条件；评分作业只引用现有快照和已经保存的检查回执。人工改动作为追加事件，后端按“最新有效修正＋原证据”派生当前本地分。新 Capture、验收回执变化、题目或量表版本变化使旧派生分失效而保留旧记录；禁止偷偷沿用修正。旧 `arena-machine-v1` 保持原样可读。

缺失语义至少区分：未准备/未执行、程序确证失败、环境或工具故障、引用无效、证据待补、正式交付未结束、条目不适用、评分协议不兼容。`null` 必须伴随状态和下一动作；只对**确证未达标**条目计零。若必要验收器未就绪，保留局部条目和原生日志，但本地最终任务分及对应题集分为空。既有五份 DeepSWE 快照已附加统一版本的只读追溯评价，不重跑被测模型；页面并列展示 U45 原题 reward 和 U47 本地分，当前完整批次为 91.2，旧 80.0 是历史 reward×100 口径。

后续接口沿用本机令牌/Origin、固定ID推导路径、revision 乐观锁和任务互斥，不新开任意命令或任意文件接口。需要的动作依次为：只读预览评分卡与题集 → 保存新版本 → 对指定现存 capture 补验证据/评分 → 人工修正主观项 → 读统一派生汇总与配对报告。每次返回目标快照哈希、算法/裁判版本和排除理由。失败或中断可在同一冻结版本重试；不可因刷新而重复计分或重复消费额度。公式 v1 已获审定；完整持久化路由、API 冲突/幂等/快照变动测试和前后端同值核对仍待实现。

U54 的新增开放题使用**已有** task、baseline、run、trial、capture、review 实体与导入路径：catalog 元信息只在缺失 ID 时生成冻结题目，各题起点以单独 baseline 保存，`checks=[]` 为无专用程序验收，不能序列化成“程序通过”。已创建的题目修订、归档态和旧评测不被启动导入覆盖；后续为题补原验收时须创建新题目/评分协议版本，不回写旧题的证据含义。`catalog/core-task-set.json` 和 `catalog/benchmark-families.json` 是前端精选顺序与研究说明，前者不是 `suiteRevision`，后者不是可执行任务 API。两者不参与后端分数或来源准备计数。

## U64：题源导入与等级报告

`POST /api/arena/sources/webgen`：沿用Host/Origin/X-CHB-Token保护，固定来源、无任意URL参数，返回added/total/shortCandidates及首次导入的commit/sha256/officialVerifier=false。下载与写入使用已有应用锁；失败不伪报成功，重试跳过已存在题。固定缓存路径属于本地私有数据清单，不打包到Git。

机器packet新增scoringContract（version、facets、anchors、requirements、formula、calibrated、sha256）；protocol.json新增scoringProtocol，历史无此字段使用旧校验。报告包含ratings[dimension].checks[coverage|quality|resilience]及score/level/method/reason/evidence/counterEvidence/可选constraint，另含requirementChecks、scoringProtocol、scoringContractSha256、calibrated=false。报告与命令、截图仍归属于同一冻结capture。缺失细项null保留，不把错误消息转成数值。

抽题备注保存balanced-v2、seed、候选池数和实际所选task IDs。相同版本题库/分组/seed可重放，允许用户手调且实际清单为准；种子不是跨题库版本的唯一复现依据。

## U65：配对实验数据与接口

- POST /api/arena/configs/minimal-copy：configId、revision；返回新配置。只写配置库，不改源版本或宿主。
- prepare与prepare-async接受可选experiment={hypothesis,repeats,activeMinutes,maxTokens}以及两个configIds。普通单配置请求保持原行为。现有requestId幂等、准备进度和恢复继续适用。
- run.experiment保存完整冻结计划；trial增加pairId、repeat、experimentArm。实际全局应用增加experimentHostContext，用哈希记录未列入实验变量的宿主设置；回收时再采集比较，不返回私有正文。
- present_run只读生成experimentReport，包含arms、pairs、条件、资源、原始差与可比较差。旧run不追加伪计划或改历史分。原生日志usage新增serviceTiers，缺失为空数组。
- ZIP record.json含计划及报告，仍只由本机用户下载；不得上传私有配置、工作区或轨迹。

## U69：题源与派生程序摘要

POST /api/arena/sources/evalplus以固定远程URL和SHA导入，返回added/total(163)/indexed(164)/excluded/commit/sha256，不接收任意网址或宿主命令。已有/归档题跳过，不覆盖。题目fixedSuite属于冻结数据；present_run派生score.programAcceptance，不修改旧评分。run_checks继续保存当前快照的检查stdout/digest/argv，摘要只接受完整匹配的结构化回执，错误/超时为未知。缓存、参考解、测试包和QA不提交Git。
