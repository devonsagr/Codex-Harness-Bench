# Codex Harness Bench

保存两套 Codex 配置，用相同任务和条件运行，并查看实际交付、耗时和证据。执行与容器隔离复用 [Harbor](https://github.com/harbor-framework/harbor)。

当前为 **本地最小验证版**：两个示例 profile、一个原创 Python 搜索修复题、独立验收容器、配置快照与静态 HTML。源码准备开放但尚未推送；不是正式公开排行榜。

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

首版还没有：MCP 对比、完整配置导入导出/恢复、多轮需求、SWE-bench 子集或置信区间。这些保留在 [路线图](docs/ROADMAP.md)。

## 验证与项目文档

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 scripts/validate_task.py
```

第二个命令用 Harbor 的 nop 和 oracle 验证错误起点被拒、参考解通过，不调用模型。

[当前交接与实测结果](docs/当前交接.md) · [需求原话](docs/requirements.md) · [设计合同](docs/PROJECT_SPEC.md) · [竞品调研](docs/research/landscape.md)

本项目代码和原创题采用 MIT；Harbor 为 Apache-2.0。未打包第三方数据集或用户个人 skills。
