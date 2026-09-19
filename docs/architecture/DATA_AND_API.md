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
    reviews/job-.../                  # Harbor 审查材料与产物
```

恢复归档只改可见性；恢复历史配置创建新配置；计划中的“按历史条件新建评测”创建新 Run/Trial。三者均不直接覆盖原工作区。当前没有 ZIP 导入恢复协议，导出 ZIP 也不是已经实现的可移植全量备份。

现有 ZIP 包含 record.json、baseline 与 captures 文件；不含原生完整日志/认证。它含私有规则与候选产物；用户本地下载，不自动上传。需要完整机器备份时应在服务停止后保存整个 `.local/arena/`，并保留已有版本信息；这是本地文件备份操作，不是应用内导入功能。

## 5. 现有 HTTP 约定

- 同源入口 `http://127.0.0.1:8765`，仅监听回环地址；校验 Host。
- `/api/` 读取要求 X-CHB-Token；写入再要求匹配 Origin。首页 meta 注入随机令牌，不提供任意来源 CORS。
- JSON 写入通常限制1 MB；trace 路由 HTTP 限制20 MB，原文限制15 MB。Content-Type 为 application/json。
- 成功通常返回实体对象或操作结果，前端随后刷新 state；错误对象为 `{ "error": "说明" }`。现有错误主要是中文消息，没有稳定业务错误码，B05 要补可操作的分类。
- 后台 check/judge 先返回含运行状态的 Run；App 在有后台操作时约1.8秒轮询 state。当前不是事件流，也没有独立分页任务列表。

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
|/tasks/save|题目字段；编辑带 id/revision|新 revision 的 Task|
|/tasks/import-originals|空对象|imported 数组；重复导入跳过已存在 ID|
|/tasks/import-preview|document：题目对象/数组/版本题包|valid/tasks/errors/warnings/fingerprint；不写入数据库|
|/tasks/import|document、fingerprint、requestId|receipt和imported；整个包与回执同一事务创建|
|/{configs\|tasks\|runs}/{id}/archive|revision、archived 布尔值|归档/恢复后的实体|
|/runs/prepare|requestId、configIds(1–2)、taskIds(1–10)、policy、notes、可选configOverrides|冻结后的 Run；相同请求内容可幂等返回|
|/runs/{rid}/restore-config|configId|历史配置的新副本|

相同 requestId 携带不同内容会拒绝；网络返回不确定时前端复用原 ID。正常“再测一次”必须用新 requestId。

### Trial 动作（POST /runs/{rid}/trials/{tid}/{action}）

|action|请求体|作用|
|---|---|---|
|open|{}|请求打开桌面目录，不发送提示词|
|start|settingsConfirmed:true|记录用户已核对并开始该轮|
|capture|可选 response|封存新 Capture|
|continue|{}|已回收后进入下一预定阶段，仍等待开始|
|complete|{}|最终阶段已回收后记录交付结束|
|interrupt|reason|外部中断记录，不停止桌面|
|trace|raw(JSONL 字符串)|归属校验后保存原文和累计用量|
|review|captureId、scores、notes、readiness、constraints；v2加criteria、constraintNotes、revisionReason|只接受最新回收；条目集合必须完整，修订已有复审须原因；始终新建版本|
|objective-review|captureId、evidenceKey、score(0–100或null撤回)、reason、evidence|最新回收且完整客观原分；拒绝后台运行和过期证据；追加人工裁定，不覆盖原分|
|check|captureId|异步运行该快照适用检查；可选历史阶段快照|
|judge|captureId、model|显式启动使用额度的 AI 复审|
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

机器方案 POST `/runs/{rid}/trials/{tid}/judge` 请求captureId/model，串联可用脚本与机器裁判；无脚本允许启动。POST同试次`/machine-correction`请求reviewId/evidenceKey/changes，changes为维度到{score,reason}的映射；拒绝后台运行、过期证据或无理由。返回Run，分数由score.machine/machineCoverage/machineRatings/machineOverrides/effectiveScores/overall派生。machine是原分（缺项时暂定）；overall含当前人工修正，缺项或未completed为null。程序结果和criteria不被修正覆盖。
