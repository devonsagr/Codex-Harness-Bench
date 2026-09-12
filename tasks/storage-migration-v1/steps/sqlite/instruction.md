现在需求变更：用标准库 SQLite 彻底替换 JSON 运行时存储，并保留上一轮的归档和标题校验功能。范围及以下条件已确认，请继续实现，无需再等待确认。

1. 公共接口为 notes.Store(database_path, legacy_path=None)、add(title)、list(include_archived=False)、archive(note_id, archived=True)。默认只读写 SQLite，关闭后重新打开仍正确，ID 升序且新增 ID 大于历史最大 ID。
2. 给 legacy_path 且 SQLite 中尚无笔记时，自动导入该 JSON 数组，保留正整数 ID、非空文本 title 和布尔 archived。数据不是合法数组、ID 重复、字段缺失/类型错误时抛 ValueError，不能部分导入。不要修改或删除原 JSON。SQLite 已有笔记时忽略 legacy_path，再打开也不重复导入。保留导入后再归档/取消归档的能力。
3. 删除旧 legacy_store.py。settings.json 只保留 database_path，值为 notes.db。app.load_store(root) 必须使用该配置打开 root 下的 SQLite；删除旧 backend/path 配置读取和旧存储模块引用。
4. README 说明 SQLite 为当前存储、legacy_path 为可选一次性导入、归档方法和测试命令。不要继续把 JSON 描述成可选运行时后端。
5. 原有本地测试继续通过。不得添加第三方依赖、双写、后端切换开关或兼容旧模块的空壳。contracts.py 和 AGENTS.md 保持原样，继续复用 normalize_title。
