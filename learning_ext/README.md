# `learning_ext` 学习特化层

`learning_ext` 是 Learn Everything 的学习领域代码，位于 Kotaemon RAG 底座之上。它负责学习路线、知识节点、掌握度、间隔复习、测验、学习笔记和学习看板等业务能力；Kotaemon 负责应用运行时、Gradio 基础设施、LLM 配置和资料库/RAG 能力。

本目录的代码应当可以在未来被独立的 HTTP API 或 Next.js 前端复用。因此，页面负责 UI 编排，领域模块负责业务规则，数据模型负责持久化结构，LLM 调用统一经过 `learning_ext.llm`。

## 先看哪里

| 想了解什么 | 建议阅读顺序 |
| --- | --- |
| 应用如何启动 | `custom_app.py` → `app.py` → `bootstrap.py` |
| 一个 Tab 如何接入 | `pages/path_generator.py` → `app.py._build_learning_tabs` |
| 学习路线如何落库 | `path_generator/service.py` → `db/models.py` |
| 掌握度如何变化 | `progress/service.py` → `progress/study.py` |
| LLM 如何调用 | `llm/client.py` → 各领域模块的 `service.py` |
| 数据之间如何关联 | `db/models.py` 中的 `LearningProject` 和 `KnowledgeNode` |

## 架构总览

```text
用户操作
   │
   ▼
custom_app.py
   │ 创建 LearningApp
   ▼
app.py: LearningApp(KotaemonApp)
   │ 注册 Gradio Tab / 页面事件
   ▼
pages/                         # UI 适配层：BasePage 子类
   │ 调用普通 Python 函数
   ▼
领域服务                         # 不依赖 Gradio 的业务逻辑
path_generator  progress  fsrs_review  quiz  notes  dashboard
feynman         practice  exporter
   │                 │
   ├── db/models.py  │ SQLModel 表模型
   ├── llm/          │ 统一 LLM facade
   └── project_ops.py 级联清理/项目操作
   │
   ▼
ktem.db.engine.engine + kotaemon/.env 中的 LLM 配置
```

### 运行时边界

- `custom_app.py` 是后端入口：准备 `sys.path`、离线模式和环境变量，然后创建 `LearningApp`。
- `app.py` 是 Kotaemon 与学习功能之间的 UI 组合点。`LearningApp.__init__` 调用 `bootstrap.init_learning_ext()`，`_build_learning_tabs()` 注册学习页面。
- `bootstrap.py` 负责幂等初始化学习表、补齐本地 SQLite 的新增列，并检查 `fsrs` 是否可用。
- 学习表复用 Kotaemon 的 SQLModel engine，表名统一使用 `le_` 前缀；运行数据位于 `kotaemon/ktem_app_data/`，不属于源码目录。
- 领域服务可以依赖共享的数据库 engine 和 LLM facade，但不应把 Gradio 组件传入领域模块。
- `llm/client.py` 读取 `kotaemon/.env` 的 OpenAI 兼容配置并负责客户端、重试和 JSON 解析；它复用的是项目配置约定，不直接调用 Kotaemon 的 `llms manager`。

## 目录结构与职责

```text
learning_ext/
├── __init__.py              # 包级说明、底座导入所需的占位环境变量
├── app.py                   # LearningApp：页面注册、全局样式、事件接入
├── bootstrap.py             # 建表、SQLite 列补齐、FSRS 可用性检查
├── guide.py                 # 应用内“使用指南”Markdown
├── project_ops.py           # 项目学习数据的级联清理与删除
├── assets/
│   └── word_lookup.js       # 浏览器端划词/术语解释脚本，由 custom_app.py 注入
│
├── pages/                   # Gradio UI 适配层，每个页面继承 ktem.app.BasePage
│   ├── quick_setup.py       # 模型配置与连通性测试
│   ├── path_generator.py    # 学习路线 Tab
│   ├── study_workbench.py   # 节点内容、笔记、资料和学习推进工作台
│   ├── review.py            # FSRS 复习 Tab
│   ├── quiz.py              # 查漏测验 Tab
│   └── dashboard.py         # 学习看板 Tab
│
├── db/
│   └── models.py            # 所有 le_* SQLModel 表模型
├── llm/
│   └── client.py            # chat/chat_json/get_llm 统一 LLM facade
├── path_generator/
│   ├── service.py           # 路线生成、审计、保存、导入导出
│   └── prompts.py           # 路线生成和审计提示词
├── progress/
│   ├── service.py           # 掌握度、学习时长、热力图和项目概览
│   ├── study.py             # 节点状态机、可学习节点、课程/实操内容生成
│   └── audit.py             # 节点课程内容审计
├── fsrs_review/
│   └── service.py           # FSRS v6 卡片调度、复习记录和到期队列
├── quiz/
│   └── service.py           # AI 出题、批改、薄弱节点查询
├── notes/
│   └── service.py           # 用户笔记、资料推荐、URL 预览和术语解释
├── dashboard/
│   └── service.py           # 看板聚合数据和演示数据
├── feynman/
│   └── service.py           # 费曼对话和苏格拉底式引导
├── practice/
│   ├── service.py           # 实操计划生成
│   └── auto_setup.py        # 环境命令生成与逐条执行
└── exporter/
    └── service.py           # Anki、Markdown 和进度报告导出
```

