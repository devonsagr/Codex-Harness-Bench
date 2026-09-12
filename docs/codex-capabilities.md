# Codex 能力与实际支持范围

查阅：2026-09-12。宿主 CLI 为 `0.154.0-alpha.6.2`；实验镜像固定 npm 官方发行 `0.154.0`。不把桌面版 alpha 与公开 CLI 当作完全相同。

本地证据：`codex --version`、`codex exec --help`、`codex exec resume --help`；官方页面全文已在 `.local/research/codex-*.md` 留作只读调查材料。

|能力|官方或本地接口|本项目状态|
|---|---|---|
|模型|`--model`|实验层固定请求标识；不保证后端权重不变|
|推理强度|`model_reasoning_effort`|当前白名单 low/medium/high/xhigh；实验内一致|
|全局指令|CODEX_HOME 下优先 AGENTS.override.md，否则 AGENTS.md|只装载快照 AGENTS.md；校验上传哈希|
|项目指令|项目根到当前工作目录的分层发现|题目固定 /app/AGENTS.md|
|skills|仓库 `.agents/skills`、用户 `$HOME/.agents/skills` 等|可注入本地显式 skill 目录；不自动复制宿主 skills；真实使用不由上传推断|
|原生配置|config.toml、CLI override、profile 文件|仅开放已列白名单；不是任意 TOML 透传|
|配置校验|`--strict-config`|真实运行附加该参数；未知字段不能静默接受|
|搜索|`web_search`|固定 disabled|
|MCP|原生 MCP 配置存在|本 MVP 不支持，遇到字段拒绝|
|权限|CLI sandbox/approval 等|由 Harbor 容器承担外层隔离；容器内使用上游 adapter 执行策略；未提供用户可切换实验权限|
|非交互|`codex exec --json`|Harbor 执行与采集 JSONL|
|续接|`codex exec resume <SESSION_ID>`；Harbor resume capability|接口核实，当前单题单轮未验收续接|
|用量|JSONL turn.completed usage|从实际事件提取，缺失 null|
|费用|订阅模式与 API 模式不同|不报告 API 估值为账单；当前费用 null|
|hooks、子代理等|可能随 CLI 版本演进|本项目未支持，不暴露虚构设置|

依据：[官方配置](https://learn.chatgpt.com/docs/config-file/config-basic)、[指令发现](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[skills](https://learn.chatgpt.com/docs/build-skills)、[非交互](https://learn.chatgpt.com/docs/non-interactive-mode)。

skills 隔离不能只改 CODEX_HOME，因为用户 skills 还可能来自 HOME。本项目用新容器解决宿主配置污染；系统自带 skills 由固定二进制控制。容器镜像中不能包含个人目录、未来答案或任务外的 AGENTS 文件。
