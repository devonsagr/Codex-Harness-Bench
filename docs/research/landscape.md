# 现有实现核查与底座选择

查阅日期：2026-09-12。结论来自官方文档、GitHub README、API 元数据和 Harbor 本地安装源码；“支持”与本项目运行验收分开。此前原文明确未联网，本文件补上实际调查。

## 最接近的项目

|项目与一手来源|查阅版本 / 许可|与本项目的关系和缺口|
|---|---|---|
|[Harbor](https://github.com/harbor-framework/harbor)、[agent 文档](https://www.harborframework.com/docs/agents)|本机安装 0.23.0；源码 main `d8cfe6b6fd463fc1f2a84abf8f1406f46e70c621`；Apache-2.0|Codex adapter 有原生配置、skills、认证文件注入、轨迹和 resume；单独验收环境与网络控制可复用。采用其执行层；项目补全局指令装载、配置快照与对比报告。|
|[SkillsBench](https://github.com/benchflow-ai/skillsbench)|`9a1f4dd5f7659f75707435da3ce854b6e48321d1`；Apache-2.0|直接研究 skills 对任务表现的影响，提供任务和确定性验收。适合作为方法和未来题源；本项目强调个人 Codex 配置历史、恢复及工程迭代。未复制数据集。|
|[SunChJ/skillbench](https://github.com/SunChJ/skillbench)|`d05557e1370704fda56aebf587bd7ca51cc8571f`；未发现仓库声明许可证|高度接近：冻结 Codex skill、隔离会话、保存轨迹/产物/验收/用量、本地文件。要求 POSIX shell 和 Rust；README 将验收命令放工作区，独立验收边界仍需审查。参考产品设计，不复制未明确授权源码。|
|[helloJamest/SkillBench](https://github.com/helloJamest/SkillBench)|`c6ab19aaf7fd1623b987f590707ae6aee0f2a82b`；MIT|提供 Codex skill 评测、judge/full-agent 路径、报告和自动改进。覆盖面较大；不将其主观评审流程作为本项目交付正确性的唯一依据。|
|[eth-sri/agentbench](https://github.com/eth-sri/agentbench)|`da299c4c6b14a9abad2ceef8c751f6c45c543656`；MIT|与仓库上下文/AGENTS.md 有关的研究实现，适合调查指令影响的实验方法。未在本机执行。|
|[SWE-bench](https://github.com/SWE-bench/SWE-bench)|main 文档；MIT（工具）|真实修复题和 Docker 验收基础。公开 Lite 子集为后续接入项，先逐题验证与记录许可证，不能把自选子集冒充官方全量分数。|
|[Terminal-Bench](https://www.tbench.ai/)、[论文](https://arxiv.org/abs/2601.11868)|官方 2.0 资料|终端任务与独立验收设计可借鉴，Harbor 为其评测底座。不是本项目首轮小题，也不直接替代配置历史管理。|
|[Inspect AI](https://inspect.aisi.org.uk/)、[源码](https://github.com/UKGovernmentBEIS/inspect_ai)|官方文档 / main；MIT|通用 task/solver/scorer 与日志工具。首版不同时引入第二个编排框架；没有完成其 Codex 实测。|
|[Stet 方法](https://www.stet.sh/methodology)|2026-09-12 网页；未核实开源许可|明确支持真实仓库回放和配置/指令变化的比较，证明该需求已有产品重叠。未据此声称提供可直接复用的开源 runner。|

上述活跃度只核对 GitHub archived=false 与最近推送，不能据此推断成熟度。SkillsBench/SunChJ/helloJamest 名称相近，不能混为同一项目。

## 未确认项

- SWE-Skills-Bench 论文搜索结果提到 `GeniusHTX/SWE-Skills-Bench`，本次 GitHub API 返回 404。仅作为待核实线索，不给出虚假的 commit 或许可，也不采用为依赖。
- [众测雷达](https://deng.codexradar.com/)已打开查看。其视觉任务不能当作软件工程题；本项目不宣称使用“同款 DeepSWE 题库”。
- 没有穷尽所有 GitHub 项目，不能宣称市场空白。

## 为什么选 Harbor

安装的 0.23.0 源码可确认：`Codex._load_base_config` 读原生配置，`_build_effective_config` 合并运行输入，`_upload_effective_config` 上传配置；`_resolve_auth_json_path` 允许显式注入认证文件；`_build_register_skills_command` 向独立 HOME 注册 skills；Trial 的 artifact handler 支持将完整候选目录送入 separate verifier。

固定执行依赖一个框架，可直接继承容器回收、超时、日志、异常和验收。新增 adapter 只做 profile 装载与证据，不拷贝上游 1,400 多行 Codex 实现。

本机 Linux Docker 引擎初始未运行，已通过 Docker Desktop 启动。Harbor 安装在项目 `.venv`，不替换全局 Codex。后续实测结果只写入 [当前交接](../当前交接.md)，不在调研表提前宣称通过。

## 头脑风暴结论

最清晰的产品入口是“比较我改前和改后的配置”。首页优先展示变化项、是否生效、验收证据和全部失败；配置收藏/恢复比早期总榜更实用。

长远可以建立两条分开的题库：公开维护题负责可比性，公开多轮替换题负责用户最关心的遗留清理。新增严肃能力之前先做好可信的实验记录；不要以一个单题冠军驱动配置推荐。
