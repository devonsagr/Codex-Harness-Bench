# 数据、接口、版本与恢复合同

负责 D15-05/14/17/20；主要工作包 B01/B02/B05/B06。先列现有协议，再列扩展提案，避免把未来接口写成现在就能调用。

## 1. 数据权威与分层

业务事实来自本机 SQLite 与冻结文件。React localStorage 只保存外观偏好。App 调 API 取得状态，成功写入后重新读取；服务断开不能回退随机数据。

现有链路：`App/Runner/Editors/Records → workbench/api.ts → webapp.py → arena/api.py → service/jobs/scoring/telemetry/files → Database/本地文件`。

继续开发时按能力分离校验与序列化，避免把项目契约、评分和生命周期继续全部塞进 service.py；仍保持单进程本机应用，不为拆模块引入微服务或新调度平台。

## 2. 现有数据库

|表|键|字段/作用|
|---|---|---|
|records|(kind,id)|revision、body(JSON)、archived；当前记录|
|revisions|(kind,id,revision)|body(JSON)、created；历次版本|

kind 包括 config、task、skill、baseline、run。Trial/Capture/Review/事件目前嵌在 Run JSON 中，并非各有独立 SQL 表。写入使用 SQLite 事务、BEGIN IMMEDIATE 和预期 revision；启用 WAL。不能在文档画出不存在的独立关系表后宣称已实现。

文件系统与数据库不是一个原子事务；当前先创建部分目录再保存记录，准备中途失败可能留下未登记目录。B05 要补可恢复的准备回执或临时目录提交策略，不能通过全局清理解决。

## 3. 现有实体字段

|实体|主要字段|不可变关系|
|---|---|---|
|Config|id/revision/name/agentsPrompt/baseModel/reasoning/interactiveMode/skills/customConstraints|Run 内保存选定版本完整正文|
|Task|id/revision/title/taskParadigm/channel/difficulty/inputPrompt/stages/checks/baselineId/hasFrontendUI/来源|Run 内保存选定版本；额外原型字段目前可透传但未完整校验|
|Skill/Baseline|id/name/sourcePath/manifest/createdAt|manifest 对应本地冻结文件|
|Run|id/revision/requestId/requestFingerprint/configs/tasks/policy/hostFingerprint/executionMode/trials/events/notes|创建冻结输入；随后仅追加过程和版本|
|Trial|id/configId/taskId/state/stageIndex/workspacePath/baseline/captures/reviews/sessionId/usage/observations|每一配置×题目独立目录|
|Capture|id/stageIndex/at/manifest/facts/response/checks/checksConfigured/harnessUnchanged/hostUnchanged|文件不可改写；检查尝试保留并可重跑|
|CheckResult|id/label/weight/argv/imageId/status/exitCode/seconds/output|绑定 Capture；旧尝试在 checkAttempts 留存|
|Human Review|id/kind=human/captureId/at/scores/notes/readiness/constraints|追加新版本，不覆盖 AI 或检查|
|AI Review|id/kind=ai/captureId/at/summary/findings/遗漏及执行元数据|独立意见，绑定回收哈希与模型|
|Usage/TraceReceipt|sessionId/各累计Token/时间/models/reasoningLevels/errors，及原文hash和导入时间|同会话累计不回退，完整原文仅本地|

当前 policy 版本固定 `arena-review-v1`；不是把用户传入任意版本号作为算法实现。Run 的 state 由所有 Trial 是否 completed 派生；Trial 的 completed 不是 accepted=true。

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
|/skills/import|path、可选 name|冻结 Skill|
|/baselines/import|path、可选 name|冻结 Baseline|
|/tasks/save|题目字段；编辑带 id/revision|新 revision 的 Task|
|/tasks/import-originals|空对象|imported 数组；重复导入跳过已存在 ID|
|/{configs\|tasks\|runs}/{id}/archive|revision、archived 布尔值|归档/恢复后的实体|
|/runs/prepare|requestId、configIds(1–2)、taskIds(1–10)、policy、notes|冻结后的 Run；相同请求内容可幂等返回|
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
|review|captureId、scores、notes、readiness、constraints|只接受最新回收的人工评分，新建版本|
|check|captureId|异步运行该快照适用检查；可选历史阶段快照|
|judge|captureId、model|显式启动使用额度的 AI 复审|
|stop|{}|返回 stopping:true / desktopStopped:false|

动作状态前提见 [执行合同](EXECUTION_AND_EVIDENCE.md)。接口列表不是统一保证所有动作在所有状态可调用。

## 6. 拟新增合同与迁移顺序

|拟新增部分|输入/关系|兼容规则|
|---|---|---|
|结构化项目契约|Task schemaVersion、稳定条目ID、项目/阶段约束|旧字段先保留，按显式迁移生成新题 revision|
|提示词编排|冻结 Task/Stage/契约，生成文本与hash|运行创建后文本不受当前编辑器修改影响|
|逐条验收|captureId、criterionId、status、notes、evidenceRefs|绑定运行内题目版本，拒绝不存在的条目|
|AI 意见处理|reviewId、finding索引/稳定ID、处理决定、理由|保存新事件，不改原意见内容|
|版本浏览/恢复|实体ID+revision，新副本来源|旧 Run 仍只读；不能升级后重算覆盖历史|
|按历史重建|源 Run、选定试次、请求ID|新工作区与新 Run；先展示哪些条件可以复用|
|异常与恢复事件|source/kind/phase/recoverability/details|保留原始错误，未知分类保持 unknown|

接口具体路径随各工作包编码时补在本文对应表，未实现前不出现在“现有路由”中。迁移需有旧 fixture、新 fixture 和回滚后的只读策略，不能单凭 JSON 允许未知字段就宣称兼容。

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
