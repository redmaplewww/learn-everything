# 前端技术栈调研

> 调研日期：2026-08-29  
> 调研范围：当前仓库源码、依赖清单、开发脚本、打包脚本与启动链路  
> 结论口径：以实际默认运行路径为准，区分现行主栈与兼容回退栈

## 1. 结论摘要

项目当前的主前端已经从 Kotaemon/Gradio 页面迁移到独立的 **Next.js 16 + React 19 + TypeScript 7** 客户端。它使用 Next.js App Router，但只有一个根页面；页面整体是客户端渲染的单页工作台。生产构建采用 Next.js 静态导出，由 FastAPI 同源托管，再由浏览器或 PyWebView 显示。

当前前端没有引入 Tailwind CSS、CSS Modules、组件库、全局状态库、数据请求库或前端路由库。样式由一份原生 CSS 文件维护，状态与副作用主要依赖 React Hooks，HTTP 与 SSE 通信直接使用浏览器 Fetch API。

旧的 Gradio UI 尚未删除，但已不是默认入口。只有显式设置 `LE_UI=gradio` 时，启动器才会运行 `custom_app.py` 和 `learning_ext/pages/` 中的 Gradio 页面。

## 2. 现行主栈

| 层次 | 技术 | 仓库版本/实现 | 证据 |
| --- | --- | --- | --- |
| Web 框架 | Next.js | `16.3.3`，App Router | [`frontend/package.json`](../frontend/package.json)、[`frontend/app/layout.tsx`](../frontend/app/layout.tsx) |
| UI 运行时 | React / React DOM | `19.2.8` | [`frontend/package.json`](../frontend/package.json) |
| 开发语言 | TypeScript | `7.0.2`，严格模式 | [`frontend/package.json`](../frontend/package.json)、[`frontend/tsconfig.json`](../frontend/tsconfig.json) |
| 渲染模式 | Client Components | 根页面及功能组件使用 `"use client"` | [`frontend/app/page.tsx`](../frontend/app/page.tsx) |
| 构建/交付 | Next.js Static Export / Turbopack | `output: "export"`，产物为 `frontend/out/` | [`frontend/next.config.ts`](../frontend/next.config.ts)、[`build_exe.bat`](../build_exe.bat) |
| 图标 | Lucide React | `1.34.0` | [`frontend/package.json`](../frontend/package.json)、[`frontend/app/page.tsx`](../frontend/app/page.tsx) |
| Markdown | react-markdown + remark-gfm | `10.1.0` + `4.0.1`；禁用原始 HTML | [`frontend/features/markdown/MarkdownContent.tsx`](../frontend/features/markdown/MarkdownContent.tsx) |
| 样式 | 原生全局 CSS | CSS Variables、Grid、Flexbox、媒体查询、关键帧动画 | [`frontend/app/styles.css`](../frontend/app/styles.css) |
| 状态管理 | React Hooks | `useState`、`useEffect`、`useMemo`、`useCallback`、`useRef` | [`frontend/app/page.tsx`](../frontend/app/page.tsx) |
| HTTP 客户端 | Browser Fetch API | 自建类型化 API 封装和 `ApiError` | [`frontend/lib/api.ts`](../frontend/lib/api.ts) |
| 流式通信 | SSE over Fetch streams | `ReadableStream` + `TextDecoder` 手工解析事件帧 | [`frontend/lib/api.ts`](../frontend/lib/api.ts) |
| 包管理 | npm | 存在 `package-lock.json`，脚本使用 `npm run` | [`frontend/package-lock.json`](../frontend/package-lock.json)、[`build_exe.bat`](../build_exe.bat) |

## 3. 前端结构与职责

```text
frontend/
├── app/
│   ├── layout.tsx       # 根布局与页面元数据
│   ├── page.tsx         # 单页工作台、主要页面状态和业务编排
│   └── styles.css       # 全局设计变量、组件样式与响应式规则
├── features/
│   ├── chat/            # RAG 流式问答
│   ├── configuration/   # 模型配置
│   ├── markdown/        # Markdown 安全渲染
│   ├── resources/       # 文件上传、索引与删除
│   └── roadmap/         # 学习路线创建
└── lib/api.ts           # API DTO、请求封装、SSE 解析
```

`app/page.tsx` 是当前组合根，承载项目列表、学习路线、节点详情、复习、测验、看板和 Tab 切换。部分相对独立的能力已拆到 `features/`，但主文件仍有 537 行，且同时承担页面编排、局部状态、异步流程和部分功能 UI。

当前没有使用 Next.js 文件路由承载多个业务页面，也没有服务端组件获取业务数据。`layout.tsx` 是服务端布局，主业务页面则以 Client Component 运行；业务视图通过组件状态切换，而不是 URL 路由切换。

## 4. 数据与运行链路

### 开发模式

```text
浏览器 :3000
  -> Next.js dev server
  -> fetch http://127.0.0.1:8000/api/v1
  -> FastAPI
  -> learning_ext application/service
```

