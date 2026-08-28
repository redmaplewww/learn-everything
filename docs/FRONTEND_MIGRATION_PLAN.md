# 前端重构迁移计划

> 状态：方案已对齐，尚未实施
> 日期：2026-08-25
> 对应路线：阶段 5（Next.js 独立前端 + Kotaemon RAG 能力适配）
> 相关报告：`docs/LEARNING_EXT_API_WRAPPING_REPORT.md`

## 一、目标与总体原则

### （一）架构决策摘要

本次重构不是重写 `learning_ext`，也不是把现有 Gradio 页面直接套一层 HTTP。核心目标是把当前 Page 中混合的业务流程编排提取到共享的 application 层，让旧客户端和新客户端共用同一套业务用例。

迁移期间的目标调用关系：

```text
Gradio Page ─┐
             ├─> learning_ext/application -> learning_ext/service
Next.js API ─┘
```

最终状态：

```text
Next.js -> FastAPI -> learning_ext/application -> learning_ext/service
```

这意味着：

- `learning_ext/service` 保留现有路线、进度、FSRS、测验、笔记、看板等核心能力。
- `learning_ext/application` 负责一次完整用户操作涉及的多个 service 组合和流程判断。
- Gradio Page 在迁移期间继续作为旧客户端、回归验证入口和可回退入口。
- FastAPI 只调用 application，不调用 Gradio Page 私有方法。
- Next.js 只依赖稳定的 HTTP 接口，不依赖 SQLModel、Gradio 状态或 Python 内部对象。
- 所有功能迁移并验证完成后，才移除 Gradio 页面和旧启动链路。

### （二）总体目标

本计划完成后，项目应具备以下能力：

1. 学习领域核心逻辑仍由 `learning_ext/service` 提供，不因换前端而重复实现。
2. Page 中的跨 service 编排被提取到 `learning_ext/application`。
3. Gradio 和 FastAPI/Next.js 可以调用相同的 application 用例。
4. 新前端可以逐个业务切片替换原有页面，而不是一次性重写全部功能。
5. 浏览器模式和 Windows 桌面模式最终展示同一套 Next.js 页面。
6. Gradio 被移除后，业务逻辑、测试和启动文档仍然保持清晰。

### （三）迁移原则

#### 1. 复用核心能力

优先复用已有 service 和数据模型。除非已有函数的接口无法满足应用用例，否则不重写路线生成、FSRS、掌握度计算、测验批改等核心逻辑。

#### 2. 提取业务编排

Page 中负责“调用多个 service、决定调用顺序、处理业务分支”的代码属于 application 职责，应逐步提取。Page 只保留 UI 适配和结果渲染。

#### 3. 纵向切片

每次迁移贯通一条真实业务路径：

```text
application 用例
    -> Gradio 适配
    -> FastAPI 接口
    -> Next.js 页面
    -> 测试与手工验证
```

不先做一套没有业务闭环的空 API，也不先搭建所有前端页面再等待后端。

#### 4. 小步验证和可回退

迁移期间保留 Gradio。每个切片先让 Gradio 改为调用 application，再接入 FastAPI 和 Next.js；出现行为差异时，可以使用原页面作为对照和临时回退入口。

#### 5. 不制造长期双轨逻辑

允许迁移期间存在两个客户端，但不允许长期存在两份独立的业务流程实现。所有新的业务流程都应进入 application，再由客户端适配。

## 二、现状分析与重构边界

### （一）当前运行结构

当前桌面和浏览器模式共用同一个 Gradio 后端：

```text
launcher.py
    -> 子进程启动 custom_app.py
        -> LearningApp
            -> learning_ext/pages/*
                -> learning_ext/*/service.py
                    -> SQLite / LLM / 资料抓取
```

关键入口：

- `launcher.py:start_gradio_backend`：启动 `custom_app.py` 子进程。
- `launcher.py:open_desktop_window`：用 PyWebView 打开同一后端地址。
- `learning_ext/app.py:LearningApp`：注册学习页面和 Gradio Tab。
- `learning_ext/pages/`：现有学习 UI 适配层。

### （二）当前代码职责

