请完成 `ledger.py` 中的 `reconcile(rows)`，实现收费和退款的逐笔核对。保留现有 `parse_amount` 与 `summarize` 的公开接口，仅使用 Python 标准库。`rows` 是按发生顺序排列的字典列表，每行有唯一业务 `id`、`customer`、`kind`（`charge` 或 `refund`）、金额字符串 `amount`；退款另有 `ref` 指向先前有效的收费单号。

金额必须大于 0 且最多两位小数；计算使用 Decimal，输出固定两位小数。相同业务 `id` 第二次出现时记 `DUPLICATE`，不重复计入；退款若引用不存在或尚未出现的有效收费，记 `UNKNOWN_REFERENCE`；退款客户不等于原收费客户，记 `CUSTOMER_MISMATCH`；累计退款超过原收费金额，记 `OVER_REFUND`；金额不合法，记 `INVALID_AMOUNT`。一个错误行只记最先适用的错误，优先顺序为重复编号、金额、引用、客户、超额。无效行不得改变余额或可退款额度。

返回 `{ "balances": {客户名: "净金额"}, "exceptions": [{"index": 从0开始的行号, "code": 错误码}] }`。余额按客户名称排序，异常按输入顺序；只列发生过有效交易的客户，包括余额归零者。不得修改输入记录。请保留现有测试可运行，并补充自己认为重要的边界测试。
