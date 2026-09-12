# Codex Harness Bench

保存两套 Codex 配置，用相同任务和条件运行，并查看实际交付、耗时和证据。执行与容器隔离复用 [Harbor](https://github.com/harbor-framework/harbor)。

当前为 **本地验证版**：示例与私有 profile、配置导入/复制/恢复、搜索/存储迁移/CSV 导入三个原创题型、同批多题计划、独立验收容器、按组与逐轮 HTML 报告和历史日志分析。源码准备开放但尚未推送；不是正式公开排行榜。

## 开始使用

需要 Python 3.12+、Docker Linux 引擎、已登录的 Codex 或 `OPENAI_API_KEY`。Windows 使用项目独立 Python 环境；无需改全局 Codex 设置。

```powershell
uv venv --python 3.13
uv sync --frozen
.venv\Scripts\python.exe -X utf8 -m chb.cli doctor
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare
.venv\Scripts\python.exe -X utf8 -m chb.cli profiles
.venv\Scripts\python.exe -X utf8 -m chb.cli diff minimal focused
```

Linux/macOS 把 `.venv\Scripts\python.exe` 换成 `.venv/bin/python`；目前真实运行验收以 Windows + Docker Desktop 为目标，不声称其他系统已经实测。

准备环境后冻结实验（不调用模型）：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli plan --model openai/gpt-6-astra
```

终端输出实验目录与预计运行数。确认该目录里的 `plan.json`、`profile-diff.txt` 后执行：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli run runs/<实验编号>
.venv\Scripts\python.exe -X utf8 -m chb.cli report runs/<实验编号>
```

`run` 会启动真实 Codex 调用并消耗对应额度。默认两次，每次 agent 上限 300 秒，安装/环境/验收另计。`plan` 默认重复 1 次，可指定 `--repeat 2`，相邻重复反转顺序。模型需对当前账号可用；不会静默切换到别的模型。

打开实验目录的 `report.html` 即可查看结果。任务起点代码、参考解、验收代码在 `tasks/search-notes-v1`；agent 容器只包含起点，验收镜像另行构建。

## 配置与证据

`profiles/<name>/` 包含 `profile.json`、`AGENTS.md`、`config.toml`，可选 `skills/<name>/SKILL.md`。这是本工具的配置包，不是 Codex 原生 profile 文件格式。

当前只开放 `model_reasoning_effort`、`web_search`，未知字段会拒绝。两套示例只改变全局指令，不代表用户完整现有配置，也没有预设任何 skill 有害。完整范围见 [能力表](docs/codex-capabilities.md)。

每个实验保存：

- 输入快照、逐文件 SHA-256、固定模型/版本/镜像/预算/顺序。
- 实际装载的全局指令哈希与 native config；最终回复的 profile 标记观察。
- Codex 事件、候选目录（含新增文件）、外部验收日志、耗时与可取得的用量。
- 全部失败和异常；缺失数据为 null，费用不冒充实际账单。

历史 attempt 不覆盖。修改源配置后建立新 plan；旧快照若被改动则不能运行。`runs/`、认证、完整日记和私人资料默认不提交。

## 能从结果判断什么

单题、每配置一次只验证工具管线。即使两次耗时不同，也不能判断规则带来稳定收益。不同轮次不是独立题；之后需要更多来源独立的任务，再按任务组进行配对统计。

尚未支持：MCP 对比、完整个人配置导入、可移植导出包、SWE-bench 子集或置信区间。这些保留在 [路线图](docs/ROADMAP.md)。

## 导入当前规则并对比一个 skill

以下命令只读取全局说明和白名单设置，输出到忽略提交的 `.local/profiles/`。全局说明优先取非空 `AGENTS.override.md`，否则取 `AGENTS.md`。当前支持的是**部分导入**：不自动遍历整个 home、复制凭据、MCP、插件或全部 skills。省略项与设置调整记录在 `.local/provenance/`。

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli config import-current my-agents --reasoning medium
.venv\Scripts\python.exe -X utf8 -m chb.cli config clone my-agents my-agents-skill --skill 'C:/Users/DevonSage/.codex/skills/brainstorming'
.venv\Scripts\python.exe -X utf8 -m chb.cli diff my-agents my-agents-skill
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --task storage-migration-v1
.venv\Scripts\python.exe -X utf8 scripts/validate_task.py --task storage-migration-v1
.venv\Scripts\python.exe -X utf8 -m chb.cli plan --task storage-migration-v1 --profiles my-agents,my-agents-skill --model openai/gpt-6-astra
```

将 `--skill` 换成实际存在的技能目录；可重复该参数选择多个技能。名称已存在会拒绝覆盖。只有最后另行执行 `run runs/<实验编号>` 才调用模型；两套配置各两轮，共 4 次 agent 执行，每轮最多 300 秒。第一轮实现归档，第二轮续接同一会话切换到 SQLite、导入旧数据并清理旧入口。新题仍只有一个独立任务组。

对照两套配置的全局说明与原生设置完全一致，只有选定 skill 和配置名称不同。两套配置都收到同样的题面；题面显式提示“若有 brainstorming 则使用”。这是显式使用的装载验证，不能据此推断自然触发概率或 skill 的普遍效果。

报告分别展示上传文件哈希、完整 skill 读取输出、会话是否续接和逐轮验收。读取证据不代表每条指令都被遵循。多轮用量通过原生会话记录校验后，展示每轮增量和总量；缺失或冲突保留 null 并显示原因。

## 从历史实验恢复配置

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli config restore runs/<实验编号> <旧配置名> restored-profile
```

这会先校验旧快照，再创建新的私有配置。AGENTS、config 和 skill 内容逐字节保留，只有 profile.json 中的名称更新。不会覆盖历史实验，也不会把恢复结果写回你的 Codex 全局配置。模型、任务、运行版本仍由下一份实验计划固定。

## 补算历史实验用量

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli analyze runs/<实验编号>
```

不调用模型、不重跑任务。程序读取已结束的实验，在 `.local/analyses/<分析编号>/` 新建结果和 report.html。原实验的计划、验收、结果与报告保持不变；新报告记录来源文件哈希和分析代码快照，证据链接指向原始产物。如果重新解析改变了原来的通过/失败结论，会停止而非静默替换。

针对固定 Codex 0.154.0，统计须确认每轮原生会话编号相同、第二轮的用量历史包含第一轮完整前缀、计数不回退，并与 CLI 最终上报一致。总量取最后累计值，每轮使用相邻累计值之差。**输入已经包含缓存输入，二者不能再次相加**。缺日志、未知版本、历史被改写或用量冲突时显示 — 和原因；不会当作零消耗或猜测账单。

## 独立的 CSV 导入题

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --task csv-catalog-v1
.venv\Scripts\python.exe -X utf8 scripts/validate_task.py --task csv-catalog-v1
.venv\Scripts\python.exe -X utf8 -m chb.cli plan --task csv-catalog-v1 --profiles my-agents,my-agents-skill --model openai/gpt-6-astra
```

这是一道单轮、独立代码起点的题，覆盖流式 CSV 解析、Unicode/BOM/引号换行、重复键和错误行、JSONL 原子替换及命令行回归。与笔记题不同，该题不点名要求读取某个 skill。它仍只是一个原创任务组，不代表已建立统计可信的综合榜单。运行依然需要另行执行生成计划对应的 `run` 命令。

## 一次对比多道题

先为所选题目分别执行 `prepare --task <题目名>`。之后把两个命名配置、全部题目和顺序固定在同一份计划里：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli plan --tasks search-notes-v1,storage-migration-v1,csv-catalog-v1 --profiles my-agents,my-agents-skill --model openai/gpt-6-astra
.venv\Scripts\python.exe -X utf8 -m chb.cli run runs/<实验编号>
```

`--tasks` 按逗号列出题目，与单题参数 `--task` 二选一。默认仍是一道搜索题。重复题名会拒绝；`--repeat` 表示同题重复，不会增加独立任务数。

上例每配置各做三题，产生 **6 次整题运行、8 轮 agent 执行**。存储题每次两轮，其余各一轮；每轮 300 秒，上限共 2400 秒，环境准备和验收另计。首次重复的顺序为搜索 A/B、存储 B/A、CSV A/B；下一次重复将每题的配置顺序反转。这个顺序是预先固定的，没有声称完全消除时间和缓存影响。

运行开始前一次核对全部题目、两个配置、镜像、预算和执行顺序。每次整题运行使用自己的环境与新会话，仅多轮题内部续接。执行异常会停止余下批次，已运行记录保留；正常结束但验收未通过会记为失败并继续后续题。不覆盖或补跑同一计划中的旧 attempt。

打开 `report.html`，先看按组的通过、未通过、异常、待完成数量，再看每次运行的证据。配对耗时只来自同一题、同一次重复中双方都通过的结果，并显示覆盖数；没有配对或耗时缺失显示 —。`comparison.json` 保存相同的汇总数据。三组来自题目元数据，其中笔记搜索和存储演进存在共同设计来源，**不能把三个组名当作三个已证明独立的统计样本**。当前不输出跨组速度排名或置信区间。

新计划使用 schema 3，题目分别保存在 `inputs/tasks/<题目名>/`。旧版单题实验仍可用 `analyze` 另建分析报告；新旧实验不会自动合并排名。

## 验证与项目文档

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/validate_task.py
```

第二个命令用 Harbor 的 nop 和 oracle 验证错误起点被拒、参考解通过，不调用模型。

[当前交接与实测结果](docs/当前交接.md) · [需求原话](docs/requirements.md) · [设计合同](docs/PROJECT_SPEC.md) · [竞品调研](docs/research/landscape.md)

本项目代码和原创题采用 MIT；Harbor 为 Apache-2.0。未打包第三方数据集或用户个人 skills。
