# `learning_ext` 核心逻辑与 API 包装深度探索报告

> 历史设计分析：本文记录迁移前的 Gradio 耦合情况。当前项目侧 Gradio 入口和页面已删除，运行方式以 Next.js + FastAPI 为准；`kotaemon/` 底座保持不变。

> 状态：源码探索完成，尚未实施 API 改造
> 日期：2026-08-24
> 对齐文档：`docs/ARCHITECTURE.md`、`docs/FRONTEND_MIGRATION_PLAN.md`

## 1. 执行结论

先回答最核心的问题：

> `learning_ext` 目前没有统一的“业务接口类”或独立应用层，但大部分核心能力已经以普通 Python 函数形成了可复用的模块接口。FastAPI 可以复用这些函数，不能复用 Gradio Page；在正式暴露 HTTP 接口前，还需要抽出页面中的流程编排，并补齐事务、用户隔离、长任务和安全约束。

当前代码不是“Gradio 里全是业务逻辑”，也不是“已经天然可以直接变成 API”。实际情况位于两者之间：

- 路线、进度、FSRS、测验、笔记、看板、导出等算法和持久化函数主要位于 `learning_ext/*/service.py` 或 `learning_ext/progress/study.py`，没有 Gradio 参数，可以复用。
- Gradio Page 仍承担了大量应用流程编排，例如“生成路线后自动审计、保存项目、生成环境清单、同步生成前三节课程、后台生成剩余课程”。这些流程必须从 Page 中提取，否则 FastAPI 只能复制一份页面逻辑。
- 现有 SQLModel 表模型不能直接当作稳定的 HTTP 请求/响应模型；API 必须建立独立 Schema。
- 现有写操作普遍在底层函数内部 `commit()`，组合流程无法形成清晰的原子事务。
- 当前桌面模式关闭了用户管理，大量调用硬编码 `user_id="default"`。本地单用户可以继续使用默认用户，但所有 API 查询仍必须执行资源归属校验。
- 长耗时 LLM、资料抓取、课程批量生成不能作为普通同步请求长期占用连接，应包装为可查询状态的后台任务并通过 SSE 提供进度。
- `learning_ext` 当前没有真正调用 Kotaemon RAG。知识问答和资料库迁移是独立工作面，不能认为包装现有 `learning_ext` 函数后就自动获得 Kotaemon RAG API。

综合判断：

| 范围 | 当前可复用程度 | 结论 |
|---|---:|---|
| 学习项目、路线读取、节点状态 | 高 | 适合作为第一批 API |
| FSRS 复习、统计、笔记、导出 | 较高 | 补用户归属校验和 DTO 后可包装 |
| 路线生成、课程生成、资料生成 | 中 | 核心函数可复用，但必须进入任务系统 |
| 工作台完整流程 | 中低 | 聚合查询和副作用编排仍在 Page 中 |
| 测验闭环 | 中低 | service 已存在，但有节点关联缺失等正确性问题 |
| 模型配置 | 低 | 文件和密钥操作仍写在 Gradio Page 中 |
| 自动环境配置 | 不应直接暴露 | 本质是远程命令执行能力，必须隔离和二次确认 |
| Kotaemon RAG/资料库 | 低 | 底层有 pipeline 接口，但现有入口与 Gradio 状态强耦合 |

## 2. 探索范围与证据边界

本报告实际检查了：

- 启动链：`launcher.py`、`custom_app.py`、`learning_ext/app.py`
- 数据模型与初始化：`learning_ext/db/models.py`、`learning_ext/bootstrap.py`
- 全部学习业务模块：路线、进度、FSRS、测验、笔记、看板、实操、费曼、导出
- 全部学习 Page，重点追踪 `PathGeneratorPage` 和 `StudyWorkbenchPage`
- LLM 配置和调用：`learning_ext/llm/client.py`、`learning_ext/pages/quick_setup.py`
- Kotaemon 的 `BaseIndex`、`IndexManager`、`BaseReasoning`、Chat pipeline 和文件索引 pipeline
- 项目自有测试 `tests/`

静态规模用于辅助判断，不作为质量指标：

- `learning_ext` Python 代码约 6860 行。
- `learning_ext/pages` 约 2651 行，占比约 39%。
- `service.py` 文件合计约 1879 行。
- `StudyWorkbenchPage` 单文件 1382 行，已经明显超出纯视图职责。

测试基线：

- `python -m pytest -q tests` 输出 `131 passed, 6 skipped, 1 warning`。
- 测试结果输出后进程仍未自动退出，本次手动终止了残留进程，因此不能把该命令记为正常退出码 0。
- 直接运行整个仓库的 `pytest` 会在收集 Kotaemon 自带测试时失败：`kotaemon/libs/ktem/ktem_tests/test_qa.py` 无法导入顶层模块 `index`。这不是 `learning_ext` 测试失败，但说明当前仓库没有统一可直接运行的全量测试入口。