```text
Gradio Page
    ├── Gradio 控件和布局
    ├── 事件注册和参数接收
    ├── 结果渲染和状态提示
    └── 部分跨 service 业务编排

learning_ext/service
    ├── 路线生成和路线持久化
    ├── 节点内容、学习进度和掌握度
    ├── FSRS 卡片调度
    ├── 测验生成和批改
    ├── 笔记、资料、看板和导出
    └── 具体数据库、LLM 和外部资源调用
```

核心判断是：现有 service 已经包含大部分核心功能，但部分“完整用户操作”仍然由 Page 事件函数组合多个 service 完成。前端重构的主要接缝就是这部分 Page 编排代码。

### （三）需要提取的代码

以下代码应进入 application，或由 application 统一调用：

- 生成路线后继续审计路线的连续流程。
- 保存路线后创建环境任务和初始课程的流程。
- 选择项目后聚合项目、节点、进度、课程和资料的读取流程。
- 选择节点后按需生成课程内容和参考资料的流程。
- 批量重新生成项目内容的流程。
- 复习、掌握度和学习进度之间的组合更新。
- 测验生成、答题、批改和掌握度回流的完整流程。

### （四）继续保留在 Page 的代码

以下代码不属于 application，应继续保留在 Gradio Page：

- `gr.Markdown`、`gr.Dropdown`、`gr.Button` 等组件创建。
- Gradio Tab 布局和组件可见性控制。
- Gradio 事件注册，例如 `.click()`、`.change()`、`.load()`。
- 将 application 结果转换成 `gr.update()`、Markdown 或文件输出。
- Gradio 专用的提示文本和视觉状态。

提取 application 并不等于重做 Gradio 页面。迁移期间对 Page 的修改只应是最小的调用路径调整，例如把原来的多 service 调用替换为一次 application 调用，页面结构和用户可见交互保持不变。

### （五）范围与非目标

#### 1. 本次范围

- 新增 `learning_ext/application/`。
- 新增 FastAPI 接口层。
- 新增 Next.js + TypeScript 前端。
- 迁移学习路线、学习工作台、FSRS 复习、测验、看板、笔记、资料和导出。
- 通过适配层逐步迁移 Kotaemon 的问答、索引和检索能力。
- 最终调整浏览器和 PyWebView 的启动链路。

#### 2. 本次非目标

- 不重写现有 service 的核心算法。
- 不修改 `kotaemon/` 底座源码。
- 不一次性迁移全部页面。
- 不在第一阶段删除 `learning_ext/pages/`。
- 不让 FastAPI 直接调用 Page 私有方法。
- 不为尚未进入迁移范围的功能提前建立复杂抽象。
- 不长期维护两套独立的业务编排逻辑。

## 三、目标架构与代码组织

### （一）分层职责

#### 1. `learning_ext/service`

负责单项能力和领域规则，例如：

- `generate_roadmap`：生成学习路线。
- `save_roadmap`：将路线持久化为项目和节点。
- `set_node_status`：更新知识节点状态。
- `review_card`：执行 FSRS 复习。
- `generate_quiz`：生成测验。
- `build_dashboard_data`：汇总看板数据。

service 的函数可以被多个客户端间接复用，但不负责 HTTP、Gradio 组件或 Next.js 状态。

#### 2. `learning_ext/application`

负责一次完整业务操作，例如：

- 创建学习项目。
- 读取学习工作台。
- 生成节点课程内容。
- 批量重新生成项目内容。
- 提交一次复习或测验操作。

application 规定 service 的调用顺序、组合结果和业务分支，是新的共享业务入口。

#### 3. FastAPI

负责：

- HTTP 路由和方法定义。
- 请求参数校验。
- 将请求转换为 application 输入。
- 将 application 结果转换为响应 Schema。
- 将后端异常转换为稳定的 HTTP 错误响应。

FastAPI Router 不应复制 Page 中的业务流程，也不应直接调用多个底层 service 进行临时拼装。

#### 4. Gradio Page

负责：

- Gradio 组件。
- 页面事件。
- application 调用。
- 结果渲染。

迁移期间 Page 是旧客户端适配器，不再是新的业务编排中心。

#### 5. Next.js

负责：

