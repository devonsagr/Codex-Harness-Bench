# Codex Harness Bench

在 Codex 桌面中执行真实需求，检查自己的 AGENTS、技能和交互约定如何影响交付。默认一套配置、一道项目构建题；可选对比，Bug 修复单独分类。

以用户提供的 Gemini React 前端为输入，目前已实现本地 Python / SQLite 基础链路：配置版本、技能和起点导入、独立工作区、逐轮回收、客观检查、AI辅助审查、人工评分、历史与导出。**Gemini的产品功能尚未全部接入**：已接项目契约、逐项验收、题包导入与筛选；本轮补配置应用/撤销、全宽准备与自定义评分；配置差异矩阵、完整历史复用与异常恢复仍有缺口。具体对照见[Gemini审计](docs/architecture/GEMINI_ALIGNMENT.md)，不要将基础测试通过理解为整个产品完成。

架构文档从[阅读索引](docs/README.md)进入；[总架构第8节](docs/PROJECT_SPEC.md#8-唯一实施路线与完成标准)给出逐包后端完成路线，[前端合同](docs/FRONTEND_SPEC.md)说明页面与交互，[当前交接](docs/当前交接.md)记录版本和实测范围。

## 启动

需要 Python 3.12+、uv、Node.js 和 pnpm。桌面执行需已安装并登录 Codex；只有容器检查和 AI 审查需要 Docker Linux 引擎。

```powershell
uv venv --python 3.13
uv sync --frozen
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
.venv\Scripts\python.exe -X utf8 -m chb.cli ui
```

也可以双击 **launch-ui.cmd**。前端首次缺少构建时启动器会安装锁定依赖并构建。浏览器入口 **http://127.0.0.1:8765**，只监听本机。启动终端保持运行，Ctrl+C 关闭；可加 `--port 8766` 或 `--no-browser`。升级源码后重新执行前端 build。

Linux/macOS 使用 `.venv/bin/python`；当前真实操作验证以 Windows 为主。支持从源码仓库 editable 安装，独立 wheel 不包含完整题库和 React 构建，不作为完整应用分发。

配置有两个方向：从Codex导入是保存工作台副本；配置管理的“保存并一键应用到Codex”会备份并写入本机设置，可撤销。模型/推理、原生白名单、AGENTS、Skills及已配置MCP/插件开关可应用；插件安装、认证、Hooks等不迁移。准备后也可应用本题冻结配置。新任务才使用新条件，项目覆盖与桌面实际值仍需核对。

## 一次评测怎么做

1. **配置管理**：编辑 AGENTS 内容，选择模型/推理档位，明确导入技能目录，填写个人约束。保存为可追溯版本。
2. **题库中心**：项目构建与 Bug 修复分开。可编辑故事/接口/数据/验收契约，导入JSON题包，设置多轮提示词与检查；“保存并用于评测”直接带入该题。
3. **工作台**：默认单配置单题，只选择并预览已保存配置；导入在配置管理完成。技能在统一面板勾选即选用，配置内容独立预览。评分页显示实际检查方案与人工内部百分比，按底部下一步完成准备，最后创建并冻结输入、策略及独立工作区；不会自动调用模型。
4. **在 Codex 桌面打开**该目录，核对模型和推理档位，复制当前提示词发送。第一轮新建任务，后续轮次继续同一任务。工作台的“记录开始”不代替发送。
5. **本轮结束后回收**：保存真实文件、新增/删除/修改事实及回复说明。需要下一轮时，先回收再明确确认。
6. **验收**：运行已声明容器检查；按需启动会使用模型额度的 AI 辅助审查；实际查看交付物后逐项记录状态与各维评分依据。自动原分可附理由/证据作人工裁定，原分和失败记录保留。必要项结论与分数分开，三类证据分开保存；无脚本题可明确选纯人工，通用检查命令可在题库复用。
7. **结束与历史**：完成全部阶段后标记交付结束。查看当时配置、快照和复审；可导出 ZIP、归档/恢复、将历史配置恢复为新副本。

没有模型用量时显示“—”。可以明确导入该桌面任务的原生 JSONL，服务校验工作区与会话，读取最终累计 Token 和可确认的活动时长；缓存包含在输入中，不额外重复加总。费用不估算。

## 题目和检查

初始包含 **31 份 Gemini 题面**，不是31套已验证测试。参考 URL 不会自动克隆，原型里的建议命令不冒充可执行验收。可以导入自己的起点、设置检查镜像与命令参数，或只作人工复审。

体验新契约流程可在题库“导入JSON题包”选择[原创人工题包示例](catalog/examples/contract-task.json)，先预览再导入新副本。它没有脚本检查，准备前需明确选择纯人工策略；示例不是正式桌面成绩或已校验完整项目题。每轮提示词由后端冻结，包含总体需求、完整契约和当前阶段。改题库不会改变旧评测。

题库按钮“导入项目的 3 道完整原创题”提供笔记搜索修复、两轮存储演进、CSV 导入修复。只把起点交给桌面，参考解和验收器留在工程目录。准备对应镜像：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task storage-migration-v1
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task csv-catalog-v1
```

自定义检查采用参数数组，例如镜像 `chb-verifier:search-notes-v1`，参数 `["python", "-I", "/tests/verify.py", "/app"]`。检查在无网络容器的快照副本执行，不运行宿主脚本。默认只验收最终阶段；可指定检查属于第几轮。可勾选最终交付再次运行早期检查；最终快照必须有新执行证据。超时/环境错误/取消不是题目失败。

AI 审查首次需执行 `.venv\Scripts\python.exe -X utf8 scripts/prepare_arena_review.py` 准备独立镜像（不调用模型）。

AI 审查使用 [Harbor](https://github.com/harbor-framework/harbor) 的隔离 Codex CLI，标为 `cli-review-only`，与正式桌面执行区分。它引用实际文件行，只作为建议；引用存在不意味着判断必然正确。它不能自动给人工分，不能在未运行测试时宣称通过，也不能仅从源码保证视觉效果。

## 如何读分数

客观分是适用检查的通过权重比例。多轮按每一阶段最新快照的检查汇总；任何要求的检查未执行或遇到环境错误时保持未知。新人工量表默认七项：需求完成、可维护性、健壮性、适用的交互与可访问性、验证与回归、规则遵守、交付可复现性。可增删、调整权重，添加安全/性能或自定义项；0–100、支持小数、必须说明依据。旧记录仍使用原四项。个人约束另列满足情况与依据。题目必要项未满足时，即使数值高分也不会显示必要项通过。

默认客观50% + 人工50%可在创建前调整，是产品约定。无脚本题可选择纯人工。策略冻结后不改旧结果；必要证据不齐或未结束交付，总分为空。没有预设高分、全局总榜、固定误差或统计显著性承诺。

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