## 3. 当前真实架构

### 3.1 运行调用链

```text
launcher.py
  -> 子进程启动 custom_app.py
    -> LearningApp.make()
      -> 构建 Gradio Page
        -> Page 事件处理函数
          -> learning_ext 业务函数
            -> SQLModel Session / OpenAI 兼容 LLM / HTTP 抓取
```

浏览器和 PyWebView 都访问同一个 Gradio 服务。exe 只是启动器和窗口容器，不包含另一套前端或业务实现。

### 3.2 目标调用链

```text
Next.js
  -> FastAPI Router
    -> 应用用例模块
      -> learning_ext 领域/业务函数
        -> SQLModel Session
        -> LLM Gateway
        -> Job Runner
        -> Kotaemon RAG Gateway
```

关键规则：

- Router 只负责 HTTP、鉴权上下文、Schema 和错误映射。
- 应用用例负责一次用户操作的完整流程和事务。
- 现有 service 函数负责领域计算或具体持久化行为。
- Gradio Page 在迁移期间只能作为旧适配器，不能继续充当业务编排中心。

## 4. 当前到底有哪些“接口”

### 4.1 没有统一的业务接口类

`learning_ext` 内没有类似下面这种统一抽象：

```python
class LearningService(Protocol):
    ...
```

也没有现成的 FastAPI Router、应用用例层、Repository 层或 HTTP Schema。当前仓库中不存在 `api/`、`frontend/`，也没有项目自有 FastAPI 路由。

这不代表没有可复用接口。接口不一定是 `class` 或 Python `Protocol`；函数签名、异常、事务行为、配置要求和返回结构共同构成模块接口。

### 4.2 已存在的函数接口

各包的 `__init__.py` 已经暴露了一批调用面，例如：

- `learning_ext.path_generator`：`generate_roadmap`、`save_roadmap`、`load_roadmap`、`replace_project_roadmap`
- `learning_ext.fsrs_review`：`get_due_cards`、`review_card`、`get_review_stats`
- `learning_ext.quiz`：`generate_quiz`、`grade_answer`、`get_weak_nodes`
- `learning_ext.notes`：`get_note`、`save_note`、`get_resources`、`generate_resources`
- `learning_ext.exporter`：`export_markdown`、`export_progress_report`、`export_anki_apkg`
- `learning_ext.feynman`：`feynman_chat`、`socrates_chat`

这些函数是当前最值得复用的接口，但尚未达到稳定 HTTP 契约的要求。

### 4.3 `Session` 参数是有价值的 seam，但并不完整

架构文档称“所有 service 函数第一参数是 `session: Session`”。源码中只有数据库相关函数大体遵守这一约定：

- 纯 LLM 函数不需要 Session，例如 `generate_roadmap()`、`generate_node_summary()`。
- `generate_node_summary_to_db()`、`generate_practice_lesson_to_db()`、`regenerate_all_content()` 会在函数内部反向导入 `ktem.db.engine.engine` 并自行创建 Session。
- 页面也大量直接导入全局 engine 并自行管理 Session。

因此当前 Session 注入已经改善了测试性，但还没有形成统一的事务 seam。

### 4.4 `learning_ext.llm.chat/chat_json` 是现成 facade

`learning_ext/llm/client.py` 提供：

- `chat()`：普通或流式文本调用
- `chat_json()`：JSON 解析和容错提取
- `get_llm()`：兼容旧调用风格的包装对象

它已经把业务模块与 OpenAI SDK 的多数细节隔开，是可保留的 seam。但它同时负责：

- 固定读取 `kotaemon/.env`
- 配置缓存
- 创建 OpenAI Client
- 重试
- JSON 解析

测试通过对多个模块的导入符号进行 monkeypatch，而不是注入依赖。这说明 facade 有用，但实现与调用方仍是模块级静态耦合。

### 4.5 `BasePage` 不是新 API 应复用的接口

`PathGeneratorPage`、`StudyWorkbenchPage` 等继承 Kotaemon `BasePage`。这个接口的职责是：

- 构建 Gradio 组件
- 绑定 Gradio 事件
- 操作 `gr.State`
- 返回 `gr.update()` 和 Markdown/HTML 展示文本

它是旧 UI 适配器接口，不是业务接口。FastAPI 不应实例化 Page 或调用 `_handle_*`、`_on_*` 私有方法。

### 4.6 Kotaemon 确实存在底层 pipeline 接口

Kotaemon 内存在更明确的抽象接口：

- `BaseIndex.get_indexing_pipeline()`
- `BaseIndex.get_retriever_pipelines()`
- `BaseReasoning.get_pipeline()`
- reasoning pipeline 的 `stream()`

