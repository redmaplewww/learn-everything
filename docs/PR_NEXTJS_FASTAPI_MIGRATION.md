# PR 记录：统一 Next.js + FastAPI 架构

> 提交：`58ee90f 清理 Gradio 入口统一 NextJS FastAPI`
>
> 本文记录已完成的架构清理与验证结果。

## 背景

项目已采用独立 Next.js 前端。随着学习路线、节点详情、复习、测验、RAG 问答和模型配置等能力增加，原有 Gradio 页面回调不再适合作为交互入口，也不利于前端独立演进和 HTTP 契约维护。

本 PR 将运行路径统一为 Next.js + FastAPI，同时继续复用 Kotaemon 的 SQLite、LLM 和 RAG 基础设施。项目侧 Gradio 入口已删除。

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

- Next.js 是默认前端；前端通过 `frontend/lib/api.ts` 调用 FastAPI。
- FastAPI 仅负责 HTTP 接入、DTO、错误映射、SSE 响应和静态前端托管，不承载学习业务规则。
- `learning_ext/application` 是客户端无关的应用层，供 FastAPI 调用。
- 开发环境由 `start.bat` 启动 Next.js（3000）和 FastAPI（8000）；生产构建/桌面兼容路径由 FastAPI 同源托管 `frontend/out`。
- 桌面 exe 和便携版交付链路继续保留，统一启动 FastAPI 并托管 Next.js 静态资源。

## 本次改动

### 后端与业务边界

- 新增 `api/` FastAPI API 层和 `/api/v1` 路由，覆盖项目、路线、节点、复习、测验、看板、资料、RAG 问答和模型配置。
- 新增 `learning_ext/application/`，承载供 FastAPI 调用的界面无关业务用例。
- 增加 Kotaemon RAG 适配层，并为请求透传 `X-Request-ID` 和关键路线操作日志。
- 保持 SQLite 数据、LLM 配置、文档索引和 RAG 基础设施不变；本 PR 不引入数据迁移。

### 前端工作台

- 新增 Next.js + React + TypeScript 单页学习工作台，并使用静态导出交付。
- 通过项目栏提供项目选择、新建、编辑和删除；删除仍要求显式确认。
- 覆盖学习概览、学习路线、节点详情、到期复习、RAG 问答、查漏测验和模型配置六类工作区能力。
- 保留 REST/SSE 接口调用和现有视觉风格，未在模块化过程中重设计业务流程或 API 契约。
- 将原本集中的 `frontend/app/page.tsx` 拆分为项目目录、工作区、路线、复习、测验、看板等 feature 组件与 hooks；组合根仅保留项目选择、视图切换和跨模块刷新协调。
- 新增 Vitest、React Testing Library 和 jsdom 测试配置，覆盖项目弹窗、项目选择/删除回退、节点状态成功/失败回滚、路线详情进入/返回及错误状态。

### 运行与交付

- 新增浏览器开发服务编排：Next.js 与 FastAPI 独立启动、日志落盘并在退出时回收子进程。
- 支持通过 `LEARNING_DEV_DATA_DIR` 使用隔离开发数据，避免回归测试改写正式 SQLite。
- 更新静态构建、启动器和便携版相关路径，使构建产物可由 FastAPI 同源提供。
- 修复 `build_exe.bat` 的前端静态资源打包路径，恢复 `LearnEverything.exe` 与便携版组装流程。
- 增加 `frontend/README.md`，说明前端技术栈、目录职责、组合根、状态所有权、API/SSE 数据流、错误处理和扩展边界。

## 用户可见结果

- 运行 `start.bat` 后，开发者应访问 `http://127.0.0.1:3000` 使用学习工作台；`http://127.0.0.1:8000` 仅提供 API。
- 学习项目、路线与节点详情可在新的浏览器工作台中完成主要学习流程。
- 前端模块化后，项目目录、工作区状态、节点详情和各功能面板的状态所有权更清晰，后续新增能力不必继续膨胀根页面。
- 执行前端静态构建后，可通过 FastAPI 在 `http://127.0.0.1:8000/` 提供页面；桌面模式可由 PyWebView 承载同一页面。

## 验证

已完成的开发验证记录：

- 前端 `npm run test`：8 项测试通过。
- 前端 `npm run typecheck`：通过。
- 前端 `npm run build`：通过。
- 已在正式 Rust 学习项目完成项目切换、六个工作区标签、路线节点详情进入/返回的只读浏览器回归；390px 窄屏未出现横向溢出。
- 已使用隔离数据验证空项目 API 和前端空状态分支，未改写正式学习数据。
- 已完成 `frontend/out` 静态构建、`build_exe.bat` 打包和 `pack_portable.bat` 便携版组装检查。
- 已启动便携版验证 FastAPI `/` 与 `/api/v1/projects` 均返回 200，并使用 `LE_DESKTOP=1` 验证 PyWebView 窗口打开、标题显示和关闭后的进程退出。

## 建议评审顺序

1. 阅读 `docs/ARCHITECTURE.md`，确认运行路径和职责边界。
2. 阅读 `api/main.py`、`api/routers/` 和 `api/schemas/`，确认 HTTP 接入层范围。
3. 阅读 `learning_ext/application/`，确认业务用例与 FastAPI 表现层解耦。
4. 阅读 `frontend/README.md`，再查看 `frontend/lib/api.ts` 与 `frontend/features/`，确认 API 契约和前端模块边界。
5. 阅读 `scripts/start_frontend_dev.py`、`launcher.py`、构建脚本和测试，确认浏览器运行、桌面交付和回归覆盖。

## 兼容性、风险与后续工作

- 不修改 `kotaemon/` 底座；项目侧不再提供 Gradio 页面扩展机制。
- 桌面 exe 和便携版的构建、静态页面加载及 PyWebView 窗口生命周期已完成基础验收；便携版内完整学习工作区操作仍未全量回归。
- 前端架构入口为 `frontend/README.md`，端到端运行和后端边界继续以 `docs/ARCHITECTURE.md` 为准。