- 页面和交互。
- 前端状态管理。
- 加载、空数据、错误和重试状态。
- 调用 FastAPI 和展示返回数据。

Next.js 不直接读取 Python 文件、SQLModel 实体或 Kotaemon 内部对象。

### （二）依赖关系

目标依赖关系：

```text
Next.js -> FastAPI -> application -> service
Gradio Page -> application -> service
```

必须满足：

- application 不导入 Gradio。
- service 不依赖 HTTP 请求对象。
- FastAPI 不依赖 Page 的私有方法。
- Page 不重新实现 application 已经负责的业务流程。
- Next.js 只依赖 API Schema 和接口行为。

### （三）目标工程结构

```text
learn-everything/
├── frontend/                         # Next.js + TypeScript
│   ├── app/                          # 页面路由
│   ├── features/                     # 按学习能力组织的功能模块
│   ├── components/                   # 跨页面 UI 组件
│   └── lib/                          # API client、类型和基础工具
├── api/                              # FastAPI 接口层
│   ├── main.py                       # API 服务入口
│   ├── routers/                      # HTTP 路由
│   └── schemas/                      # 请求和响应模型
├── learning_ext/
│   ├── application/                  # 共享业务用例
│   │   ├── projects.py               # 项目和工作台
│   │   ├── roadmap.py                # 路线生成和保存流程
│   │   ├── study.py                  # 课程和节点学习流程
│   │   ├── review.py                 # FSRS 复习流程
│   │   ├── quiz.py                   # 测验流程
│   │   └── jobs.py                   # 长任务编排
│   ├── pages/                        # 迁移期间保留的 Gradio 适配层
│   ├── path_generator/
│   ├── progress/
│   ├── fsrs_review/
│   ├── quiz/
│   └── ...
├── kotaemon/                         # 只读底座和 RAG 能力
├── launcher.py
└── custom_app.py                     # 迁移完成前保留
```

目录按实际切片逐步创建，不要求第一阶段一次性建立所有文件。

### （四）Page 编排提取规则

以路线保存流程为例。

当前 Page 编排：

```text
PathGeneratorPage._handle_save_with_setup()
    -> save_roadmap()
    -> generate_env_checklist()
    -> save_env_tasks()
    -> generate_node_summary_to_db()
```

目标结构：

```text
PathGeneratorPage._handle_save_with_setup()
    -> application.create_project()
        -> save_roadmap()
        -> generate_env_checklist()
        -> save_env_tasks()
        -> 安排课程生成任务
    -> 将结果转换为 Gradio 输出
```

Page 仍然负责接收 Gradio 参数和返回 Gradio 输出，但不再自行决定完整业务流程。

## 四、Application 用例设计

### （一）用例设计要求

每个 application 用例都要记录以下内容：

- 现有 Page 入口和符号位置。
- 复用的 service 函数和符号位置。
- 输入、输出和错误行为。
- 读操作、写操作或长任务类型。
- Gradio 和 FastAPI 的调用方式。
- 独立测试方式。

行号用于定位当前工作区版本；代码变更后应优先通过函数名搜索。

### （二）项目与路线用例