这些接口比 `ChatPage.chat_fn()` 更适合作为 RAG 适配基础。但是当前 `ChatPage.create_pipeline()` 仍负责拼装 settings、文件选择、reasoning state 和 Gradio 展示状态；`FileIndex.get_retriever_pipelines()` 还依赖 selector UI 将组件值转换为文件 ID。因此它们不能未经适配直接暴露为 HTTP。

## 5. 模块级 API 就绪度

| 模块 | 当前核心接口 | 主要依赖 | Gradio 耦合 | API 前必要处理 |
|---|---|---|---|---|
| 路线生成 | `generate_roadmap`、`refine_roadmap`、`audit_*` | LLM | 无 | 放入长任务；校验 LLM JSON |
| 路线持久化 | `save_roadmap`、`load_roadmap`、导入导出 | Session | 无 | 独立 DTO、用户归属、事务统一 |
| 路线替换/删除 | `replace_project_roadmap`、`delete_project` | Session | 无 | 明确破坏性语义、确认和审计日志 |
| 节点推进 | `set_node_status`、`get_next_learnable_nodes` | Session | 无 | 状态枚举统一、用户归属 |
| 课程内容 | `generate_node_summary*`、`regenerate_all_content` | LLM、全局 engine、线程池 | 无直接 Gradio | 任务状态、去重、取消、错误可见性 |
| FSRS | `get_due_cards`、`review_card`、统计 | Session、fsrs | 无 | 卡片归属校验、响应 DTO |
| 测验 | `generate_quiz`、`grade_answer` | Session、LLM | 无 | 修复题目节点关联、事务和归属 |
| 笔记 | `get_note`、`save_note` | Session | 无 | 校验 node/project/user 一致性 |
| 参考资料 | `generate_resources`、`fetch_resource_content` | LLM、外部 HTTP、PDF | 无 | SSRF、防大文件、任务化 |
| 看板 | `build_dashboard_data` | Session | 无 | 移除 UI tuple，定义稳定 DTO |
| AI 助教 | Page 内 `_chat_send` | Session、LLM、`gr.State` | 高 | 提取上下文构建和对话用例 |
| 费曼/苏格拉底 | `feynman_chat`、`socrates_chat` | LLM | 无 | 对话历史 Schema、可选持久化 |
| 实操计划 | `generate_practice_plan` | Session、LLM | 无 | 任务化、输入校验 |
| 自动环境配置 | `run_all_commands` | PowerShell 子进程 | Page 触发 | 不进入普通 API；强隔离和确认 |
| 模型配置 | `_read_env`、`_write_env`、`_apply_to_runtime` | 文件、Kotaemon Manager、HTTP | 全在 Page | 提取配置模块，密钥只写不读 |
| 导出 | `export_*` | Session | 无 | Content-Type、文件名、HTML 转义 |
| Kotaemon RAG | Index/Reasoning pipeline | Kotaemon 全局配置和状态 | 中高 | 建专用 adapter，先做技术验证 |

## 6. 两条最重要的现有调用链

### 6.1 路线创建流程

当前生成阶段位于 `PathGeneratorPage._handle_generate()`：

```text
用户输入
  -> generate_roadmap()             第一次 LLM
  -> audit_and_rewrite_roadmap()    第二次 LLM
  -> Page 转 Markdown/JSON
```

当前保存阶段位于 `PathGeneratorPage._handle_save_with_setup()`：

```text
save_roadmap()
  -> generate_env_checklist()
  -> save_env_tasks()
  -> 同步生成前 3 节 generate_node_summary_to_db()
  -> 后台线程生成剩余课程 generate_summaries_background()
```

核心问题：这是一个真正的应用用例，但实现位于 Gradio Page。FastAPI 如果直接组合底层函数，会复制同一流程；如果直接调用 Page，则会继承 Gradio 类型、展示文本和全局 engine。

建议提取三个用例：

```text
GenerateRoadmapDraft
CreateLearningProject
PrepareLearningProject
```

其中 `PrepareLearningProject` 必须作为后台任务运行，并输出结构化进度事件，不能输出已经拼好的 Markdown 状态文本。

### 6.2 学习工作台流程

`StudyWorkbenchPage` 当前同时完成：

- 项目列表和进度聚合
- 节点解锁判断和下拉框选项构造
- 节点内容、笔记、实操、资料聚合
- 缺少课程内容时立即触发生成
- 缺少参考资料时后台触发抓取
- AI 助教上下文构造和对话历史维护
- 把 AI 回答追加到课程正文
- 环境命令生成和执行
- 节点状态变更后预生成后续课程

这里有一个必须改变的 HTTP 语义：

