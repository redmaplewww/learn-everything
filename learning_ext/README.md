# `learning_ext` 学习特化层

`learning_ext` 是 Learn Everything 的学习领域代码，位于 Kotaemon RAG 底座之上。它负责学习路线、知识节点、掌握度、间隔复习、测验、学习笔记和学习看板等业务能力；Kotaemon 负责运行时、LLM 配置和资料库/RAG 能力。当前界面由 Next.js 提供，经 FastAPI 调用本目录的领域服务。

本目录的代码应当可以在未来被独立的 HTTP API 或 Next.js 前端复用。因此，页面负责 UI 编排，领域模块负责业务规则，数据模型负责持久化结构，LLM 调用统一经过 `learning_ext.llm`。

## 先看哪里

| 想了解什么 | 建议阅读顺序 |
| --- | --- |
| 浏览器应用如何启动 | `start.bat` → `scripts/start_frontend_dev.py` → `api/main.py` → `bootstrap.py` |
| 前后端如何通信 | `frontend/` → `api/main.py` → `application/` |
| 学习路线如何落库 | `path_generator/service.py` → `db/models.py` |
| 掌握度如何变化 | `progress/service.py` → `progress/study.py` |
| LLM 如何调用 | `llm/client.py` → 各领域模块的 `service.py` |
| 数据之间如何关联 | `db/models.py` 中的 `LearningProject` 和 `KnowledgeNode` |

## 架构总览

```text
浏览器（http://127.0.0.1:3000）
   │
   ▼
frontend/ (Next.js)
   ▼
api/main.py (FastAPI)
   │ 调用 application / 领域服务
   ▼
领域服务                         # 不依赖 UI 的业务逻辑
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

- `scripts/start_frontend_dev.py` 是日常开发入口：启动 Next.js（3000）与 FastAPI（8000），并设置 `LEARNING_DEV_MODE=1`，让 8000 只提供 API。
- `api/main.py` 是浏览器应用的后端入口：注册 `/api/v1` 路由，在启动生命周期中调用 `bootstrap.init_learning_ext()`。
- `bootstrap.py` 负责幂等初始化学习表、补齐本地 SQLite 的新增列，并检查 `fsrs` 是否可用。
- 学习表复用 Kotaemon 的 SQLModel engine，表名统一使用 `le_` 前缀；运行数据位于 `kotaemon/ktem_app_data/`，不属于源码目录。
- 领域服务可以依赖共享的数据库 engine 和 LLM facade，但不应把 Next.js 或 FastAPI 组件传入领域模块。
- `llm/client.py` 读取 `kotaemon/.env` 的 OpenAI 兼容配置并负责客户端、重试和 JSON 解析；它复用的是项目配置约定，不直接调用 Kotaemon 的 `llms manager`。

## 目录结构与职责

```text
learning_ext/
├── __init__.py              # 包级说明、底座导入所需的占位环境变量
├── bootstrap.py             # 建表、SQLite 列补齐、FSRS 可用性检查
├── guide.py                 # 应用内“使用指南”Markdown
├── project_ops.py           # 项目学习数据的级联清理与删除
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
RoadmapCreation (Next.js)
  -> api/routers/roadmaps.py
  -> learning_ext.llm.chat_json()
  -> path_generator.save_roadmap(session, ...)
  -> LearningProject / KnowledgeNode / KnowledgeEdge
```

### 一次复习或测验如何影响掌握度

```text
ReviewPanel (Next.js)       QuizPanel (Next.js)
  -> fsrs_review.review_card  -> quiz.grade_answer
  -> ReviewLog / Card         -> QuizAttempt
                 \             /
                  -> progress.update_mastery()
                     -> KnowledgeNode.mastery
```

前端组件只负责交互和展示，业务规则应留在领域模块中。例如新增“下一步学习”策略时，优先修改 `progress/study.py`。

## 开发约定

1. 学习特化代码放在 `learning_ext/`，不要修改 `kotaemon/` 底座来承载学习业务。
2. 需要数据库的 service 函数通常把 `session: Session` 作为第一个参数；这样便于测试、组合调用和控制事务。
3. LLM 调用统一使用 `learning_ext.llm.chat` 或 `chat_json`，模型配置遵循 `kotaemon/.env` 的 OpenAI 兼容约定；不要在业务模块中直接创建客户端。
4. 新增或调整提示词时，放在对应模块的 `prompts.py`；当前路线模块已有该约定。
5. 新增界面功能：在 `frontend/features/` 添加组件，通过 `api/routers/` 暴露所需 HTTP 契约。
6. 数据模型变更先更新 `db/models.py`，再考虑 `bootstrap.py` 的 SQLite 兼容补列；不要把迁移逻辑藏在页面事件中。
7. `notes.service` 的 URL 抓取和 `practice.auto_setup` 的命令执行都涉及外部输入/本机副作用，修改时必须单独评估安全边界。

## 新功能落点判断

| 需求 | 主要落点 |
| --- | --- |
| 新增持久化实体或字段 | `db/models.py`，必要时 `bootstrap.py` |
| 新增学习规则/算法 | 对应领域目录的 `service.py` 或 `progress/study.py` |
| 新增 AI 输出格式 | 对应领域的 `prompts.py` 和 service 解析逻辑 |
| 新增用户界面 | `frontend/features/`，并在 `api/` 增加契约 |
| 新增跨模块项目清理 | `project_ops.py` |
| 新增导出格式 | `exporter/service.py` |
| 替换模型供应商或配置读取 | `llm/client.py`，不改各业务调用方 |

## 验证与演进

- 日常启动验证使用 `start.bat`，访问 `http://127.0.0.1:3000`；8000 仅用于 API 调试。首次启动会加载较多底座依赖。
- 修改 `learning_ext` 或 `api/` 后重启开发脚本即可生效；修改桌面打包路径的 `launcher.py` 后才需要重新执行 `build_exe.bat`。
- 业务服务应优先做函数级测试，前端组件使用 Vitest/React Testing Library 覆盖交互。完整测试入口可能受 Kotaemon 自带测试的导入环境影响，因此应区分学习模块测试与仓库全量测试。
- 当前页面层为 `frontend/`（Next.js），所有业务访问统一通过 `api/` 的 FastAPI 契约。
