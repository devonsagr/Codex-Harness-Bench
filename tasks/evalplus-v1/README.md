# HumanEval+ 桌面适配

来源：[EvalPlus](https://github.com/evalplus/evalplus)，数据release采用Apache-2.0，固定提交和SHA见 `src/chb/arena/evalplus_source.py`。上游数据、测试和参考解仅下载到本地缓存，不随本仓库分发。接口 `/sources/evalplus` 导入163道通过验收器资格检查的函数题；32号导出已发现问题，排除而不修改上游断言。桌面起点只有原签名和题面，不含参考解及隐藏测试。

`tests/Dockerfile` 的 `tests.json` 由受校验的本地缓存构建，不是缺失的公开资产。使用现有容器检查接口，禁网且只读挂载本次快照，在容器副本运行 `solution.py`。程序通过不依赖AI；预算耗尽保持未知。本地Python/预算/生成协议不同，不提供官方排行榜或pass@k。

验证器本身属于CHB本地适配，不是上游EvalPlus运行器。完整研究及实测范围见 `docs/research/community-tasks-and-fixed-scoring-20261001.md`。