> 当前“打开课程”可能触发课程生成和资料抓取。新的 `GET` 接口必须是只读操作，不能因为读取节点而隐式产生 LLM 费用、网络请求或数据库写入。

建议拆成：

- `GetProjectWorkspace`：只读聚合查询
- `GetNodeStudyDetail`：只读节点详情
- `StartLessonGeneration`：显式创建生成任务
- `StartResourceGeneration`：显式创建资料任务
- `UpdateNodeStatus`：状态变更，并显式决定是否创建后续预生成任务
- `AskStudyAssistant`：对话流
- `AppendAssistantSupplement`：把指定消息追加到正文

## 7. API 暴露前必须处理的问题

### 7.1 用户隔离和资源归属

当前大量函数只按主键查询：

- `session.get(LearningProject, project_id)`
- `session.get(KnowledgeNode, node_id)`
- `session.get(Card, card_id)`
- `session.get(QuizQuestion, question_id)`

它们没有验证资源是否属于当前用户。`review_card()` 甚至可以读取任意卡片，再用调用方传入的 `user_id` 写 ReviewLog。

API 必须满足：

- 客户端不传可信 `user_id`；用户 ID 由 FastAPI dependency 提供。
- 通过 Project 归属验证 Node、Task、Note、Resource、Quiz、Card。
- 单用户阶段仍统一使用一个 `UserContext(user_id="default")`，不能绕过归属检查。

第一阶段不需要引入完整登录系统，但不能把“单用户”实现为“完全不校验 ID”。

### 7.2 事务所有权不清晰

现有多数写函数内部直接 `commit()`：

- `save_roadmap()`
- `set_node_status()`
- `save_note()`
- `review_card()`
- `generate_quiz()`
- `grade_answer()`
- `save_resources_to_db()`

当多个函数组成一次用户操作时，中途失败会留下部分结果。例如项目已经保存，但环境清单或前三节课程生成失败。

建议规则：

- 简单单写操作可以暂时保留现有 commit 行为，避免第一阶段大改。
- 新增的组合应用用例必须成为事务所有者。
- 逐步把内部持久化 helper 改为 `flush()`，由用例统一 commit/rollback。
- 不要给所有函数增加传播式 `commit=True/False` 参数；这会扩大接口复杂度。

### 7.3 数据库实体不能直接当响应

SQLModel table 同时包含持久化细节：

- `roadmap_json` 是字符串
- `scope_node_ids`、`collection_ids` 是逗号分隔字符串
- `QuizQuestion.options` 是 JSON 字符串
- datetime 同时存在 naive UTC 和 aware UTC 转换
- status、stage、rating 只是普通字符串/整数

API Schema 应转换为：

- JSON 对象和数组
- 明确枚举
- ISO 8601 datetime
- 不暴露内部字段和密钥
- 所有响应都包含前端需要的稳定 ID

特别是 `load_roadmap()` 当前返回节点 code、状态和掌握度，但不返回节点数据库 ID，无法单独支撑前端节点操作。

### 7.4 状态和模型不变量不统一

当前代码存在多套状态定义：

- 模型注释：`pending|learning|reviewing|mastered|weak`
- `progress/study.py`：`pending|learning|mastered|weak|skipped`
- 看板和导出仍识别 `reviewing`

API 前需要建立唯一 `NodeStatus`，否则 Schema、数据库和前端会出现不同合法值。

其他缺少的约束包括：

- 节点 code 在项目内没有唯一约束。
- 笔记“每用户每节点一条”只靠查询约定，没有数据库唯一约束。
- node/project 组合没有一致性验证。
- difficulty、weekly_hours、mastery 没有统一输入校验。
- 外键没有声明级联删除，项目删除依赖 `project_ops.py` 手工清理。

### 7.5 测验闭环存在正确性缺口

`generate_quiz()` 读取多个 KnowledgeNode 后创建 `QuizQuestion`，但创建题目时没有填写 `node_id`。

`grade_answer()` 只有在 `q.node_id` 存在时才调用 `update_mastery()`。因此当前 AI 生成的题目通常不会回写节点掌握度，与模块注释声明的“批改后更新掌握度”不一致。

同时还需要处理：

- node_ids 是否属于同一个 project。
- node_ids 是否属于当前用户。
- LLM 返回题目数量、题型和选项是否合法。
- 一次批改中 `update_mastery()` 和 QuizAttempt 的事务边界。

测验 API 不应在修复这些问题前作为已完成闭环对外承诺。

### 7.6 后台线程不是任务接口

当前 `generate_summaries_background()` 和资料自动抓取使用 daemon thread：

- 没有 job ID
- 没有结构化状态
- 没有取消
- 没有去重
- 进程退出即丢失
- 错误只写日志或被转换为 `False`
- 重复请求可能并发写同一个节点

