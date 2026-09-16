# 架构入口

本仓库唯一总架构和实施路线是 [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)，工作包状态在第8节；本文只作根目录入口。

- [Gemini 架构与当前实现的对照](docs/architecture/GEMINI_ALIGNMENT.md)：第8节逐项回应 Gemini `ARCHITECTURE.md` 第7节的数据库及接口方案。
- [当前 SQLite 和真实 API 合同](docs/architecture/DATA_AND_API.md)：包含现有路由、题包导入、契约版本、冻结提示词和逐项验收字段。
- [前端合同](docs/FRONTEND_SPEC.md)与[后端完成合同](docs/architecture/BACKEND_DELIVERY.md)：功能连接、实现边界和验收要求。
- [当前交接](docs/当前交接.md)：本轮验证、版本和剩余工作。

工程采用 Python 轻量后端和 React 前端，沿用已有版本数据库。正式执行按用户已确定的 Codex 桌面工作流；CLI 辅助审查独立标记。Gemini 的模拟执行与示例接口不被当作已实现功能。
