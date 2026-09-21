# Codex Harness Bench

在 Codex 桌面中执行真实需求，检查自己的 AGENTS、技能和交互约定如何影响交付。默认一套配置、一道项目构建题；可选对比，Bug 修复单独分类。

以用户提供的 Gemini React 前端为输入，目前已实现本地 Python / SQLite 基础链路：配置版本、技能和起点导入、独立工作区、逐轮回收、客观检查、AI辅助审查、人工评分、历史与导出。**Gemini的产品功能尚未全部接入**：已接项目契约、逐项验收、题包导入与筛选；本轮补配置应用/撤销、全宽准备与自定义评分；配置差异矩阵、完整历史复用与异常恢复仍有缺口。具体对照见[Gemini审计](docs/architecture/GEMINI_ALIGNMENT.md)，不要将基础测试通过理解为整个产品完成。

架构文档从[阅读索引](docs/README.md)进入；[总架构第8节](docs/PROJECT_SPEC.md#8-唯一实施路线与完成标准)给出逐包后端完成路线，[前端合同](docs/FRONTEND_SPEC.md)说明页面与交互，[当前交接](docs/当前交接.md)记录版本和实测范围。

## 启动

需要 Python 3.12+、uv、Node.js 和 pnpm。桌面执行需已安装并登录 Codex；容器检查及 Docker 裁判需要 Docker Linux 引擎；本机裁判需要已安装并登录官方 Codex CLI，不需要 Docker。

### 本机裁判的前置条件

本仓库不打包 Codex CLI，也不假定作者电脑上的安装路径。工作台启动本机评分时按系统 `PATH` 查找 `codex`；如果 CLI 安装在非标准位置，可在启动工作台前设置 `CHB_CODEX_BIN` 为可执行文件的完整路径。先在同一个终端确认：

```powershell
codex --version
codex login status
```

应能看到 CLI 版本和已登录状态。登录可使用 Codex 支持的 ChatGPT 账户方式；也可以使用 API Key，但两种方式的额度/计费归属不同。当前机器若显示 `Logged in using ChatGPT`，评分使用当前 ChatGPT/Codex 账户的 Codex 限额，不是仓库自带额度。换一台机器必须自行安装、登录并确认模型可用；仓库不会替用户安装 CLI、登录账户或复制认证文件。未满足条件时，配置、题库、工作区准备和桌面执行仍可用，本机评分会明确报“未安装/未登录”，也可以改选 Docker 裁判。

本机评分默认选择 `gpt-5.6-luna`、推理档位 `max`；账户没有该模型时页面回退到可见的本机模型，仍需在评分页确认。模型可用不等于评分正确：每次评分都是一次新的无历史 Codex CLI 进程，结果可能因模型随机性、依赖和环境变化而不同，系统保存原始提示词、命令、输出和报告，不自动把一次结果当成稳定基准。

```powershell
uv venv --python 3.13
uv sync --frozen
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
.venv\Scripts\python.exe -X utf8 -m chb.cli ui
```

也可以双击 **launch-ui.cmd**。前端首次缺少构建时启动器会安装锁定依赖并构建。浏览器入口 **http://127.0.0.1:8765**，只监听本机。启动终端保持运行，Ctrl+C 关闭；可加 `--port 8766` 或 `--no-browser`。升级源码后重新执行前端 build。

Linux/macOS 使用 `.venv/bin/python`；当前真实操作验证以 Windows 为主。支持从源码仓库 editable 安装，独立 wheel 不包含完整题库和 React 构建，不作为完整应用分发。

**Docker 不是网站启动条件。** 配置、题库、桌面工作区准备、产物回收与历史浏览可不启动 Docker。评分可选本机 Codex 原生沙箱，复制回收产物后独立取证，使用当前登录账户的模型额度；本机模式不启动容器脚本。固定程序检查和 Harbor 裁判仍需 Docker 及对应镜像；尚未提供无需安装依赖的完整应用包。Docker 的数据盘位置由 Docker Desktop 管理，工作台通过 Docker CLI 连接当前引擎，无需在项目里填写磁盘路径。

遇到 `Failed to fetch` 或“无法连接本地工作台”：先确认启动进程仍在运行，再点“刷新记录”。服务重启后访问令牌会变化，需先保留未提交的表单内容，再重新加载页面。断连不等于项目执行或评分失败，也不自动删除落盘数据；先在评测历史核对回收版本和执行状态，避免重复提交。Codex 已生成的文件仍在独立工作区，尚未回收的成果可在桌面停止写入后点“回收产物”。

前端断连回归检查：`node --test frontend/tests/api.test.mjs`（先安装前端依赖）。

配置有两个方向：从Codex导入是保存工作台副本；配置管理的“保存并一键应用到Codex”会备份并写入本机设置，可撤销。模型/推理、原生白名单、AGENTS、Skills及已配置MCP/插件开关可应用；插件安装、认证、Hooks等不迁移。准备后也可应用本题冻结配置。新任务才使用新条件，项目覆盖与桌面实际值仍需核对。

## 一次评测怎么做

1. **配置管理**：左侧选配置，右侧分区编辑模型与规则、Skills、工具与原生设置、应用到 Codex。顶部“删除配置”移入左侧“回收站”，可恢复；历史评测和已经应用的宿主设置保留。保存为可追溯版本。
2. **题库中心**：项目构建与 Bug 修复分开。可编辑故事/接口/数据/验收契约，导入JSON题包，设置多轮提示词与检查；“保存并用于评测”直接带入该题。
3. **工作台**：默认单配置单题，只选择并预览已保存配置；导入在配置管理完成。技能在统一面板勾选即选用，配置内容独立预览。评分页显示机器评分维度、权重与依据，按底部下一步完成准备，最后创建并冻结输入、策略及独立工作区；不会自动调用模型。
4. **在 Codex 桌面打开**该目录，核对模型和推理档位，复制当前提示词发送。第一轮新建任务，后续轮次继续同一任务。工作台按精确工作区自动发现原生会话，不必回来手动“记录开始”；检测不到时仍可导入日志。
5. **本轮结束后回收**：保存真实文件、新增/删除/修改事实及回复说明。需要下一轮时，先回收再明确确认。
6. **评分**：选择裁判模型与“本机 · 无需 Docker”，点击自动检查并评分。独立 AI 读取副本、尝试构建/测试/交互，按通用维度和原始需求返回带引用的分数。无专用脚本也能发起；验证不了的项为空。人工按需修正分项，原分、证据和历史保留。选择 Docker 时可先运行已声明的容器脚本。
7. **结束与历史**：完成全部阶段后标记交付结束。查看当时配置、快照和复审；可导出 ZIP、归档/恢复、将历史配置恢复为新副本。

没有模型用量时显示“—”。页面活动时，服务只查询与本题工作区匹配的 Codex 会话索引并读取对应日志；也可手动导入原生 JSONL。服务校验工作区与会话，读取最终累计 Token 和可确认的活动时长；缓存包含在输入中，不额外重复加总。费用不估算。

## 题目和检查

初始包含 **31 份 Gemini 题面**（14份项目构建、17份缺源码的修复题面），另自动提供3套原创题包。题库和工作台默认只展示“可开始”题目，18份缺源码题面（17份修复、1份重构）放在“待补全”，不能开始修复评测；不能宣传成31套已验证测试。参考 URL 不会自动克隆，原型里的建议命令不冒充可执行验收。可以导入本地源码起点，或在题库输入公开 GitHub 仓库和完整 commit SHA 下载源码，再保存题目版本。修复题没有起点会阻止准备；从零构建题可以从空目录开始。下载不等于依赖/数据库/外部服务已经准备完成。

体验新契约流程可在题库“导入JSON题包”选择[原创人工题包示例](catalog/examples/contract-task.json)，先预览再导入新副本。它没有脚本检查，可使用默认机器评分；示例不是正式桌面成绩或已校验完整项目题。新评测提示词只冻结原始需求和当前阶段，不再注入完整内部验收契约。改题库不会改变旧评测。

启动时自动提供三道原创题：笔记搜索修复、存储演进、CSV 导入修复，不需要用户手工导入。创建评测自动复制各自源码、既有测试和规则到独立目录；参考解和独立验收器不进入该目录。它们使用 Python 标准库，开发及本机裁判不需要 Docker；下列镜像只用于可选的独立脚本验收：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task storage-migration-v1
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task csv-catalog-v1
```

自定义检查采用参数数组，例如镜像 `chb-verifier:search-notes-v1`，参数 `["python", "-I", "/tests/verify.py", "/app"]`。检查在无网络容器的快照副本执行，不运行宿主脚本。默认只验收最终阶段；可指定检查属于第几轮。可勾选最终交付再次运行早期检查；最终快照必须有新执行证据。超时/环境错误/取消不是题目失败。

Docker 裁判首次需执行 `.venv\Scripts\python.exe -X utf8 scripts/prepare_arena_review.py` 准备独立镜像（不调用模型）。

机器裁判可以使用本机原生沙箱或 [Harbor](https://github.com/harbor-framework/harbor) 容器，均标为 `cli-review-only`，与正式桌面执行区分。它返回机器分和引用，人工修正另存；引用存在不意味着判断必然正确。前端交互分要求实际运行证据，不能仅从源码保证视觉效果。本机 CLI 合成题已实跑；浏览器交互评分的本轮实跑被裁判额度不足中断，尚未通过。

## 如何读分数

新评测使用机器先评、人工修正。默认维度为需求50%、健壮性20%、交互15%、交付10%、维护5%，可调整；这是产品起点，不是行业统一权重。程序检查提供通过/失败证据，连续分由裁判按评分锚点综合判断。非界面题排除交互维度，剩余权重归一。必要项结论单列，不能用高视觉分掩盖业务失败。

旧记录保留当时的客观/人工比例；新评测不要求人工占50%。机器覆盖率表示已有评分的维度权重，不是测试覆盖率。所有适用项有有效分且结束交付才形成最终分；缺项显示暂定分。策略冻结后不改旧结果。没有预设高分、全局总榜、固定误差或统计显著性承诺。

独立目录是工作区规则叠加层，**仍继承桌面全局规则、技能和插件**，不是全局隔离。宿主指纹只覆盖部分文件。即使同条件分组，也不能把一次差异视为微小 Harness 改动的可靠收益。

## 数据与历史

`.local/arena/` 保存 SQLite、导入快照、独立工作区、产物、私有原生日志和审查记录；原 CLI 实验在 `runs/`。二者都不提交 Git。前端 localStorage 只存外观偏好。

回收忽略依赖目录、Git 元数据并排除凭据；链接和超限文件明确报错。单文件8 MB，单快照50 MB/5000文件。导出 ZIP 包含私有规则与产物、最大200 MB，不含认证和原生完整日志；不会自动发布。哈希可发现意外修改，不是防恶意篡改的数字签名。

旧 CLI 的冻结、容器运行与历史分析仍保留为独立辅助路径：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli doctor
.venv\Scripts\python.exe -X utf8 -m chb.cli plan --model openai/gpt-6-astra
.venv\Scripts\python.exe -X utf8 -m chb.cli run runs/<实验编号>
.venv\Scripts\python.exe -X utf8 -m chb.cli report runs/<实验编号>
.venv\Scripts\python.exe -X utf8 -m chb.cli analyze runs/<实验编号>
```

`run` 会使用模型额度；`analyze` 新建派生报告、不改原实验。完整旧合同保存在 [历史说明](docs/archive/2026-09-13-README.md)，其中 F1/F2 规划已由新架构替代。

## 开发与验收

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q src scripts tests
pnpm --dir frontend build
.venv\Scripts\python.exe -X utf8 scripts/validate_arena.py
```

`validate_arena.py` 默认仅做工作台与容器验收，不调用模型；只有明确传入 `--judge-model <model>` 才启动一次有时限的辅助 AI 审查。测试记录只写 `.local/arena-validation/`。前端操作请使用 Python 同源服务；Vite 静态预览不等于已连接后端。

[需求记录](docs/requirements.md) · [主架构与路线](docs/PROJECT_SPEC.md) · [前端合同](docs/FRONTEND_SPEC.md) · [当前交接](docs/当前交接.md)