FastAPI 第一阶段不需要引入 Celery、Redis 等基础设施。可以实现小型 `InProcessJobRunner`，但它必须至少提供：

- job ID
- `queued/running/succeeded/failed/cancelled`
- 当前步骤和进度
- 错误摘要
- 同一资源的幂等键或并发保护
- 应用关闭时停止接收新任务并等待/取消运行任务

### 7.7 URL 抓取存在 SSRF 和资源消耗风险

`fetch_resource_content()` 接受任意 HTTP/HTTPS URL，允许重定向，直接下载响应后再解析。若直接暴露为 API，调用方可能访问：

- `127.0.0.1`、局域网和云元数据地址
- 本机其他管理端口
- 超大文件或无限重定向资源

API 适配前至少需要：

- 拒绝 loopback、私网、link-local 和非 HTTP(S) 地址
- 对重定向后的最终地址重复校验
- 限制响应大小、超时和重定向次数
- 限制支持的 Content-Type
- 资料生成进入任务系统

### 7.8 自动环境配置是高权限能力

`practice/auto_setup.py` 会执行 LLM 生成的 PowerShell 命令，并流式返回输出。它不是普通业务 API，而是本机代码执行入口。

迁移原则：

- 不提供“提交任意命令”的 HTTP 接口。
- 不允许 Next.js 自动调用执行接口。
- 命令生成和命令执行必须分成两个动作。
- 执行前显示精确命令、风险等级和影响范围，要求用户再次确认。
- 高风险命令默认拒绝，必要时再设计 allowlist。
- API 必须只监听 loopback，并增加每次启动随机令牌或同源保护。

该能力可以晚于学习核心迁移，不应阻塞第一阶段。

### 7.9 模型配置需要密钥安全设计

当前 QuickSetup Page 会读取 `.env` 中完整 API Key，并把它作为 password input 的值返回给页面。新 API 不应提供读取明文密钥的接口。

建议：

- `GET /settings/llm` 只返回 `configured: true` 和脱敏信息。
- `PUT /settings/llm` 接收新密钥并写入，不回显。
- 测试连接使用请求中本次提交的密钥，或已保存密钥，但不能把密钥转发到未经约束的任意 base URL。
- 配置和运行时刷新从 `QuickSetupPage` 提取为独立模块。

### 7.10 本地 API 也需要来源保护

仅绑定 `127.0.0.1` 不能替代安全控制。生产桌面模式建议：

- 前端与 API 尽量同源。
- 开发模式 CORS 只允许明确的本地前端 Origin。
- 修改、删除、配置、命令执行接口要求每次启动生成的本地 bearer token。
- 不使用 `Access-Control-Allow-Origin: *`。

## 8. 推荐的目标 seam

### 8.1 最小目录调整

遵循 KISS/YAGNI，第一阶段不需要建立复杂的 DDD 目录树。建议最小结构：

```text
api/
├── main.py
├── dependencies.py
├── errors.py
├── routers/
└── schemas/

learning_ext/
├── application/
│   ├── projects.py
│   ├── study.py
│   └── jobs.py
├── existing feature modules...
└── adapters/
    └── kotaemon_rag.py       # 到 RAG 阶段再创建
```

`application/` 不是简单转发层。只有需要组合多个模块、控制事务或生成任务的用户操作才进入这里。

### 8.2 不建议立即建立通用 Repository

当前只有一个 SQLModel/SQLite 实现，没有第二个真实持久化 adapter。为每张表建立 Repository 接口只会增加浅层转发代码。

第一阶段继续在应用用例中注入 `Session`，并提供少量有业务含义的查询/归属 guard，例如：

```text
get_project_for_user
get_node_for_user
get_card_for_user
```

当数据库实现真的需要变化时，再引入持久化 port。

### 8.3 值得建立的 port

以下 seam 已经存在生产实现和测试替身，或确定会有不同 adapter：

| Port | 生产 Adapter | 测试 Adapter | 理由 |
|---|---|---|---|
| LLM Gateway | 当前 OpenAI 兼容 client | Fake LLM | 现有测试已经大量替换 LLM |
| Job Runner | 本地线程池 | Immediate/Fake Runner | Page 线程将被 FastAPI 任务替换 |
| RAG Gateway | Kotaemon pipeline adapter | Fake RAG | 隔离 Kotaemon 内部状态和升级变化 |
| Resource Fetcher | 受限 HTTP/PDF fetcher | Fake Fetcher | 外部网络、安全和可测试性 |
| Config Store | `.env` 文件 | In-memory Store | 密钥写入与测试隔离 |

不要把这些内部 port 暴露给 Next.js。前端只看 HTTP 契约。

## 9. 推荐的 HTTP 契约

### 9.1 第一批短请求