## 核心领域对象

`LearningProject` 是一次学习主题的根对象。路线生成后，项目包含一组 `KnowledgeNode` 和表示前置依赖的 `KnowledgeEdge`：

```text
LearningProject
  └── KnowledgeNode ── KnowledgeEdge (source -> target，target 是前置节点)
        ├── Card ── ReviewLog                 # FSRS 记忆轨迹
        ├── Quiz ── QuizQuestion ── QuizAttempt # 测验与答题
        ├── ProgressRecord                     # 掌握度/学习时长时序
        ├── Task                               # 实操或环境任务
        ├── NodeNote                           # 用户笔记
        └── NodeResource                       # 参考资料
  └── DailyReport                              # 学习日报
```

主要表模型都在 `db/models.py`，表名以 `le_` 开头。`KnowledgeNode.mastery` 是当前综合掌握度，`status` 是节点状态；测验、复习和学习推进模块都会围绕这两个字段协作。

## 典型调用链

### 生成并保存学习路线

```text
PathGeneratorPage
  -> path_generator.generate_roadmap()
  -> learning_ext.llm.chat_json()
  -> path_generator.save_roadmap(session, ...)
  -> LearningProject / KnowledgeNode / KnowledgeEdge
```

### 一次复习或测验如何影响掌握度

```text
ReviewPage                  QuizPage
  -> fsrs_review.review_card  -> quiz.grade_answer
  -> ReviewLog / Card         -> QuizAttempt
                 \             /
                  -> progress.update_mastery()
                     -> KnowledgeNode.mastery
```

页面可以组合多个服务，但业务规则应留在领域模块中。例如新增“下一步学习”策略时，优先修改 `progress/study.py`，而不是在 `StudyWorkbenchPage` 中复制查询逻辑。

## 开发约定

1. 学习特化代码放在 `learning_ext/`，不要修改 `kotaemon/` 底座来承载学习业务。
2. 需要数据库的 service 函数通常把 `session: Session` 作为第一个参数；这样便于测试、组合调用和控制事务。
3. LLM 调用统一使用 `learning_ext.llm.chat` 或 `chat_json`，模型配置遵循 `kotaemon/.env` 的 OpenAI 兼容约定；不要在业务模块中直接创建客户端。
4. 新增或调整提示词时，放在对应模块的 `prompts.py`；当前路线模块已有该约定。
5. 新增 Tab：在 `pages/` 创建 `BasePage` 子类，在 `pages/__init__.py` 导出，并在 `app.py._build_learning_tabs()` 注册；事件绑定放在页面的 `on_register_events()`。
6. 数据模型变更先更新 `db/models.py`，再考虑 `bootstrap.py` 的 SQLite 兼容补列；不要把迁移逻辑藏在页面事件中。
7. `notes.service` 的 URL 抓取和 `practice.auto_setup` 的命令执行都涉及外部输入/本机副作用，修改时必须单独评估安全边界。

## 新功能落点判断

| 需求 | 主要落点 |
| --- | --- |
| 新增持久化实体或字段 | `db/models.py`，必要时 `bootstrap.py` |
| 新增学习规则/算法 | 对应领域目录的 `service.py` 或 `progress/study.py` |
| 新增 AI 输出格式 | 对应领域的 `prompts.py` 和 service 解析逻辑 |
| 新增用户界面 | `pages/`，再由 `app.py` 注册 |
| 新增跨模块项目清理 | `project_ops.py` |
| 新增导出格式 | `exporter/service.py` |
| 替换模型供应商或配置读取 | `llm/client.py`，不改各业务调用方 |

## 验证与演进

- 启动验证从 `run.bat` 或项目约定的 Kotaemon 虚拟环境进入；首次启动会加载较多底座依赖。
- 修改 `learning_ext` 或 `custom_app.py` 通常不需要重新打包 launcher；修改 `launcher.py` 才需要重新执行 `build_exe.bat`。
- 业务服务应优先做函数级测试，页面测试只覆盖事件编排和关键交互。完整测试入口可能受 Kotaemon 自带测试的导入环境影响，因此应区分学习模块测试与仓库全量测试。
- 当前页面层仍是 Gradio 适配层；未来迁移到 Next.js 时，优先复用领域 service、模型语义和 LLM facade，逐步替换 `pages/` 与 `app.py`，而不是把 Gradio 组件直接暴露给 API。
