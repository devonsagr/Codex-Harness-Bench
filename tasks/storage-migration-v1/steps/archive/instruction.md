请在 /app 的现有笔记项目上增加归档功能。目标、范围和下面的验收条件都已确认，直接实施即可，无需等待再次确认。若环境提供 brainstorming skill，请读取并使用它来确认范围已经足够清楚，然后继续实施；没有该 skill 则正常完成。

公开接口维持 notes.Store(path)、add(title)、list(include_archived=False)。新增 archive(note_id, archived=True)，允许归档和取消归档；不存在的 ID 抛 KeyError。
归档状态必须写入当前 JSON 存储，重新打开仍生效。list() 默认隐藏已归档笔记；list(True) 包含全部并保持 ID 升序。add() 和 list() 返回的字典不得引用可被调用方改写的内部状态。继续复用 contracts.normalize_title，拒绝空白或非文本标题。
保留原有测试与接口，更新 README 中的归档用法。不添加依赖、框架、后台服务或额外项目流程文档。不改 contracts.py 和 AGENTS.md。