| Method | Path | 对应现有逻辑 | 备注 |
|---|---|---|---|
| `GET` | `/api/v1/health` | 新增 | 服务和数据库状态 |
| `GET` | `/api/v1/projects` | 从 Page 项目列表查询抽取 | 第一条业务 API |
| `GET` | `/api/v1/projects/{project_id}` | LearningProject + progress | 用户归属校验 |
| `GET` | `/api/v1/projects/{project_id}/roadmap` | `load_roadmap` | 响应补 node ID |
| `GET` | `/api/v1/projects/{project_id}/workspace` | 从 Workbench 聚合逻辑抽取 | 只读，不触发生成 |
| `GET` | `/api/v1/nodes/{node_id}` | Workbench 节点详情 | 课程、笔记、资料分结构返回 |
| `PATCH` | `/api/v1/nodes/{node_id}/status` | `set_node_status` | 枚举校验、归属校验 |
| `PUT` | `/api/v1/nodes/{node_id}/note` | `save_note` | project_id 不由客户端信任 |
| `GET` | `/api/v1/reviews/due` | `get_due_cards` | 支持 project filter |
| `POST` | `/api/v1/cards/{card_id}/reviews` | `review_card` | rating 1-4 |
| `GET` | `/api/v1/dashboard` | `build_dashboard_data` | 返回 API DTO，不返回下拉框 tuple |

### 9.2 长任务

| Method | Path | 用途 |
|---|---|---|
| `POST` | `/api/v1/roadmap-draft-jobs` | 生成并审计路线草稿 |
| `POST` | `/api/v1/projects` | 从已确认草稿创建项目 |
| `POST` | `/api/v1/projects/{id}/preparation-jobs` | 环境清单、课程预生成 |
| `POST` | `/api/v1/nodes/{id}/lesson-jobs` | 生成/重新生成课程 |
| `POST` | `/api/v1/nodes/{id}/resource-jobs` | 生成并抓取参考资料 |
| `POST` | `/api/v1/nodes/{id}/audit-jobs` | 审计课程完整性 |
| `GET` | `/api/v1/jobs/{job_id}` | 查询状态和结果 |
| `GET` | `/api/v1/jobs/{job_id}/events` | SSE 进度事件 |

第一阶段优先使用 SSE，而不是同时引入 WebSocket：这些场景主要是服务器单向推送进度，SSE 的接口和重连语义更简单。需要双向中断或实时协作时再评估 WebSocket。

### 9.3 对话流

建议把学习助教和 Kotaemon RAG 分开：

```text
POST /api/v1/nodes/{id}/assistant/messages
POST /api/v1/rag/conversations/{id}/messages
```

二者可以使用相同的前端消息组件，但后端语义不同：

- 学习助教基于当前课程正文和短对话历史。
- RAG 对话基于 Kotaemon 索引、文件选择、reasoning pipeline、引用和会话状态。

不要用一个巨大的 `chat` 接口通过大量 mode 参数承载所有对话能力。

## 10. 第一条 API 应该怎么包

建议第一条真实业务 API 是：

```text
GET /api/v1/projects
```

原因：

- 没有 LLM、网络和后台任务。
- 只读，不会改变用户数据。
- 可以验证 FastAPI Session 注入、用户上下文、DTO 序列化和错误处理。
- 是 Next.js 路线页、工作台和看板共同需要的基础能力。
- 当前逻辑位于 `PathGeneratorPage._refresh_projects()`，正好可以验证“从 Page 抽业务查询”的方法。

推荐的应用接口不是返回 Gradio Dataframe 行，而是：

```text
list_projects(session, user_id, limit=50) -> list[ProjectSummary]
```

`ProjectSummary` 至少包含：

```json
{
  "id": 12,
  "title": "从零学习 Transformer",
  "topic": "Transformer",
  "status": "active",
  "progress": {
    "total": 24,
    "mastered": 6,
    "learning": 1,
    "pending": 17,
    "percent": 25.0
  },
  "created_at": "2026-08-24T10:00:00Z"
}
```

第二条建议是：

```text
GET /api/v1/projects/{project_id}/workspace
```

它应从 `StudyWorkbenchPage._on_project_change()`、`_build_nodes_data()`、`_load_env()` 中抽取结构化聚合查询，但不得包含 `gr.update()`、展示图标、Markdown 状态文本或自动生成副作用。

第三条建议是：

```text
PATCH /api/v1/nodes/{node_id}/status
```

它验证第一个写接口、状态枚举、资源归属和数据库事务。完成这三条后，再迁移路线生成任务，风险最低。

## 11. Kotaemon RAG 的单独结论

### 11.1 `learning_ext` 目前没有使用 RAG

虽然 `KnowledgeNode` 有 `collection_ids` 字段，但当前学习工作台：