| 计划用例 | 现有 Page 入口 | 复用的 service 或现有逻辑 | 对应功能 |
|---|---|---|---|
| `list_projects` | `learning_ext/pages/path_generator.py:_refresh_projects:669`；`learning_ext/pages/study_workbench.py:_refresh_projects:841` | 当前 Page 中对 `LearningProject` 的查询 | 获取学习项目列表，供路线页和工作台选择项目 |
| `get_project_workspace` | `learning_ext/pages/study_workbench.py:_auto_init:733`、`_on_project_change:853`、`_build_nodes_data:644` | `learning_ext/progress/study.py:get_project_progress:129`、`get_practice_task:290`；`learning_ext/notes/service.py:get_note:28`、`get_resources:67` | 聚合项目、节点、进度、环境任务、课程、笔记和资料，形成工作台数据 |
| `get_project_roadmap` | `learning_ext/pages/path_generator.py:_handle_load:445` | `learning_ext/path_generator/service.py:load_roadmap:357` | 读取路线 JSON、项目节点和阶段信息 |
| `generate_roadmap_preview` | `learning_ext/pages/path_generator.py:_handle_generate:269` | `learning_ext/path_generator/service.py:generate_roadmap:36`、`audit_and_rewrite_roadmap:72` | 根据主题、背景、目标和投入时间生成并审计路线预览 |
| `refine_roadmap` | `learning_ext/pages/path_generator.py:_handle_refine:299` | `learning_ext/path_generator/service.py:refine_roadmap:58` | 根据用户补充要求调整当前路线 JSON |
| `create_project` | `learning_ext/pages/path_generator.py:_handle_save_with_setup:316` | `save_roadmap:172`；`progress/study.py:generate_env_checklist:439`、`save_env_tasks:487` | 保存路线并初始化项目、节点和环境任务 |
| `prepare_project_content` | `learning_ext/pages/path_generator.py:_handle_save_with_setup:316`、`_handle_audit_project:522` | `progress/study.py:generate_node_summary_to_db:533`、`generate_summaries_background:595`、`regenerate_all_content:668` | 生成首批课程内容，并安排剩余节点的后台生成 |
| `replace_project_roadmap` | `learning_ext/pages/path_generator.py:_handle_audit_project:522` | `learning_ext/path_generator/service.py:replace_project_roadmap:300` | 审计已有路线、替换项目路线，并触发内容重新生成 |

其中 `list_projects` 和部分工作台聚合目前没有独立的领域 service，而是直接写在 Page 查询中。提取时可以先放入 application，是否进一步下沉为 service 由实际重复程度决定，不为了形式统一而强行新增 service。

### （三）学习内容与工作台用例

| 计划用例 | 现有 Page 入口 | 复用的 service | 对应功能 |
|---|---|---|---|
| `get_node_detail` | `learning_ext/pages/study_workbench.py:_on_node_select:952`、`_on_course_change:1000` | `get_practice_task`、`get_note`、`get_resources` | 获取节点详情、当前课程、实操任务、笔记、资料和状态 |
| `update_node_status` | `learning_ext/pages/study_workbench.py:_set_status:1347` | `learning_ext/progress/study.py:set_node_status:72` | 更新节点学习状态并刷新相关进度数据 |
| `generate_node_content` | `learning_ext/pages/study_workbench.py:_ensure_course_content:1005`、`_regen_current_node:1305` | `generate_node_summary_to_db:533` | 生成或强制重新生成节点教学内容 |
| `generate_practice_lesson` | `learning_ext/pages/study_workbench.py:_gen_practice_lesson:1061` | `generate_practice_lesson_to_db:395` | 生成节点对应的实操课程和任务 |
| `generate_node_resources` | `learning_ext/pages/study_workbench.py:_ensure_resources_background:1079`、`_gen_resources:1114` | `learning_ext/notes/service.py:generate_resources:75`、`save_resources_to_db:138` | 生成、保存和展示节点参考资料 |
| `save_node_note` | `learning_ext/pages/study_workbench.py:_save_note:1050` | `learning_ext/notes/service.py:save_note:39` | 保存用户对知识节点的学习笔记 |
| `audit_node_content` | `learning_ext/pages/study_workbench.py:_audit_current_node:1326` | `learning_ext/progress/audit.py:audit_node_content:68` | 审计单个节点的课程内容并返回问题说明 |
| `regenerate_project_content` | `learning_ext/pages/study_workbench.py:_regen_all:1336` | `learning_ext/progress/study.py:regenerate_all_content:668` | 按项目批量重新生成缺失或过期内容 |

`get_node_detail` 是典型的 application 聚合用例：它不是简单调用一个 service，而是组合节点、项目、课程、任务、笔记和资料查询，并决定是否触发内容或资料生成。读取接口和生成接口应在新 API 中分开，避免选择节点这种读取操作隐式触发大量副作用。

### （四）复习、测验、看板与导出用例

