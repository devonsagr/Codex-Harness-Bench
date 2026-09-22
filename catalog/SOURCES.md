# 公开题源索引

`public-task-sources.json` 记录 DeepSWE 113份task.toml中的任务标识、标题、语言、目标仓库和base commit，并生成固定版本的题面/环境/验收器链接。核对日期2026-09-21，来源[datacurve-ai/deep-swe](https://github.com/datacurve-ai/deep-swe/tree/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea)，版本`0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`。

题目元数据来自 Datacurve AI Inc. 的 DeepSWE，许可证 [Apache-2.0](DEEPSWE-LICENSE.txt)。本项目提取元数据、增加链接和接入状态；不包含目标工程源码、参考解或验收测试。各目标工程沿用自身许可证，适配或再分发时还须核对[上游PROVENANCE](https://github.com/datacurve-ai/deep-swe/blob/0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea/PROVENANCE.md)。

`public-task-files.json` 是同一固定版本中113题、904个题面/环境/验收文件的路径与SHA-256索引，由已核对的上游定义包生成，不含文件正文或solution。按题下载时逐文件验证，只获取所选题的材料；目标工程仍按独立base commit下载并冻结。原分类为4个bugfix、106个feature_request、3个enhancement。

`status=indexed-not-adapted` 表示已查阅来源，尚不能在本工作台直接运行。不启动网络下载、环境安装、领题或评分，不计入本地可开始题目。公开任务适配合同见[题库架构](../docs/architecture/TASKS_AND_CONTRACTS.md)。

上游三项base ref为缩写：eicrud-keyset-pagination-cursor、koota-entity-snapshot-rollback、langchain-request-coalescing。已于2026-09-21通过对应目标仓库公开GitHub commits API解析完整SHA，baseCommit保存解析值，sourceBaseRef保留原始值；未替换为分支最新提交。其他项沿用上游完整SHA，未声称全部目标仓库已下载或实跑。
