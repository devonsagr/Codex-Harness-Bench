# Gemini 前端工程副本

本目录基于用户在 2026-09-15 提供的 Gemini 前端，保留导航、主题与卡片风格，将模拟业务替换为本机 `/api/arena`。

```powershell
pnpm install --frozen-lockfile
pnpm build
cd ..
.venv\Scripts\python.exe -X utf8 -m chb.cli ui
```

使用 http://127.0.0.1:8765 的 Python 同源服务。`pnpm dev` / `pnpm preview` 仅用于静态构建调试，不提供后端令牌或真实操作环境。

架构、接口与页面责任见 [前端合同](../docs/FRONTEND_SPEC.md) 和 [主架构](../docs/PROJECT_SPEC.md)。原型模拟器及虚构命令已从活动源码移除；完整输入来源目录保持只读，来源哈希回执存于项目 `.local/sources/`。