| 计划用例 | 现有 Page 入口 | 复用的 service | 对应功能 |
|---|---|---|---|
| `get_due_cards` | `learning_ext/pages/review.py:_load_next:111` | `learning_ext/fsrs_review/service.py:get_due_cards:164` | 获取待复习 FSRS 卡片 |
| `review_fsrs_card` | `learning_ext/pages/review.py:_review:128` | `learning_ext/fsrs_review/service.py:review_card:110` | 提交复习评分并更新卡片调度结果 |
| `generate_quiz` | `learning_ext/pages/quiz.py:on_register_events:53` 当前仍是 TODO | `learning_ext/quiz/service.py:generate_quiz:56` | 按节点范围生成测验 |
| `submit_quiz_answer` | 目标接入 `learning_ext/pages/quiz.py` | `learning_ext/quiz/service.py:grade_answer:119` | 提交答案、AI 批改并记录结果 |
| `build_dashboard` | `learning_ext/pages/dashboard.py:_load_dashboard:83`、`_dashboard_outputs:88` | `learning_ext/dashboard/service.py:build_dashboard_data:264` | 汇总项目进度、掌握度、节点状态和热力图 |
| `export_project` | `learning_ext/pages/path_generator.py:_handle_export_roadmap:463` | `learning_ext/path_generator/service.py:export_roadmap_bundle:241`；`learning_ext/exporter/service.py` | 导出路线、Markdown、进度报告或 Anki 包 |

测验页面当前仍未完整接入 service，因此该功能应先补 application 用例和测试，再实现 API 和 Next.js 页面，不应仅按现有 Gradio 页面外观进行复制。

### （五）Application 与客户端的共同调用方式

Application 用例应该是客户端无关的普通 Python 调用：

```python
result = create_project(
    session=session,
    topic=topic,
    background=background,
    goal=goal,
    weekly_hours=weekly_hours,
)
```

Gradio 适配器负责：

```python
result = create_project(...)
return result.project_id, result.progress_text, result.roadmap_markdown
```

FastAPI 适配器负责：

```python
result = create_project(...)
return ProjectCreatedResponse.from_result(result)
```

两者的业务结果来自同一个 application 用例，差异只存在于输出格式。

## 五、分阶段实施路线

### （一）阶段 0：重构基线

目标：在改动业务入口前，明确现有行为和迁移顺序。

工作内容：

- 梳理 Page 到 service 的调用关系。
- 确认路线创建、工作台读取、节点状态、FSRS 复习的现有行为。
- 确定首批 application 用例及其输入输出。
- 为首批用例补充或整理现有测试。
- 记录当前 Gradio 启动和回归验证方式。

完成标准：

- 首批用例都有明确源码入口。
- 关键旧页面行为可以重复验证。
- 没有在这一阶段修改前端视觉或迁移全部功能。

### （二）阶段 1：建立 application 接缝

目标：让旧 Gradio 页面先通过 application 工作，验证共享业务层不会改变原有行为。

工作内容：

- 创建 `learning_ext/application/`。
- 优先提取 `list_projects`、`get_project_workspace`、`get_project_roadmap`、`update_node_status`。
- 将对应 Page 事件函数中的多 service 调用替换为 application 调用。
- 保持 Gradio 组件、页面布局和输出格式不变。
- 为 application 增加独立单元测试。

完成标准：

- Gradio 页面仍能完成项目选择、路线读取和节点状态更新。
- application 不依赖 Gradio。
- Page 不再直接编排首批用例的多个 service。

### （三）阶段 2：第一条 API 纵向切片

目标：用最小业务范围验证 FastAPI、application 和 Next.js 的完整链路。

建议接口：

```text
GET   /api/v1/projects
GET   /api/v1/projects/{project_id}/workspace
GET   /api/v1/projects/{project_id}/roadmap
PATCH /api/v1/nodes/{node_id}/status
```

工作内容：

- 创建 FastAPI API 入口和路由目录。
- 为项目、工作台、路线和节点状态定义独立请求/响应结构。
- 路由只调用 application，不复制 Page 逻辑。
- 创建 Next.js 应用外壳、项目列表和工作台基础页面。
- 接入真实 SQLite 数据，完成节点状态更新。

完成标准：

- Next.js 可以读取真实项目和路线数据。
- 用户可以在 Next.js 修改节点状态并看到结果。
- Gradio 仍然可以完成同一操作。
- API 和 application 有对应测试。

### （四）阶段 3：迁移路线创建流程