`scripts/start_frontend_dev.py` 同时启动 Next.js 与 FastAPI，并通过 `NEXT_PUBLIC_LEARNING_API_BASE` 把前端请求指向 `http://127.0.0.1:8000/api/v1`。FastAPI 仅允许本机 `3000` 端口的开发跨域来源。

### 构建与桌面运行

```text
npm run build
  -> frontend/out/
  -> FastAPI StaticFiles 挂载到 /
  -> http://127.0.0.1:8000
  -> 浏览器，或 LE_DESKTOP=1 时由 PyWebView 打开
```

静态构建中 API 基址默认是相对路径 `/api/v1`，因此前端与 FastAPI 同源，不需要生产 CORS。`launcher.py` 默认选择该链路；如果找不到 `frontend/out/index.html`，启动会直接失败并提示先构建前端。

PyWebView 只是桌面窗口容器，不参与 React 渲染、状态管理或 API 通信。默认仍打开系统浏览器，只有设置 `LE_DESKTOP=1` 才尝试创建 PyWebView 窗口。

## 5. 通信方式

- 普通业务操作使用 JSON REST API，统一前缀为 `/api/v1`。
- RAG 问答和资料上传进度使用 `text/event-stream`。
- SSE 没有使用 `EventSource`，因为调用包含 POST 请求体或文件上传；代码直接读取响应流并解析 `event:` / `data:` 帧。
- 请求错误由自建 `ApiError` 统一携带 HTTP 状态、消息与后端 `x-request-id`。
- 前后端 DTO 由 `frontend/lib/api.ts` 手写维护，当前没有 OpenAPI 代码生成。

## 6. 样式与交互实现

设计层未使用 Tailwind、Sass、styled-components、Emotion、CSS-in-JS 或 CSS Modules。`styles.css` 使用：

- `:root` CSS Variables 管理颜色与阴影；
- CSS Grid 和 Flexbox 构建工作台、列表、表单、看板与聊天布局；
- `760px`、`1100px` 媒体查询适配窄屏；
- 原生 `:focus-visible`、ARIA tab 属性和隐藏文本提供基础可访问性；
- `@keyframes` 实现加载旋转动画。

组件没有依赖 shadcn/ui、MUI、Ant Design 等设计系统。按钮、表单、状态卡片和 Tab 都由原生 HTML + CSS 实现。

## 7. Gradio 兼容栈

仓库仍保留完整的 Kotaemon/Gradio UI：

- `custom_app.py` 构建 `LearningApp` 并启动 Gradio；
- `learning_ext/pages/` 下的页面继承 Kotaemon `BasePage`；
- `learning_ext/assets/word_lookup.js` 会注入 Gradio 初始模板；
- 设置 `LE_UI=gradio` 后，启动器改用 `7860` 端口运行该界面。

因此准确描述应是：**Next.js/React 是当前默认前端，Gradio 是仍可运行的兼容回退前端**，两者共享 `learning_ext` 业务能力，但入口与交互实现不同。

## 8. 明确未使用的技术

根据 `frontend/package.json`、锁文件和源码导入，当前没有发现以下依赖：

- Tailwind CSS、Sass、PostCSS 自定义插件；
- shadcn/ui、MUI、Ant Design、Chakra UI；
- Redux、Zustand、MobX、XState；
- TanStack Query、SWR、Axios；
- React Hook Form、Zod；
- React Router；
- Jest、Vitest、React Testing Library、Playwright、Cypress；
- ESLint、Prettier。

这不是对技术选型优劣的判断，只表示当前仓库中没有实际采用。

## 9. 现状判断与风险

1. **迁移已提前发生，架构文档滞后。** `docs/ARCHITECTURE.md` 仍把 Next.js 独立前端列为阶段 5，并主要描述 Gradio 链路；实际默认启动链路已经是 Next.js + FastAPI。
2. **前端测试与质量脚本缺失。** `package.json` 只有开发、构建、启动和类型检查脚本，没有 lint 或前端测试命令。
3. **组合根偏重。** `app/page.tsx` 已达到 537 行，继续扩展时会增加状态耦合和回归范围；现有 `features/` 拆分方向是合理的。
4. **API 类型手工同步。** DTO 与后端 schema 没有自动生成关系，接口演进时存在前后端类型漂移风险。
5. **SSE 解析器重复。** RAG 与上传各自维护近似的帧解析循环，可在确有第三个流式接口时再抽取，当前不必为复用而提前设计。

## 10. 验证结果与边界

本报告同时核对了仓库静态证据、依赖锁文件和本地构建结果：

- `npm ls --depth=0`：通过，安装版本与依赖清单一致；本地另有两个未列入清单的可选 Sharp/WASM 相关包，不构成项目直接依赖；
- `npm run typecheck`：通过，`tsc --noEmit` 无类型错误；
- `npm run build`：通过，Next.js 16.3.3 使用 Turbopack 完成生产构建；
- 构建结果：`/` 与 `/_not-found` 均为静态预渲染页面。

本次没有启动 FastAPI、浏览器或 PyWebView 做端到端交互验证。运行链路结论来自启动、服务挂载与打包代码，而非本轮桌面应用实测。
