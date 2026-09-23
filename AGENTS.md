# Codex Harness Bench 项目合同

- 本地工程与 Git 根：`D:\AAAcodex项目\harnes测试`；origin `https://github.com/devonsagr/1.git`（GitHub 已重定向到同一仓库 `devonsagr/Codex-Harness-Bench`）。用户 U06 已授权上传源码、公开题目与文档；私有配置、原文、轨迹与产物不提交。
- 本地权威文档根：`docs/`。唯一需求保真记录：`docs/requirements.md`；完整附件 `.local/sources/2026-09-10.md`、`.local/sources/2026-09-15.md` 仅本地。
- 唯一当前架构与实施路线：`docs/PROJECT_SPEC.md`；前端合同：`docs/FRONTEND_SPEC.md`；当前交接：`docs/当前交接.md`；历史版本证据：`docs/CODEX_HISTORY.md`。`docs/ROADMAP.md` 仅入口指针；旧 F1/F2 合同在 `docs/archive/`，不作为当前实施路线。
- 文档索引：`docs/README.md`；模块合同与历史来源审计：`docs/architecture/`。主架构第8节B00–B10是唯一工作包状态来源，模块合同保存细则/接口/验收，不再各自维护路线。U27明确Gemini只提供前端框架，当前产品/题库/评分依据用户目标独立设计；来源审计仅历史追溯，不再作为产品路线。
- 用户U27：在Codex桌面底座上评测模型＋个人可配置Harness；Gemini仅为初始前端来源。源目录 `D:\AAAcodex项目\杂\codex-harness-arena` 只读；工程副本 `frontend/`，来源回执 `.local/sources/gemini-frontend-20260915.json`。不要恢复随机成绩/模拟执行。
- 用户 U08：桌面端为正式评测，准备独立工作区，在 Codex 桌面手动执行，回收产物后验收。CLI 自动跑单独标注。单配置、项目构建为主，Bug 修复分开；多轮明确等用户确认。
- 工作区规则是叠加层，仍继承宿主全局 AGENTS/技能/插件；不能宣称全部隔离或替换。不得暗改宿主 Codex 配置；U15授权用户点击“一键应用到Codex”后写入所选设置，必须备份、校验及可撤销。开发验证只使用隔离CODEX_HOME，不替用户选一套日常全局配置。
- Obsidian 镜像：none；未指定镜像根，声明集合为空。不回写日记，不扫描 Vault。
- Python 3.12+；本机 `.venv\Scripts\python.exe`（3.13）。安装 `uv sync --frozen`。
- 前端 Node.js + pnpm；安装 `pnpm --dir frontend install --frozen-lockfile`；类型检查 `pnpm --dir frontend exec tsc --noEmit`；构建 `pnpm --dir frontend build`。
- 启动：双击 `launch-ui.cmd`，或 `.venv\Scripts\python.exe -X utf8 -m chb.cli ui`，默认 `http://127.0.0.1:8765`；`--no-browser` 不自动打开。Python 同源提供 React 构建与 API。
- 本机 API：仅 127.0.0.1；Host、Origin、随机令牌保护。没有任意文件/宿主命令入口。业务数据以 `.local/arena/arena.sqlite3` 和冻结文件为准，不以 localStorage 为准。
- 新后端：`src/chb/arena/`。配置、题目版本不可覆盖；回收生成新快照；机器评分、人工修正、旧 AI 意见和客观检查分存；缺失指标为 null；不编造固定误差与费用。
- 测试：`.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v`；语法 `.venv\Scripts\python.exe -m compileall -q src scripts tests`；Python 无独立类型检查器。
- 包构建 `uv build`；独立 wheel 不是完整数据/React 分发，支持仓库 editable 安装。
- 容器准备 `.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only`；可加 `--task storage-migration-v1` / `--task csv-catalog-v1`。启动时自动补齐三道完整原创题（不覆盖编辑或恢复已归档题）；公开题源索引与可运行题包分别计数，不能把索引当环境已准备。
- 旧容器题自检 `.venv\Scripts\python.exe -X utf8 scripts/validate_task.py`，只运行 nop/oracle。新工作台验收见 `scripts/validate_arena.py`；仅 `--judge-model` 显式启用一次有时限的 AI 审查。
- Docker 检查只挂载本次冻结快照且只读，在容器副本执行；不挂项目根、个人 home、Docker socket。独立 AI 审查标注 `cli-review-only`：Docker 路径由 Harbor 管理；U22新增固定的本机 Codex 原生沙箱裁判，使用临时凭据目录与快照副本，不修改宿主配置。不得提供任意宿主命令入口或再造通用 Agent runner。
- 旧 CLI 实验仍在 `runs/`，与桌面新工作流分开；schema 1/2 只读兼容，schema 3 冻结多题路由/预算。更改 runner/profile/task 创建新实验；历史重分析只写 `.local/analyses/`。
- `runs/`、`.local/`、node_modules、构建文件保持忽略。ZIP 可包含用户私有规则和产物，只由用户本地下载，不自动上传。恢复创建新副本；归档可逆，禁止自动合并/改写历史。
- 长期项目按主架构持续推进完整闭环；交接写真实完成/未验证/阻塞，不再以小步结束要求用户不断回复继续。

- AI 审查专用镜像准备：`.venv\Scripts\python.exe -X utf8 scripts/prepare_arena_review.py`；使用 `reviewer/Dockerfile`，只需 Codex CLI 和 Node，不依赖旧修题 Agent 镜像。

- U29：DeepSWE固定定义包下载与按题源码准备已接入；依赖/原生验收未就绪不能称官方跑分。下载缓存public-sources/downloads、裁判临时reviewer-runtime与开发runs均位于项目.local/arena，禁止提交。数据页清理仅已回收且结束的workspace，先移入trash/workspaces再显式永久删除，保留快照/复查/评分；验证删除只用隔离夹具。
- U30：Tengo支持Windows固定Go工具链及原测试适配，题库一键准备、快照验收与日志/历史分存；不是官方Linux排行榜。工具链/环境检查/native-runtime/native-homes均在.local/arena；命令沙箱限制写入并禁网，但允许宿主读取，不宣称虚拟机隔离。参考解只用于.local/qa负例/正例验证，不进入开发起点、提示词或Git。

- U31：DeepSWE工作台直接选题，创建时仅准备所选定义与固定源码；同仓库同提交校验复用，每次独立run/trial/workspace。Tengo两题与Yaegi Embed支持Windows原测试适配；ABS改进题仅源码验证。preparation_job持久化进度、请求幂等与中断恢复，不宣称113套环境已就绪。

- U33–U34：裁判思考档位读取原生模型能力，未知档位使用模型默认；本机裁判预算默认1小时、上限8小时，预算耗尽是未完成。首次保护config.toml/AGENTS.md/AGENTS.override.md，不含认证；恢复必须显式且可撤销。工作区清理与整评测永久删除分开；删除测试仅隔离夹具。
- 两类评分解释：公开基准优先原题验收，开放真实项目按需求/质量/体验；程序、AI、人工参考评价分存。人工审查副本在run/trial/human-inspections，页面仅展示文件/图片和已声明启动说明，不自动执行项目。不得将AI质量分冒充官方榜单；所有分数仅供参考。来源研究见docs/research/benchmark-scoring-20260923.md。