目标：迁移第一个包含多个 service 和长耗时步骤的完整写入流程。

工作内容：

- 提取 `generate_roadmap_preview`。
- 提取 `refine_roadmap`。
- 提取 `create_project`。
- 将环境清单、环境任务和课程生成从 Page 编排中移出。
- 明确路线预览、项目保存和后台内容生成的边界。
- 让 Gradio 和 FastAPI 共用相同 application。
- 实现 Next.js 路线创建和保存页面。

完成标准：

- 路线生成、审计、保存行为与原页面一致。
- 失败时能够区分路线生成失败、保存失败和内容生成失败。
- 长耗时内容生成不阻塞普通页面读取。
- Gradio 可以继续作为对照入口。

### （五）阶段 4：迁移学习核心功能

目标：让日常学习闭环在 Next.js 中可用。

迁移顺序建议：

1. 节点详情和课程内容。
2. 笔记和参考资料。
3. 节点状态和学习进度。
4. FSRS 到期卡片和评分。
5. 测验生成、答题和批改。
6. 看板、统计和导出。

每项功能都应先有 application 用例，再增加 FastAPI 接口和 Next.js 页面。

完成标准：

- 用户可以从路线进入节点学习。
- 学习结果可以回流到进度和掌握度。
- 复习、测验和看板数据来自同一套后端业务逻辑。
- 长任务、失败、空数据和重试状态在前端可见。

### （六）阶段 5：迁移 Kotaemon 能力

目标：迁移当前仍依赖 Kotaemon/Gradio 的问答和资料库能力。

工作内容：

- 区分 Kotaemon 的底层 pipeline 能力和 Page/UI 状态。
- 为索引、检索和 reasoning pipeline 建立独立适配层。
- 迁移知识问答、流式回答和引用展示。
- 迁移文档上传、索引状态、资料列表和删除操作。
- 迁移必要的模型配置页面。
- 不调用 `ChatPage.chat_fn()` 作为长期 API。

完成标准：

- 新前端可以完成日常问答和资料库操作。
- API 不依赖 Gradio 组件状态。
- Kotaemon 底座源码没有被业务迁移直接修改。

### （七）阶段 6：桌面端切换

目标：让浏览器模式和 Windows exe 使用同一套 Next.js 前端。

工作内容：

- 调整 `launcher.py` 的进程编排。
- 确定开发模式和打包模式下的前端资源加载方式。
- 让 PyWebView 加载 Next.js 页面。
- 更新 `run.bat`、`build_exe.bat` 和便携版打包脚本。
- 验证启动顺序、就绪等待、端口占用、日志转发和进程退出。

完成标准：

- 浏览器和 exe 展示同一套 Next.js UI。
- 关闭桌面窗口后相关子进程可以正确退出。
- 首次启动、离线启动和已有端口场景可以处理。

## 六、验收、风险与最终收敛

### （一）单个切片验收标准

每个迁移切片必须同时满足：

- application 可以脱离 Page 独立测试。
- Gradio 页面仍能正常运行。
- FastAPI 使用同一个 application 用例。
- Next.js 完成真实数据读写闭环。
- 没有在 API 或前端复制 service 业务规则。
- 新旧客户端关键行为一致。
- 失败时可以回退到 Gradio。
- 测试命令、手工验证步骤和遗留风险已记录。

### （二）测试策略

#### 1. Application 测试

- 使用临时 SQLite 或现有测试 fixture。
- 测试用例输入、输出和业务分支。
- 测试 service 调用顺序和失败传播。
- 测试重复提交、空数据和无效状态。

#### 2. FastAPI 契约测试

- 测试请求 Schema 和响应 Schema。
- 测试状态码和错误结构。
- 测试 API 不返回 SQLModel 内部细节。
- 测试长任务返回任务标识和状态信息。

#### 3. Page 回归测试

- 保留现有 Page 测试。
- application 接入后确认 Gradio 输出仍符合原行为。
- 在对应 Next.js 切片稳定前，不删除 Page 测试。

#### 4. 前端流程测试

- 项目列表加载。
- 项目切换和节点选择。
- 节点状态更新。
- 路线创建和保存。
- 失败、重试和空状态。

### （三）主要迁移风险