- AI 助教只把节点正文前 2000 字和最近对话交给 `learning_ext.llm.chat()`。
- 参考资料是 LLM 推荐 URL 后通过 requests/PDF 解析抓取。
- 没有调用 `IndexManager`、retriever pipeline 或 Kotaemon conversation pipeline。

因此学习业务 API 可以先独立迁移，不需要等待 Kotaemon RAG API。

### 11.2 不要调用 `ChatPage.chat_fn()` 作为长期方案

`ChatPage.chat_fn()` 的参数包含：

- Gradio chat_history 结构
- settings state
- reasoning type、LLM、mindmap、citation、language
- chat state
- command state
- user ID
- 多个 selector 组件值

它还直接返回 Gradio 展示需要的 chat、refs、plot 和 state。这个接口过宽，且泄漏 UI 状态。

### 11.3 推荐 RAG Gateway

建议在只读 `kotaemon/` 外创建：

```text
KotaemonRagGateway
  - index_documents(...)
  - list_documents(...)
  - delete_document(...)
  - stream_answer(...)
```

Adapter 内部复用：

- `IndexManager` 加载索引
- `BaseIndex.get_indexing_pipeline()`
- retriever pipeline
- `BaseReasoning.get_pipeline()` 和 `stream()`

但在正式设计接口前必须做一个小型技术验证，确认：

- 如何在不创建 Gradio selector UI 的情况下传文件 ID。
- 如何构造默认 settings 和 reasoning state。
- conversation 的创建、持久化和历史格式。
- 引用、plot、mindmap 等 channel 如何转成 SSE 事件。
- FastAPI lifespan 内如何初始化并关闭 Kotaemon 全局资源。

该验证失败时，不能通过直接复制 `ChatPage` 来掩盖问题。

## 12. 推荐实施顺序

### 阶段 0：修正接口不变量

- 统一 NodeStatus。
- 增加项目/节点/卡片归属 guard。
- 修复 QuizQuestion 的 node_id 关联。
- 定义 API 错误类型。
- 定义独立 Pydantic Schema。

### 阶段 1：只读纵向切片

- FastAPI 健康检查。
- 项目列表。
- 项目详情/路线。
- 工作台只读聚合。
- Next.js 展示真实数据。

### 阶段 2：第一个写闭环

- 更新节点状态。
- 笔记读写。
- FSRS 到期卡片和评分。
- 接口测试覆盖归属和错误码。

### 阶段 3：长任务 seam

- In-process JobRunner。
- 路线生成/审计任务。
- 项目准备任务。
- 单节课程、资料和审计任务。
- SSE 进度。

### 阶段 4：学习增强功能

- AI 助教流式对话。
- 卡片生成。
- 修复后的测验闭环。
- 看板和导出。

### 阶段 5：Kotaemon RAG adapter

- 先技术验证，再实现资料库和 RAG 对话 API。
- 不修改 `kotaemon/`；所有兼容处理放在 adapter。
- 完成契约测试和本地真实索引 smoke test。

### 阶段 6：配置和高权限能力

- 模型配置 API。
- 密钥只写和脱敏状态。
- 自动环境配置单独安全设计；必要时可以继续留在桌面专用入口，不进入通用 Web API。

## 13. 测试策略

新测试应围绕 seam，而不是继续测试 Page 私有方法。

建议层次：

1. 应用用例测试：临时 SQLite + Fake LLM + Fake JobRunner。
2. FastAPI 契约测试：状态码、Schema、错误映射、用户归属。
3. 任务测试：状态转换、失败传播、幂等和重复提交。
4. RAG adapter 契约测试：Fake pipeline 验证事件转换。
5. 少量真实 smoke test：本地数据库、一个样例文档、真实索引流程。

现有 Page 测试不能立即删除。正确顺序是：

```text
先为新应用接口补等价测试
  -> Gradio Page 改为调用新接口
  -> 验证行为一致
  -> 最终移除 Gradio 后再删除对应 Page 测试
```

当前测试尚未覆盖的 API 关键风险：

- 用户越权访问
- HTTP Schema 和错误码
- 任务取消/重复提交/进程退出
- SSRF 和响应大小限制
- 密钥不回显
- CORS/Origin/本地令牌
- Kotaemon RAG 的无 Gradio 运行路径

## 14. 最终建议

不建议采用下面两种极端方案：

1. FastAPI Router 直接一对一包装所有现有 service 函数。这样会把内部 commit、SQLModel 实体、默认用户和后台线程问题直接公开。
2. FastAPI 直接调用 Gradio Page 私有方法。这样只是在 HTTP 外面继续运行 Gradio 架构，无法真正完成前后端分离。

推荐路线是：

```text
保留现有核心算法和多数 service 函数
  -> 把 Page 中的应用流程抽到 learning_ext/application
  -> FastAPI 只调用 application/service 接口
  -> 用独立 Schema 隔离数据库模型
  -> 长任务通过 Job Runner + SSE
  -> Kotaemon RAG 通过单独 Gateway 适配
```

