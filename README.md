# Codex Harness Bench

在 Codex 桌面中执行真实需求，检查自己的 AGENTS、技能和交互约定如何影响交付。默认一套配置、一道项目构建题；可选对比，Bug 修复单独分类。

前端采用用户提供的 Gemini React 方案，已接入本地 Python / SQLite 后端。当前支持配置版本、技能和题目起点导入、独立工作区、逐轮回收、客观检查、独立 AI 辅助审查、人工评分、历史恢复与导出。具体实测范围见 [当前交接](docs/当前交接.md)，整体逻辑与进度见 [主架构](docs/PROJECT_SPEC.md)。

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

## 一次评测怎么做

1. **配置管理**：编辑 AGENTS 内容，选择模型/推理档位，明确导入技能目录，填写个人约束。保存为可追溯版本。
2. **题库中心**：项目构建与 Bug 修复分开。可新建需求，设置多轮提示词，明确导入起点文件夹，声明验收检查。
3. **工作台**：默认单配置单题。创建后冻结输入、策略并生成独立工作区；不会自动调用模型。
4. **在 Codex 桌面打开**该目录，核对模型和推理档位，复制当前提示词发送。第一轮新建任务，后续轮次继续同一任务。工作台的“记录开始”不代替发送。
5. **本轮结束后回收**：保存真实文件、新增/删除/修改事实及回复说明。需要下一轮时，先回收再明确确认。
6. **验收**：运行已声明容器检查；按需启动会使用模型额度的 AI 辅助审查；实际查看交付物后填写人工评分。三类证据分开保存。
7. **结束与历史**：完成全部阶段后标记交付结束。查看当时配置、快照和复审；可导出 ZIP、归档/恢复、将历史配置恢复为新副本。

没有模型用量时显示“—”。可以明确导入该桌面任务的原生 JSONL，服务校验工作区与会话，读取最终累计 Token 和可确认的活动时长；缓存包含在输入中，不额外重复加总。费用不估算。

## 题目和检查

初始包含 **31 份 Gemini 题面**，不是31套已验证测试。参考 URL 不会自动克隆，原型里的建议命令不冒充可执行验收。可以导入自己的起点、设置检查镜像与命令参数，或只作人工复审。

题库按钮“导入项目的 3 道完整原创题”提供笔记搜索修复、两轮存储演进、CSV 导入修复。只把起点交给桌面，参考解和验收器留在工程目录。准备对应镜像：

```powershell
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task storage-migration-v1
.venv\Scripts\python.exe -X utf8 -m chb.cli prepare --checks-only --task csv-catalog-v1
```

自定义检查采用参数数组，例如镜像 `chb-verifier:search-notes-v1`，参数 `["python", "-I", "/tests/verify.py", "/app"]`。检查在无网络容器的快照副本执行，不运行宿主脚本。默认只验收最终阶段；可指定检查属于第几轮。超时/环境错误/取消不是题目失败。

AI 审查首次需执行 `.venv\Scripts\python.exe -X utf8 scripts/prepare_arena_review.py` 准备独立镜像（不调用模型）。

AI 审查使用 [Harbor](https://github.com/harbor-framework/harbor) 的隔离 Codex CLI，标为 `cli-review-only`，与正式桌面执行区分。它引用实际文件行，只作为建议；引用存在不意味着判断必然正确。它不能自动给人工分，不能在未运行测试时宣称通过，也不能仅从源码保证视觉效果。

## 如何读分数

客观分是适用检查的通过权重比例。多轮按每一阶段最新快照的检查汇总；任何要求的检查未执行或遇到环境错误时保持未知。人工分包括需求完成与切中度、可维护性、健壮性、适用时的交互与视觉，0–100、支持小数、必须说明依据。个人约束另列满足情况。

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
