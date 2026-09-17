# Codex Harness Bench 项目合同

- 本地工程与 Git 根：`D:\AAAcodex项目\harnes测试`；origin `https://github.com/devonsagr/1.git`（GitHub 已重定向到同一仓库 `devonsagr/Codex-Harness-Bench`）。用户 U06 已授权上传源码、公开题目与文档；私有配置、原文、轨迹与产物不提交。
- 本地权威文档根：`docs/`。唯一需求保真记录：`docs/requirements.md`；完整附件 `.local/sources/2026-09-10.md`、`.local/sources/2026-09-15.md` 仅本地。
- 唯一当前架构与实施路线：`docs/PROJECT_SPEC.md`；前端合同：`docs/FRONTEND_SPEC.md`；当前交接：`docs/当前交接.md`；历史版本证据：`docs/CODEX_HISTORY.md`。`docs/ROADMAP.md` 仅入口指针；旧 F1/F2 合同在 `docs/archive/`，不作为当前实施路线。
- 文档索引：`docs/README.md`；Gemini对齐审计及模块合同：`docs/architecture/`。主架构第8节B00–B10是唯一工作包状态来源，模块合同保存细则/接口/验收，不再各自维护路线。U10要求以用户原文、Gemini源代码和当前实现三方核对；不能以保留主题导航或基础测试通过宣称完整接入。
- 用户 U07 已否定旧前端产品逻辑，指定采用 Gemini 前端。源目录 `D:\AAAcodex项目\杂\codex-harness-arena` 只读；工程副本 `frontend/`，来源回执 `.local/sources/gemini-frontend-20260915.json`。不要恢复随机成绩/模拟执行。
- 用户 U08：桌面端为正式评测，准备独立工作区，在 Codex 桌面手动执行，回收产物后验收。CLI 自动跑单独标注。单配置、项目构建为主，Bug 修复分开；多轮明确等用户确认。
- 工作区规则是叠加层，仍继承宿主全局 AGENTS/技能/插件；不能宣称全部隔离或替换。不得暗改宿主 Codex 配置；U15授权用户点击“一键应用到Codex”后写入所选设置，必须备份、校验及可撤销。开发验证只使用隔离CODEX_HOME，不替用户选一套日常全局配置。
- Obsidian 镜像：none；未指定镜像根，声明集合为空。不回写日记，不扫描 Vault。
- Python 3.12+；本机 `.venv\Scripts\python.exe`（3.13）。安装 `uv sync --frozen`。
- 前端 Node.js + pnpm；安装 `pnpm --dir frontend install --frozen-lockfile`；类型检查 `pnpm --dir frontend exec tsc --noEmit`；构建 `pnpm --dir frontend build`。
- 启动：双击 `launch-ui.cmd`，或 `.venv\Scripts\python.exe -X utf8 -m chb.cli ui`，默认 `http://127.0.0.1:8765`；`--no-browser` 不自动打开。Python 同源提供 React 构建与 API。
- 本机 API：仅 127.0.0.1；Host、Origin、随机令牌保护。没有任意文件/宿主命令入口。业务数据以 `.local/arena/arena.sqlite3` 和冻结文件为准，不以 localStorage 为准。
- 新后端：`src/chb/arena/`。配置、题目版本不可覆盖；回收生成新快照；人工评分、AI 意见和客观检查分存；缺失指标为 null；不编造固定误差与费用。
- 测试：`.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v`；语法 `.venv\Scripts\python.exe -m compileall -q src scripts tests`；Python 无独立类型检查器。
- 包构建 `uv build`；独立 wheel 不是完整数据/React 分发，支持仓库 editable 安装。
- 容器准备 `.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only`；可加 `--task storage-migration-v1` / `--task csv-catalog-v1`。题库内可显式导入三道完整原创题；31 份 Gemini 题面不能冒充31套已验证测试。
- 旧容器题自检 `.venv\Scripts\python.exe -X utf8 scripts/validate_task.py`，只运行 nop/oracle。新工作台验收见 `scripts/validate_arena.py`；仅 `--judge-model` 显式启用一次有时限的 AI 审查。
- Docker 检查只挂载本次冻结快照且只读，在容器副本执行；不挂项目根、个人 home、Docker socket。独立 AI 审查由 Harbor 管 CLI 执行，标注 `cli-review-only`。不得再造通用 Agent runner。
- 旧 CLI 实验仍在 `runs/`，与桌面新工作流分开；schema 1/2 只读兼容，schema 3 冻结多题路由/预算。更改 runner/profile/task 创建新实验；历史重分析只写 `.local/analyses/`。
- `runs/`、`.local/`、node_modules、构建文件保持忽略。ZIP 可包含用户私有规则和产物，只由用户本地下载，不自动上传。恢复创建新副本；归档可逆，禁止自动合并/改写历史。
- 长期项目按主架构持续推进完整闭环；交接写真实完成/未验证/阻塞，不再以小步结束要求用户不断回复继续。

- AI 审查专用镜像准备：`.venv\Scripts\python.exe -X utf8 scripts/prepare_arena_review.py`；使用 `reviewer/Dockerfile`，只需 Codex CLI 和 Node，不依赖旧修题 Agent 镜像。