#### 1. Page 编排提取不完整

如果只提取一个 service 调用，而遗漏 Page 中的业务分支，Gradio 和 Next.js 可能产生行为差异。每个 application 用例都要以完整用户操作为边界进行验证。

#### 2. 读取操作夹带副作用

当前工作台选择节点可能触发课程和资料生成。新的读取 API 应先返回已有数据，生成操作通过明确的 POST 或任务接口触发，避免 GET 请求隐式调用 LLM 或网络抓取。

#### 3. 长任务被误当成普通请求

路线生成、课程生成、资料抓取和索引可能耗时较长。应把它们设计为任务用例，提供状态查询和失败反馈，不让页面请求无限等待。

#### 4. Gradio 与 Next.js 形成行为分叉

所有新业务流程必须先进入 application。禁止在 Next.js API Router 中重新复制一套 Page 编排，也禁止为两个客户端分别维护不同的业务规则。

#### 5. Kotaemon Page 与底层 pipeline 耦合

问答和资料库迁移需要先验证无 Gradio 的 pipeline 调用路径。适配代码放在项目侧，不修改 `kotaemon/` 底座。

#### 6. 现有 service 的边界不完整

部分 service 自己管理 Session、提交事务或使用全局配置。第一阶段不要求全面重构；只有当某个 application 用例需要统一事务或可测试替换时，才针对该用例调整 service 接口。

### （四）阶段 7：移除 Gradio

只有满足以下条件后，才进入最终收尾：

- 所有用户日常流程均可在 Next.js 完成。
- 浏览器和 exe 的关键回归测试通过。
- Kotaemon 问答和资料库能力已有新入口。
- application 已成为所有业务流程的共享入口。
- 没有仍依赖 Gradio Page 私有方法的 FastAPI 路由。

收尾工作：

- 删除 `learning_ext/app.py` 中的学习 Page 注册。
- 删除 `learning_ext/pages/` 中不再需要的页面适配代码。
- 删除 Gradio 专用事件绑定和 CSS/脚本注入。
- 调整 `custom_app.py` 和启动器职责。
- 清理不再需要的 Gradio 依赖，但保留 Kotaemon 仍需要的底层依赖。
- 更新架构、启动、打包和故障排查文档。

### （五）里程碑完成定义

| 里程碑 | 完成定义 |
|---|---|
| Application 接缝 | 首批 Page 编排已提取，并由 Gradio 调用 application |
| 第一条 API 切片 | Next.js 完成项目读取和节点状态更新闭环 |
| 路线迁移 | 路线生成、审计、保存和项目准备共用 application |
| 学习功能迁移 | 工作台、课程、复习、测验和看板可用 |
| Kotaemon 迁移 | 问答、资料库和必要配置页面可用 |
| 桌面端切换 | 浏览器和 exe 使用同一套 Next.js UI |
| Gradio 移除 | 主运行链路不存在 Gradio 用户界面 |

## 七、近期执行顺序

### （一）第一批代码任务

1. 新增 `learning_ext/application/` 包。
2. 提取 `list_projects`。
3. 提取 `get_project_roadmap`。
4. 提取 `get_project_workspace`。
5. 提取 `update_node_status`。
6. 让 `PathGeneratorPage` 和 `StudyWorkbenchPage` 调用这些 application 用例。
7. 为 application 用例补测试，确认 Gradio 行为不变。

### （二）第二批代码任务

1. 新增 FastAPI 最小服务入口。
2. 为第一批 application 用例增加 HTTP 路由。
3. 定义项目、路线、工作台和节点状态响应结构。
4. 增加 Next.js 项目列表和工作台页面。
5. 完成项目读取和节点状态更新的端到端验证。

### （三）当前完成定义

本计划文档完成不代表迁移已经开始。进入下一阶段的条件是：

- 计划中的 application 用例与源码位置已对齐。
- 第一批切片范围已经确认。
- 旧 Gradio 行为的验证方式已经明确。
- 新增代码可以从 `list_projects` 和 `get_project_roadmap` 等低风险读取用例开始。

迁移的核心顺序保持不变：**先抽取共享 application，再接入 FastAPI 和 Next.js，最后移除 Gradio。**
