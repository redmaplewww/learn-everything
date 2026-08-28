# 学习 Agent 架构文档

> 版本：阶段 0 完成（已切换为 Windows 桌面 exe 方案）
> 状态：本地运行 + exe 打包全部跑通，学习特化模块骨架就位

## 1. 总体架构

```
┌──────────────────────────────────────────────────────────┐
│           LearnEverything.exe (PyWebView 桌面窗口)        │
│                  launcher.py (主进程)                     │
└────────────────────────┬─────────────────────────────────┘
                         │ subprocess (Kotaemon venv python)
                         ▼
┌──────────────────────────────────────────────────────────┐
│              custom_app.py (Gradio 后端)                  │
│              http://127.0.0.1:7860                        │
│  Kotaemon 原生 Tab          学习特化 Tab (新增)           │
│  ┌──────┐┌──────┐   ┌─────────┐┌─────┐┌─────┐┌─────┐   │
│  │ Chat ││Files │   │🎯学习路线││🔄复习││📝测验││📊看板│   │
│  └──┬───┘└──┬───┘   └────┬────┘└──┬──┘└──┬──┘└──┬──┘   │
└─────┼───────┼────────────┼─────────┼──────┼──────┼───────┘
      │       │            │         │      │      │
┌─────▼───────▼────────────▼─────────▼──────▼──────▼───────┐
│              LearningApp (继承 Kotaemon App)              │
│         libs/ktem         +        learning_ext/          │
│  ┌─────────────┐         ┌──────────────────────────┐    │
│  │ reasoning   │         │ path_generator 路线生成   │    │
│  │ (ReAct等)   │         │ fsrs_review   FSRS复习    │    │
│  │ index/RAG   │         │ quiz          测验批改    │    │
│  │ llms mgr    │◄────────│ progress      掌握度     │    │
│  │ db engine   │  复用   │ feynman       费曼对话    │    │
│  │ (SQLite)    │         │ practice      实操辅助    │    │
│  └──────┬──────┘         │ exporter      导出        │    │
│         │                └──────────┬───────────────┘    │
│  ┌──────▼───────────────────────────▼───────────────┐    │
│  │   共享: SQLite + LLM (ktem.llms.manager.llms)     │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │ LLM Provider│ DeepSeek/GLM/OpenAI/Ollama
              └─────────────┘
```
```
┌──────────────────────────────────────────────────────────┐
│                    浏览器 :7860                           │
│  Kotaemon 原生 Tab          学习特化 Tab (新增)           │
│  ┌──────┐┌──────┐   ┌─────────┐┌─────┐┌─────┐┌─────┐   │
│  │ Chat ││Files │   │🎯学习路线││🔄复习││📝测验││📊看板│   │
│  └──┬───┘└──┬───┘   └────┬────┘└──┬──┘└──┬──┘└──┬──┘   │
└─────┼───────┼────────────┼─────────┼──────┼──────┼───────┘
      │       │            │         │      │      │
┌─────▼───────▼────────────▼─────────▼──────▼──────▼───────┐
│              LearningApp (继承 Kotaemon App)              │
│         libs/ktem         +        learning_ext/          │
│  ┌─────────────┐         ┌──────────────────────────┐    │
│  │ reasoning   │         │ path_generator 路线生成   │    │
│  │ (ReAct等)   │         │ fsrs_review   FSRS复习    │    │
│  │ index/RAG   │         │ quiz          测验批改    │    │
│  │ llms mgr    │◄────────│ progress      掌握度     │    │
│  │ db engine   │  复用   │ feynman       费曼对话    │    │
│  │ (SQLite)    │         │ practice      实操辅助    │    │
│  └──────┬──────┘         │ exporter      导出        │    │
│         │                └──────────┬───────────────┘    │
│         │                           │                    │
│  ┌──────▼───────────────────────────▼───────────────┐    │
│  │   共享: SQLite + LLM (ktem.llms.manager.llms)     │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │ LLM Provider│ DeepSeek/GLM/OpenAI/Ollama
              └─────────────┘
```

