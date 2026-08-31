# PR 记录：统一 Next.js + FastAPI 架构

> 相关提交：`58ee90f 清理 Gradio 入口统一 NextJS FastAPI`、`8655e90 更新 NextJS FastAPI 架构文档`、`67afb5e fix: align setup with Next.js FastAPI stack`
>
> 本文记录已完成的架构清理与验证结果。

## 背景

项目已采用独立 Next.js 前端。随着学习路线、节点详情、复习、测验、RAG 问答和模型配置等能力增加，原有 Gradio 页面回调不再适合作为交互入口，也不利于前端独立演进和 HTTP 契约维护。

本 PR 将运行路径统一为 Next.js + FastAPI，同时继续复用 Kotaemon 的 SQLite、LLM 和 RAG 基础设施。项目侧 Gradio 入口已删除。

## 前端效果

![Next.js 学习工作台](https://raw.githubusercontent.com/Aeside1/learn-everything/feature/nextjs-fastapi-migration/docs/assets/pr-frontend-workbench.png)

## 架构调整

```text
Next.js 浏览器前端
  开发环境：http://127.0.0.1:3000
  构建产物：frontend/out
        |
        | REST / SSE
        v
FastAPI API
  /api/v1/*
        |
        v
learning_ext/application
  项目、路线、节点学习、复习、测验、资料、RAG、配置等用例编排
        |
        v
Kotaemon 基础设施
  SQLite / SQLModel、LLM 配置与调用、文档索引、RAG
```

## 本次改动

- 完成前端独立化、后端 API 化和业务层解耦：以 Next.js 提供学习工作台，以 FastAPI 提供统一的 `/api/v1` 接口，并将学习业务集中到可复用的 `learning_ext` 应用层；前端按学习领域拆分功能模块，覆盖项目管理、学习路线、节点详情、复习、RAG 问答、测验、看板和模型配置。
- 补充前后端通信、错误处理、请求追踪和测试支持，保留现有数据、LLM 和 RAG 基础设施，不引入数据迁移。
- 统一初始化脚本和项目启动脚本，使其适配新的运行方式，负责准备 Python、桌面和 Next.js 依赖，并启动 Next.js 与 FastAPI.
- 同时移除项目侧 Gradio 入口和页面装配代码，桌面 exe 与便携版统一通过 FastAPI 托管 Next.js 静态资源。

## 验证

### 前端验证

- `npm run test`、`npm run typecheck` 和 `npm run build` 均通过。
- 已完成正式 Rust 项目的项目切换、六个工作区标签、路线节点详情进入/返回及 390px 窄屏回归。

### 后端验证

- FastAPI API、`learning_ext` application、RAG 适配和请求编号链路已有测试覆盖。
- 已验证 Next.js 到 FastAPI 再到 `learning_ext` 的主要调用链，以及空项目等边界状态。

### Desktop 打包运行验证

- 已完成 `build_exe.bat` 打包和 `pack_portable.bat` 便携版组装。
- 已验证便携版 FastAPI 静态页面 `/` 和 `/api/v1/projects` 均返回 200。
- 已使用 `LE_DESKTOP=1` 验证 PyWebView 窗口打开、页面加载和关闭后的进程退出。

## 建议评审顺序

1. 阅读 `docs/ARCHITECTURE.md`，确认运行路径和职责边界。
2. 阅读 `api/main.py`、`api/routers/` 和 `api/schemas/`，确认 HTTP 接入层范围。
3. 阅读 `learning_ext/application/`，确认业务用例与 FastAPI 表现层解耦。
4. 阅读 `frontend/README.md`，再查看 `frontend/lib/api.ts` 与 `frontend/features/`，确认 API 契约和前端模块边界。
5. 阅读 `scripts/start_frontend_dev.py`、`launcher.py`、构建脚本和测试，确认浏览器运行、桌面交付和回归覆盖。
