修复 /app 中的产品目录 CSV 导入工具。目标、范围和以下验收条件均已确认，请直接完成，不需要另行等待确认。

保留 iter_products(source)、import_catalog(source_path, destination_path) 和 python -m catalog 的公开入口，仅用 Python 标准库。

1. iter_products 接收可逐行迭代的文本输入，惰性产出字典 {sku, name, quantity}。用标准 CSV 规则处理引号、字段内逗号、字段内换行及 CRLF，支持 UTF-8 BOM。标题行必须且只能含 sku、name、quantity，各一次，顺序可变。空文件或错误表头抛 ValueError；只有表头的文件产出空序列，跳过完全空白的物理空行。
2. 必须复用 validation.normalize_sku 和 validation.parse_quantity；name 去除两端空白且不可为空，保留内部换行和 Unicode。规范化后的 SKU 在整个文件内必须唯一；多列、少列、空字段、非法数量、重复 SKU 或未闭合引号都抛 ValueError。不能用 read()/readlines() 或预先把整个源文件装进列表；读取首条产品不应消耗后面的产品。
3. import_catalog 从 UTF-8 CSV 文件导入 UTF-8 JSONL（每行一个上述字典，quantity 为整数），顺序与输入一致，返回产品数。目标父目录已存在。只有全部输入成功验证后才原子替换目标；任何解析错误必须保留已有目标的原始字节，若原本无目标则不能留下半成品。成功和失败都不遗留临时文件，不修改源文件。源和目标为同一路径时在写入前抛 ValueError。
4. CLI 接受 source destination 两个参数：成功退出 0 并输出 Imported N products；数据错误退出 2，说明写 stderr，不能有 Python traceback，目标仍完好。既有调用和测试继续通过，README 更新使用方式和原子写入保证。
5. 不改 validation.py、AGENTS.md 或已有测试，不增加依赖、数据库、后台进程、配置开关或额外项目流程文档。