这条路线符合现有阶段 5 目标，也符合当前代码现实：学习领域逻辑已经具备较高复用价值，但真正需要补的是稳定 seam，而不是重写全部 Python 核心。

## 附录 A：关键源码证据索引

以下索引用于后续开发时快速回到原始实现。行号对应本报告撰写时的工作区版本，代码继续演进后应以符号名搜索为准。

| 判断 | 关键源码位置 | 证据 |
|---|---|---|
| exe 和浏览器共用同一个 Gradio 后端 | `launcher.py:134`、`launcher.py:152`、`launcher.py:189`、`launcher.py:234` | 启动器以子进程运行 `custom_app.py`，随后由 PyWebView 或系统浏览器打开同一 URL |
| Gradio Page 是当前 UI 接入点 | `learning_ext/app.py:291`、`learning_ext/app.py:373` | `LearningApp` 继承 Kotaemon App，并在 `_build_learning_tabs` 中实例化学习页面 |
| 路线生成流程由 Page 编排 | `learning_ext/pages/path_generator.py:269`、`:274`、`:280`、`:316` | Page 串联生成、审计、保存和后续准备动作，而不是单一 service 用例 |
| 工作台读取动作夹带生成副作用 | `learning_ext/pages/study_workbench.py:952`、`:1005`、`:1079` | 节点选择后会检查并生成课程内容、启动资料生成线程 |
| 现有路线 service 可作为函数级接口 | `learning_ext/path_generator/service.py:36`、`:172`、`:357` | 已有生成、保存、读取路线的普通 Python 函数 |
| 底层写函数自行提交事务 | `learning_ext/path_generator/service.py:237`、`:352`、`learning_ext/progress/study.py:509`、`:775` | 多个 service 内部直接 `commit()`，组合用例难以统一控制事务边界 |
| 部分后台函数绕过调用方 Session | `learning_ext/progress/study.py:395`、`:405`、`:407`、`:533`、`:548`、`:550`、`:668`、`:681`、`:684` | 函数内部导入全局 engine 并新建 Session |
| 现有后台执行不是可管理任务 | `learning_ext/progress/study.py:605`、`:641`、`learning_ext/pages/study_workbench.py:1090`、`:1107` | 使用 daemon thread，没有持久化任务 ID、状态查询、取消和去重契约 |
| LLM 已有统一 facade，但仍绑定本地配置 | `learning_ext/llm/client.py:3`、`:87`、`:95`、`:98`、`:188` | `chat/chat_json` 统一调用，但直接读取配置并创建 OpenAI 客户端 |
| 数据模型不适合直接作为 HTTP Schema | `learning_ext/db/models.py:20`、`:33`、`:41`、`:59`、`:124`、`:140`、`:144`、`:154` | 表实体包含 JSON 字符串、逗号分隔字段和持久化细节 |
| 测验生成没有写入题目所属节点 | `learning_ext/quiz/service.py:96`、`:104`、`:112`、`:152` | 测验保存了范围，但新建 `QuizQuestion` 时未设置 `node_id`；评分只有在 `q.node_id` 存在时才更新掌握度 |
| URL 抓取不能原样暴露到 API | `learning_ext/notes/service.py:309`、`:316`、`:318`、`:319` | 接受 URL 并跟随重定向，尚未限制内网地址、响应体大小和目标来源 |
| 模型配置涉及密钥读写 | `learning_ext/pages/quick_setup.py:61`、`:75`、`:87`、`:95`、`:224` | Page 读取和写入 `.env`，并把 API Key 放入密码输入控件 |
| 自动配置具有本机命令执行能力 | `learning_ext/practice/auto_setup.py:41`、`:61`、`:72`、`:99` | LLM 生成 PowerShell 命令后可通过 `subprocess.Popen` 逐条执行 |
| Kotaemon 有可适配的底层抽象 | `kotaemon/libs/ktem/ktem/index/base.py:14`、`:112`、`:128`、`kotaemon/libs/ktem/ktem/reasoning/base.py:6`、`:36` | `BaseIndex` 和 `BaseReasoning` 暴露 indexing、retrieval、reasoning pipeline 接口 |
| 文件索引检索仍依赖 UI selector | `kotaemon/libs/ktem/ktem/index/file/index.py:462`、`:473` | `get_retriever_pipelines` 调用 `_selector_ui.get_selected_ids`，无 Gradio 适配需要单独验证 |
| Chat Page 不应成为业务 API | `kotaemon/libs/ktem/ktem/pages/chat/__init__.py:1286`、`:1296` | `chat_fn` 周边直接处理 selector UI、组件状态和页面级流程 |