## 2. 核心设计决策

### 2.1 为什么 fork Kotaemon 作底座
Kotaemon (25.5k★) 已成熟实现：多用户登录、文档集合、混合 RAG(全文+向量+rerank)、
PDF 引用高亮、ReAct/ReWOO Agent、GraphRAG、Docker 部署。**这些占学习 Agent 所需
功能的 60%，复用可省去重写 RAG/文档/对话轮子。**

### 2.2 学习特化模块解耦
`learning_ext/` 独立于 Kotaemon 代码树，只通过三个公共接口耦合：
- `ktem.db.engine.engine` (共享 SQLite)
- `ktem.llms.manager.llms` (共享 LLM 配置)
- `ktem.app.BasePage` (Gradio Tab 基类)

**好处**：阶段 5 可把 `learning_ext` 抽出为独立 FastAPI 服务，配 Next.js 前端，
Kotaemon 降级为 RAG 微服务，迁移成本最小。

### 2.3 FSRS v6 而非 SM-2
采用 [Free Spaced Repetition Scheduler](https://github.com/open-spaced-repetition)
v6 算法 (pip 包 `fsrs`)，比 Anki 经典 SM-2 先进 30%+，是当前最强开源间隔重复算法。
核心参数：`stability`(记忆稳定性)、`difficulty`(难度)、`state`(新/学习/复习/重学)。

## 3. 目录结构

```
learn-everything/
├── launcher.py               # 桌面启动器 (PyWebView + 子进程编排)
├── custom_app.py             # 后端入口 (LearningApp，设置 sys.path/环境变量)
├── setup.bat                 # 首次环境初始化 (uv + venv + 依赖)
├── run.bat                   # 启动程序
├── build_exe.bat             # PyInstaller 打 launcher.exe
├── pack_portable.bat         # 组装完整便携版
│
├── kotaemon/                 # fork 的 Kotaemon 底座 (原样不动)
│   ├── .env                  # 本地配置 (LLM key)
│   ├── .venv/                # uv 创建的 Python 3.11 虚拟环境
│   ├── flowsettings.py       # Kotaemon 读取的配置 (路径/LLM/索引)
│   └── libs/{kotaemon,ktem}/ # RAG 引擎 + 应用层
│
├── learning_ext/             # 学习特化模块 (我们的核心代码)
│   ├── app.py                # LearningApp (继承 Kotaemon App，加学习 Tab)
│   ├── bootstrap.py          # 初始化 (建表、加载 fsrs)
│   ├── db/models.py          # 11 个学习数据模型
│   ├── llm/client.py         # LLM 调用封装 (复用 ktem llms)
│   ├── path_generator/       # 阶段1: 选题→学习路线 DAG
│   ├── fsrs_review/          # 阶段2: 艾宾浩斯记忆曲线
│   ├── quiz/                 # 阶段3: 查漏补缺测验
│   ├── progress/             # 阶段3: 进度+掌握度
│   ├── feynman/              # 阶段4: 费曼/苏格拉底对话
│   ├── practice/             # 阶段4: 环境/实操辅助
│   ├── exporter/             # 阶段4: 导出 Anki/MD/PDF
│   └── pages/                # Gradio Tab (路线Tab 已可用)
│
├── kotaemon/ktem_app_data/   # 运行时数据 (gitignore)
│   └── user_data/
│       ├── sql.db            # SQLite (Kotaemon + learning_ext 共用)
│       ├── files/            # 上传的文献
│       ├── docstore/         # LanceDB 全文索引
│       └── vectorstore/      # Chroma 向量库
│
└── docs/ARCHITECTURE.md      # 本文档
```

## 4. 运行机制（双进程模型）

```
用户双击                    PyWebView              Gradio 后端
LearnEverything.exe  ──>   launcher.py 主进程  ──>  custom_app.py 子进程
(原生 Win 窗口)            (调度+窗口)             (Kotaemon venv python)
                            │                        │
                            │ subprocess.Popen        │ demo.launch()
                            │ 日志转发                │ http://127.0.0.1:7860
                            │                        │
                            │ wait_for_server()  <────┘ 端口探测
                            │
                            │ webview.create_window(url)
                            ▼
                       桌面窗口打开
                       (Edge WebView2)
```

**为什么双进程而非线程**：
- Gradio/uvicorn 的信号处理与 PyWebView 冲突
- 子进程隔离，崩溃不影响窗口
- launcher.exe (PyInstaller) 和 Kotaemon venv 的 python 解耦，各自升级

## 5. 数据模型

全部复用 Kotaemon 的 SQLite engine，表名前缀 `le_` 避免冲突。

| 表 | 说明 | 关键字段 |
|---|---|---|
| `le_project` | 学习项目(选题) | topic, goal, weekly_hours, roadmap_json |
| `le_knode` | 知识图谱节点 | code, title, stage, est_hours, difficulty, **mastery**, status |
| `le_kedge` | 依赖边 | source_id→target_id (target 是前置) |
| `le_card` | FSRS 复习卡片 | front, back, **stability**, **difficulty**, state, next_review |
| `le_reviewlog` | 复习记录 | card_id, rating(1-4), stability, difficulty |
| `le_quiz` | 测验 | project_id, quiz_type, scope_node_ids |
| `le_quiz_question` | 题目 | qtype, stem, options, answer, explanation |
| `le_quiz_attempt` | 答题 | question_id, user_answer, **is_correct**, feedback |
| `le_progress` | 进度时序 | node_id, metric, value, recorded_at |
| `le_task` | 实操任务 | title, description, task_type, status |
| `le_daily_report` | 日报 | content, study_minutes, cards_reviewed |

**核心关系**：`User → Project → KnowledgeNode → {Card, Quiz, Task}`，
掌握度 `mastery` 横跨 `测验正确率 + FSRS稳定性 + 状态进度` 三信号加权。

## 6. Kotaemon 关键扩展点 (备忘)

| 扩展点 | 位置 | 用途 |
|---|---|---|
| `App.ui()` | `ktem/main.py` | **插入新 Tab** ← 我们用了这个 |
| `BasePage` | `ktem/app.py` | 编写 Tab 页面基类 |
| `KH_REASONINGS` | `flowsettings.py` | 注册新 reasoning pipeline |
| `ktem.llms.manager.llms` | `ktem/llms/manager.py` | 获取已配置 LLM |
| `ktem.db.engine.engine` | `ktem/db/engine.py` | 共享 DB engine |
| `IndexManager` | `ktem/index/` | 文档集合/RAG |
| 事件系统 | `subscribe_event` | 跨 Tab 通信 |

## 7. 阶段路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **0 脚手架** | 底座 + learning_ext 骨架 + 数据模型 + Windows exe 方案 | ✅ 完成 |
| **1 路线闭环** | 路线生成 Agent 调优、图谱可视化、节点状态机 | 🔜 进行中 |
| **2 认知巩固** | FSRS 复习队列完整 UI、AI 卡片提炼 | ⏳ 待做 |
| **3 查漏+看板** | 测验出题/批改、错题本、热力图、甘特图、AI 日报 | ⏳ 待做 |
| **4 增强** | 费曼对话、苏格拉底、实操辅助、导出 | ⏳ 待做 |
| **5 演进** | Kotaemon→RAG微服务、Next.js 独立前端 | ⏳ 待做 |

## 8. 开发约定

- **依赖注入**：所有 service 函数第一个参数是 `session: Session`，便于测试
- **LLM 调用**：统一走 `learning_ext.llm.chat/chat_json`，不直接碰 ktem
- **提示词**：复杂提示词放各模块 `prompts.py`，不混在业务代码里
- **新增 Tab**：在 `learning_ext/pages/` 加 BasePage 子类，在 `app.py._build_learning_tabs` 注册
- **数据迁移**：当前用 `SQLModel.metadata.create_all` 自动建表；量大后引入 Alembic
- **打包**：改完 launcher.py 需重新 `build_exe.bat`；改 learning_ext 或 custom_app.py 不用重打（venv 内直接生效）
