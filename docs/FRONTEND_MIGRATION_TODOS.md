# 前端重构 TODO 清单

> 状态：待执行
> 创建日期：2026-08-26
> 方案基线：`docs/FRONTEND_MIGRATION_PLAN.md`
> 源码探索：`docs/LEARNING_EXT_API_WRAPPING_REPORT.md`

## 一、文档职责与执行规则

### （一）文档职责

本文档负责把前端重构方案展开为可领取、可执行、可验证的工程任务。

相关文档职责：

- `FRONTEND_MIGRATION_PLAN.md`：解释目标架构、重构边界和迁移顺序。
- `LEARNING_EXT_API_WRAPPING_REPORT.md`：记录现有源码、复用能力、耦合点和风险证据。
- `FRONTEND_MIGRATION_TODOS.md`：记录具体改什么、依赖什么、如何完成和如何验证。

本文档不重新讨论已经确认的架构方向。迁移期间统一遵循：

```text
Gradio Page ─┐
             ├─> learning_ext/application -> learning_ext/service
Next.js API ─┘
```

最终在全部切片迁移并验证后移除 Gradio。

### （一）当前交付范围调整（2026-08-28）

本轮只负责浏览器前端、FastAPI、application 和项目侧 service 的迁移与验证。PyWebView 真窗口、exe 构建、便携版组装、桌面端启动矩阵不属于当前前后端交付范围，不作为浏览器前后端完成的阻塞条件；相关任务保留在文档中并暂停，待单独安排桌面发布工作时再执行。Gradio 仍作为迁移期间的回退入口保留，当前也不执行删除。

### （二）LLM 与外部网络可靠性原则（2026-08-28）

LLM、向量模型、资料抓取和 Kotaemon 索引均按“不可靠外部依赖”处理。任何会触发模型或网络的前后端用例，都必须明确记录并实现：超时边界、可取消边界、有限重试与退避、失败后的可恢复状态、进程重启后的处理方式，以及不会泄露密钥和提示词的结构化日志。异常必须同时具备：

- 后端 logger/控制台可定位的错误记录（请求、任务、节点、阶段、重试次数和根因）；
- API 可识别的错误类型、状态和任务 ID；
- 前端可理解的失败提示、当前状态、重试/取消入口和下一步建议。

读取接口不得隐式触发 LLM、网络抓取或索引。长任务不得只依赖匿名 daemon 线程；任务必须可查询、可取消、可重试，并在服务重启后能明确恢复、重新排队或标记为中断，不允许静默丢失。

### （二）任务状态

任务使用标准 Markdown 复选框：

- `[ ]`：任务尚未完成。
- `[x]`：任务已经完成并有验证记录。

进行中、阻塞和暂停状态写在任务的“执行记录”中，不使用非标准复选框。只有同时满足任务完成标准并记录验证结果后，才能勾选为 `[x]`。

### （三）任务执行规则

1. 任务编号保持稳定。新增任务使用所在阶段尚未使用的编号，不重排已有编号。
2. 按依赖关系执行。前置任务未完成时，不开始会依赖其接口或结果的后续任务。
3. 每次只推进一个可验收切片，避免同时改动 application、全部 Page、全部 API 和全部前端页面。
4. 迁移期间不修改 `kotaemon/` 底座源码；项目侧适配代码放在 `learning_ext/` 或 `api/`。
5. 不复制业务规则。FastAPI Router 和 Next.js 不重新实现 Page 或 service 中已有的业务逻辑。
6. 保留用户已有工作区变更。每个阶段开始前检查 `git status`，只修改任务明确涉及的文件。
7. 不在本计划内自动创建分支、提交或推送；相关操作需要单独确认。
8. 源码行号是 2026-08-25 至 2026-08-26 工作区的定位辅助。代码变化后优先按路径和符号名搜索。

### （四）单项任务记录模板

完成任务后，在任务下追加执行记录：

```markdown
- [x] `PX-XX` 实现某个任务
  - 实际修改：列出文件和关键符号。
  - 自动验证：列出命令和结果。
  - 手工验证：列出页面操作和观察结果。
  - 遗留问题：没有则写“无”。
  - 完成日期：YYYY-MM-DD。
```

### （五）阶段门禁

每个阶段需要满足该阶段完成标准，才能把后续阶段作为主工作面。允许为技术验证提前创建小型 PoC，但 PoC 不代表前置阶段已经完成。

```text
P0 基线
  -> P1 Application 接缝
    -> P2 第一条 API + Next.js 切片
      -> P3 路线创建
        -> P4 学习核心
          -> P5 Kotaemon 能力
            -> P6 桌面端切换
              -> P7 移除 Gradio
```

## 二、进度总览

### （一）阶段状态

| 阶段 | 状态 | 当前目标 | 进入下一阶段的条件 |
|---|---|---|---|
| P0 重构基线 | 已完成 | 首批用例契约、自动测试基线和隔离 Gradio 回归已记录 | 可进入 P1 |
| P1 Application 接缝 | 已完成 | 首批四个用例已由两个 Gradio Page 共享调用 | 可进入 P2 |
| P2 第一条 API 与 Next.js 切片 | 已完成 | 已完成真实项目读取和节点状态 API 闭环 | 可进入 P3 |
| P3 路线创建流程 | 已完成 | 路线生成、审计、保存和内容准备已共用 application | 可进入 P4 |
| P4 学习核心功能 | 已完成 | 工作台、复习、测验、看板与导出已迁移到 Next.js | 可进入 P5 |
| P5 Kotaemon 能力 | 已完成 | 问答、资料库和必要模型配置已在 Next.js 迁移并验证 | 可进入 P6 |
| P6 浏览器与桌面端切换 | 前后端部分完成，桌面端暂停 | 浏览器前后端链路已完成；不推进 PyWebView、exe 和便携版 | 如重新纳入桌面交付，再执行桌面启动和打包验证 |
| P7 移除 Gradio | 未开始 | 删除旧 UI 和启动链 | 主运行链路不再渲染 Gradio |

### （二）当前已知边界

- `learning_ext/application/`、`api/` 和 `frontend/` 已创建；浏览器端项目读取、路线、工作台、节点状态、复习、测验、看板、资料和问答链路已完成首轮迁移。
- `learning_ext/*/service.py` 和 `learning_ext/progress/study.py` 已包含大部分核心能力。
- 首批 Page 编排入口集中在 `path_generator.py` 和 `study_workbench.py`。
- 项目当前是本地单用户模式，本轮迁移不增加账号、多用户权限或多租户设计。
- 数据继续使用现有 SQLite 和 Kotaemon SQLModel engine，不引入新的数据库客户端或数据库迁移项目。
- 正式 `kotaemon/ktem_app_data/user_data/sql.db` 当前无法由 SQLite/SQLModel 打开；浏览器前后端验证使用 `.tmp/manual-app-data` 隔离恢复库，正式库未被覆盖。
- 路线/课程/资料等长任务的持久化任务状态、取消、超时和进程重启恢复仍未统一；读取接口不应隐式触发生成。
- 本次 `kotaemon/.venv/Scripts/python.exe -m pytest -q tests` 输出 `139 passed, 6 skipped, 1 warning`，输出完成后进程未自然退出，已用 Ctrl+C 结束，退出码 1；该行为与仓库既有后台线程残留问题一致。
- 直接执行仓库全量 `pytest -q` 仍在收集 `kotaemon/libs/ktem/ktem_tests/test_qa.py` 时因顶层 `index` 导入失败而退出码 1；本项目测试与底座测试需要区分。

### （三）第一批执行切片

第一批拆成两个小切片，避免一次性改动全部工作台逻辑。

#### 切片 A：项目列表与路线读取

```text
list_projects
get_project_roadmap
    -> Application 测试
    -> PathGeneratorPage 接入
    -> Gradio 回归
```

#### 切片 B：工作台读取与节点状态

```text
get_project_workspace
update_node_status
    -> Application 测试
    -> StudyWorkbenchPage 接入
    -> Gradio 回归
```

切片 A 完成后再开始切片 B。P2 的 FastAPI 和 Next.js 只接入已经通过 Gradio 回归的 application 用例。

## 三、P0：重构基线

### （一）工作区与变更范围

- [x] `P0-01` 记录开始执行时的工作区状态
  - 目标位置：仓库根目录。
  - 前置依赖：无。
  - 实施内容：执行 `git status --short --untracked-files=all`，区分用户已有变更、本次允许修改的文件和生成文件。
  - 完成标准：执行记录中列出不可覆盖的现有变更；后续任务范围清晰。
  - 验证方式：再次运行 `git status`，确认没有在基线检查中产生修改。
  - 实际修改：无；记录了既有修改 `build_exe.bat`、`docs/ARCHITECTURE.md`、`launcher.py`、`pack_portable.bat` 及既有未跟踪文档/测试文件，未覆盖。
  - 自动验证：`git status --short --untracked-files=all`；基线检查没有产生额外文件。
  - 手工验证：确认本次只修改 `learning_ext/application/`、两个 Page、测试 fixture、application 测试和本 TODO 文档。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P0-02` 确认开发环境和测试解释器
  - 目标位置：`kotaemon/.venv/`、现有开发脚本和测试配置。
  - 前置依赖：`P0-01`。
  - 实施内容：确认应使用的 Python、pytest、Node.js 和包管理器版本；只记录已实际验证的环境。
  - 完成标准：后续任务有确定的 Python 测试命令；前端阶段有确定的 Node.js 运行时来源。
  - 验证方式：记录版本命令的实际输出。
  - 实际修改：无。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe --version` 输出 `Python 3.11.9`；pytest `8.4.2`；Node `v22.20.0`；npm `11.11.0`；corepack `0.34.0`。
  - 手工验证：确认后续 Python 测试统一使用 `kotaemon/.venv/Scripts/python.exe`；前端阶段可使用 Node/npm，但当前尚未创建 frontend。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

### （二）现有调用链基线

- [x] `P0-03` 固化路线页面调用链
  - 目标文件：`learning_ext/pages/path_generator.py`。
  - 重点符号：`_handle_generate:269`、`_handle_refine:299`、`_handle_save_with_setup:316`、`_handle_load:445`、`_handle_audit_project:522`、`_refresh_projects:669`。
  - 前置依赖：`P0-01`。
  - 实施内容：记录每个事件函数的输入、调用的 service、写库行为、后台行为和 Gradio 输出。
  - 完成标准：可以准确指出哪些代码留在 Page、哪些代码进入 application。
  - 验证方式：源码符号检查；不修改生产代码。
  - 实际修改：按符号检查生成、调整、保存、读取、审计和项目刷新路径；确定 `list_projects`、`get_project_roadmap` 为首批读取接缝，生成/保存/审计仍留在 Page 直到后续切片。
  - 自动验证：`rg` 检查 `learning_ext/pages/path_generator.py` 目标符号和 service 调用。
  - 手工验证：真实 Gradio 外壳验证见 `P0-12`；节点级操作尚未执行。
  - 遗留问题：无项目测试数据，节点级手工回归仍待隔离配置。
  - 完成日期：2026-08-26。

- [x] `P0-04` 固化工作台调用链
  - 目标文件：`learning_ext/pages/study_workbench.py`。
  - 重点符号：`_auto_init:733`、`_on_project_change:853`、`_on_node_select:952`、`_ensure_course_content:1005`、`_ensure_resources_background:1079`、`_set_status:1347`。
  - 前置依赖：`P0-01`。
  - 实施内容：区分纯读取、写入、LLM 生成、网络抓取和后台线程行为。
  - 完成标准：明确工作台读取结果的字段，以及读取动作当前夹带的副作用。
  - 验证方式：源码符号检查；不修改生产代码。
  - 实际修改：确认项目切换、工作台聚合和状态更新的读取/写入边界；课程生成和资料抓取副作用保留为后续切片。
  - 自动验证：`rg` 检查 `_auto_init`、`_on_project_change`、`_on_node_select`、`_ensure_course_content`、`_ensure_resources_background`、`_set_status` 及 service 调用。
  - 手工验证：真实 Gradio 外壳验证见 `P0-12`；节点级操作尚未执行。
  - 遗留问题：读取页面仍会在预加载阶段触发历史生成行为，后续需由长任务切片处理。
  - 完成日期：2026-08-26。

- [x] `P0-05` 固化复习、测验和看板调用链
  - 目标文件：`learning_ext/pages/review.py`、`quiz.py`、`dashboard.py`。
  - 重点符号：`ReviewPage._load_next:111`、`_review:128`、`QuizPage.on_register_events:53`、`DashboardPage._load_dashboard:83`。
  - 前置依赖：`P0-01`。
  - 实施内容：确认哪些 Page 已真实调用 service，哪些页面仍是未完成占位。
  - 完成标准：P4 不把未完成的 Gradio 页面错误视为可直接复刻的功能基线。
  - 验证方式：源码检查和现有测试对照。
  - 实际修改：确认复习页调用 FSRS service，测验页当前主要注册 UI 事件，看板页调用 dashboard service；未把未完成页面当作 P1 基线。
  - 自动验证：`rg` 检查目标符号；项目测试基线见 `P0-10`。
  - 手工验证：本任务不要求操作复习/测验/看板页面。
  - 遗留问题：P4 仍需补齐测验和看板的 application 契约。
  - 完成日期：2026-08-26。

### （三）首批用例契约

- [x] `P0-06` 定义 `list_projects` 用例契约
  - 现有位置：`path_generator.py:_refresh_projects:669`、`study_workbench.py:_refresh_projects:841`。
  - 前置依赖：`P0-03`、`P0-04`。
  - 实施内容：确定项目摘要字段、排序规则、空列表行为和返回类型。
  - 完成标准：Gradio 路线页和工作台可以使用同一结果，不在 application 中拼接 Gradio 文本。
  - 验证方式：用测试数据对比两个旧 Page 的项目顺序和显示信息。
  - 实际修改：契约固定为 `list_projects(session, user_id="default", limit=50) -> list[ProjectSummary]`，按项目 ID 倒序，空库返回空列表，摘要包含进度结构。
  - 自动验证：`tests/test_application_projects.py::test_list_projects_is_sorted_and_returns_structured_summary`、用户边界测试通过。
  - 手工验证：页面接入后方法级回归通过；真实节点级 Gradio 回归未完成。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P0-07` 定义 `get_project_roadmap` 用例契约
  - 现有位置：`path_generator.py:_handle_load:445`；`path_generator/service.py:load_roadmap:357`。
  - 前置依赖：`P0-03`。
  - 实施内容：确定项目不存在、路线 JSON、节点 ID、节点排序和阶段信息的行为。
  - 完成标准：返回结构可以同时支持 Gradio 渲染和未来 API Schema。
  - 验证方式：至少覆盖正常项目和不存在项目。
  - 实际修改：契约固定为结构化 `ProjectRoadmap`，包含 `project_id`、`summary`、`stages` 和带持久化 `id` 的排序节点；不存在项目抛出 `ProjectNotFoundError`。
  - 自动验证：正常和不存在项目 application 测试通过。
  - 手工验证：路线 Page 方法回归通过；真实节点级 Gradio 回归未完成。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P0-08` 定义 `get_project_workspace` 用例契约
  - 现有位置：`study_workbench.py:_auto_init:733`、`_on_project_change:853`、`_build_nodes_data:644`。
  - 前置依赖：`P0-04`。
  - 实施内容：列出项目、节点、进度、环境任务、课程、实操、笔记和资料字段；明确读取不触发生成。
  - 完成标准：工作台聚合结果与 UI 渲染结果分离。
  - 验证方式：覆盖有节点项目、无节点项目和不存在项目。
  - 实际修改：契约固定为 `ProjectWorkspace`，包含项目、进度、环境、节点及节点的课程/实操/笔记/资料摘要；读取不触发 LLM、网络抓取或后台任务。
  - 自动验证：有节点聚合和不存在项目测试通过；空节点逻辑由查询实现覆盖。
  - 手工验证：工作台方法级回归通过；真实节点级 Gradio 回归未完成。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P0-09` 定义 `update_node_status` 用例契约
  - 现有位置：`study_workbench.py:_set_status:1347`；`progress/study.py:set_node_status:72`。
  - 前置依赖：`P0-04`。
  - 实施内容：确认允许状态、非法状态、节点不存在和更新后返回内容。
  - 完成标准：application 结果足以让 Gradio 刷新节点和进度，不包含 `gr.update()`。
  - 验证方式：覆盖合法状态、非法状态和不存在节点。
  - 实际修改：契约固定为 `update_node_status(session, node_id, status, user_id="default") -> NodeStatusUpdate`，返回更新节点和刷新后的工作台；非法状态沿用 service 的 `ValueError`，不存在节点抛出 `NodeNotFoundError`。
  - 自动验证：合法、非法和不存在节点测试通过。
  - 手工验证：状态 Page 方法回归通过；真实节点级 Gradio 回归未完成。
  - 遗留问题：掌握后后台课程生成仍保留在 Page，后续长任务切片再迁移。
  - 完成日期：2026-08-26。

### （四）测试和手工回归基线

- [x] `P0-10` 运行项目自有测试基线
  - 目标位置：`tests/`。
  - 前置依赖：`P0-02`。
  - 实施内容：运行项目自有测试；记录通过、跳过、警告、退出码和残留进程情况。
  - 完成标准：后续回归有可比较的测试结果，不能只记录断言输出而忽略异常退出。
  - 验证方式：执行确定的 `pytest` 命令并保存摘要。
  - 实际修改：无。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests` 输出 `139 passed, 6 skipped, 1 warning in 32.56s`；输出完成后未自然退出，Ctrl+C 后退出码 1。全仓 `pytest -q` 另因 Kotaemon 自带测试顶层 `index` 导入失败退出码 1。
  - 手工验证：无。
  - 遗留问题：需治理测试残留后台线程；全仓测试需单独配置底座导入路径。
  - 完成日期：2026-08-26。

- [x] `P0-11` 确认 application 测试 fixture
  - 目标文件：`tests/conftest.py` 和首批 service 测试。
  - 前置依赖：`P0-02`、`P0-10`。
  - 实施内容：确认临时 SQLite、测试模型建表、测试数据和 LLM mock 的复用方式。
  - 完成标准：首批 application 测试不访问真实 LLM，不写入用户实际数据库。
  - 验证方式：新增最小 fixture smoke test，或复用已有 fixture 并记录依据。
  - 实际修改：新增 `tests/test_application_projects.py`，复用临时 SQLite、SQLModel 建表和 `mock_llm` fixture；补充 `le_note`、`le_resource` 清理，避免跨测试污染。
  - 自动验证：application 测试 8 项通过；`compileall` 通过。
  - 手工验证：确认测试未读取真实 `kotaemon/ktem_app_data`。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P0-12` 建立首批 Gradio 手工回归清单
  - 目标页面：学习路线、学习工作台。
  - 前置依赖：`P0-03`、`P0-04`。
  - 实施内容：记录项目列表加载、路线读取、项目切换、节点列表、节点状态更新的操作和期望结果。
  - 完成标准：P1 每完成一个切片都能执行相同操作进行对比。
  - 验证方式：在当前 Gradio 页面执行一次并记录观察结果。
  - 实际修改：建立并执行项目列表加载、路线读取、项目切换、节点列表和节点状态更新清单；隔离配置和数据仅位于 `.tmp/manual-app-data`。
  - 自动验证：`tests/test_application_projects.py` 9 项通过，退出码 0；`tests/test_pages.py` 36 项通过、1 个既有 tokenizer 警告，退出码 0。
  - 手工验证：以 `THEFLOW_SETTINGS_MODULE=manual_flowsettings` 启动 `custom_app.py`；刷新显示 `#1 手工回归项目`，加载路线显示 `[1.1] 测试节点`，工作台显示项目、进度和课程，点击“学习中”后节点、下拉标签和进度同时刷新。
  - 遗留问题：工作台首次 load 的旧版预加载副作用仍属于后续长任务迁移范围，但不影响本切片的隔离回归。
  - 完成日期：2026-08-27。

### （五）P0 完成标准

- [x] `P0-GATE` 完成 P0 阶段门禁
  - 前置依赖：`P0-01` 至 `P0-12`。
  - 完成标准：首批四个用例契约明确；测试基线和手工回归清单可重复执行；工作区现有变更边界已记录。
  - 验证方式：审阅 P0 执行记录，不要求创建 FastAPI 或 Next.js。
  - 实际修改：无额外生产代码；完成基线记录和隔离手工回归。
  - 自动验证：项目自有测试基线、application 测试和 Page 测试结果均已记录；全仓底座测试导入问题仍单独记录。
  - 手工验证：隔离 Gradio 回归覆盖项目列表、路线读取、工作台读取和状态更新。
  - 遗留问题：项目全量 `tests` 命令仍会在断言结束后残留线程，已记录真实退出码；P1 使用独立可退出的定向测试。
  - 完成日期：2026-08-27。

## 四、P1：建立 Application 接缝

> 工作区开始执行前已存在 `launcher.py`、`build_exe.bat`、`pack_portable.bat` 等启动/打包变更；本次 P0/P1 未修改、回退或验证这些文件，启动链调整仍属于 P6 范围。

### （一）Application 包结构

- [x] `P1-01` 创建 `learning_ext/application/` 包
  - 目标文件：`learning_ext/application/__init__.py`。
  - 前置依赖：`P0-GATE`。
  - 实施内容：建立客户端无关的应用用例包；包级说明明确不能导入 Gradio。
  - 完成标准：包可以被测试和 Page 导入，没有循环依赖。
  - 验证方式：Python import smoke test。
  - 实际修改：新增 `learning_ext/application/__init__.py`，导出首批用例和错误类型，包说明明确不依赖客户端。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -c "from learning_ext.application import *"` 输出 `application import ok`。
  - 手工验证：无 Gradio 依赖。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P1-02` 创建项目与路线 application 模块
  - 目标文件：`learning_ext/application/projects.py`、`roadmap.py`。
  - 前置依赖：`P1-01`。
  - 实施内容：按用例职责放置项目列表、工作台和路线读取逻辑，不建立空的通用 Repository。
  - 完成标准：模块边界与 P0 契约一致，未复制 service 算法。
  - 验证方式：模块导入测试和依赖扫描。
  - 实际修改：新增 `learning_ext/application/projects.py` 和 `roadmap.py`，复用现有 service，不建立 Repository 抽象。
  - 自动验证：application import smoke test、8 项 application 测试通过。
  - 手工验证：代码审阅确认未修改 `kotaemon/`。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P1-03` 定义首批 application 返回类型
  - 目标文件：优先放在对应 application 模块；只有跨模块稳定复用时才建立公共类型文件。
  - 前置依赖：`P0-06` 至 `P0-09`、`P1-02`。
  - 实施内容：定义项目摘要、路线详情、工作台聚合和节点状态结果；不引用 Gradio 类型。
  - 完成标准：Page 可以基于结果渲染，未来 API 可以转换为 Schema。
  - 验证方式：类型构造测试；`rg` 确认 application 不导入 `gradio`。
  - 实际修改：定义 `ProjectSummary`、`ProjectRoadmap`、`ProjectWorkspace`、`WorkspaceNode`、`NodeStatusUpdate` 及可预期错误类型；通过 `to_dict()` 提供 API 转换边界。
  - 自动验证：类型构造覆盖 application 测试；`rg -n "gradio|learning_ext\.pages|fastapi|frontend" learning_ext/application` 无命中。
  - 手工验证：确认返回值不含 SQLModel 实体和 `gr.update()`。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

### （二）切片 A：项目列表与路线读取

- [x] `P1-04` 实现 `list_projects`
  - 目标文件：`learning_ext/application/projects.py`。
  - 现有位置：`path_generator.py:_refresh_projects:669`、`study_workbench.py:_refresh_projects:841`。
  - 前置依赖：`P1-02`、`P1-03`。
  - 实施内容：集中项目查询、排序和项目摘要转换；保持本地单用户现状，不在此任务引入账号系统。
  - 完成标准：两个 Page 可使用同一项目结果；空数据库返回空列表。
  - 验证方式：application 单元测试覆盖多个项目排序和空列表。
  - 实际修改：集中按 `user_id` 查询、ID 倒序和进度摘要转换；空列表返回 `[]`。
  - 自动验证：排序、空列表和用户边界测试通过。
  - 手工验证：两个 Page 已改为调用同一用例。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P1-05` 实现 `get_project_roadmap`
  - 目标文件：`learning_ext/application/roadmap.py`。
  - 复用位置：`learning_ext/path_generator/service.py:load_roadmap:357`。
  - 前置依赖：`P1-02`、`P1-03`。
  - 实施内容：调用现有路线 service，补充 Page 和 API 所需的稳定结果转换；不返回 Gradio Markdown。
  - 完成标准：正常项目返回路线和节点；不存在项目保留明确错误语义。
  - 验证方式：application 单元测试覆盖正常和不存在项目。
  - 实际修改：调用 `load_roadmap` 并补齐节点持久化 ID，返回客户端无关 `ProjectRoadmap`。
  - 自动验证：正常/不存在项目测试通过。
  - 手工验证：路线 Page 方法回归通过。
  - 遗留问题：无。
  - 完成日期：2026-08-26。

- [x] `P1-06` 让 `PathGeneratorPage` 使用切片 A
  - 目标文件：`learning_ext/pages/path_generator.py`。
  - 目标符号：`_refresh_projects:669`、`_handle_load:445`。
  - 前置依赖：`P1-04`、`P1-05`。
  - 实施内容：Page 调用 application，并在 Page 内完成 Dropdown/Markdown/状态文本转换。
  - 完成标准：Page 不再自行实现已迁移的项目查询和路线读取编排；页面输出保持一致。
  - 验证方式：相关 Page 测试和 P0 手工回归。
  - 实际修改：`_refresh_projects` 调用 `list_projects`，`_handle_load` 调用 `get_project_roadmap`；Markdown、JSON 和状态文本转换保留在 Page。
  - 自动验证：`tests/test_pages.py` 36 项通过，退出码 0。
  - 手工验证：隔离 Gradio 路线页已显示项目列表并成功加载项目 #1 路线，见 `P0-12`。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P1-07` 完成切片 A 回归
  - 目标范围：`list_projects`、`get_project_roadmap`、`PathGeneratorPage`。
  - 前置依赖：`P1-06`。
  - 实施内容：运行 application 测试、Page 测试和路线页手工验证。
  - 完成标准：自动测试通过；项目列表、项目加载和路线展示与基线一致。
  - 验证方式：记录命令、退出码和手工观察。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_application_projects.py` 为 9 passed、退出码 0；`tests/test_pages.py` 为 36 passed、退出码 0。
  - 手工验证：隔离项目列表、项目 #1 路线加载、节点 Markdown 展示均与 application 返回一致。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （三）切片 B：工作台读取与节点状态

- [x] `P1-08` 实现 `get_project_workspace`
  - 目标文件：`learning_ext/application/projects.py`。
  - 现有位置：`study_workbench.py:_auto_init:733`、`_build_nodes_data:644`、`_on_project_change:853`。
  - 复用位置：`get_project_progress:129`、`get_practice_task:290`、`get_note:28`、`get_resources:67`。
  - 前置依赖：`P1-04`、`P1-07`。
  - 实施内容：聚合项目与工作台现有数据；读取用例不触发 LLM 生成、资料抓取或后台线程。
  - 完成标准：返回结果覆盖项目切换所需数据；无项目、无节点和不存在项目行为明确。
  - 验证方式：application 单元测试覆盖三类场景。
  - 实际修改：聚合项目、进度、环境、节点、实操、笔记和资料摘要；读取路径不调用生成/抓取函数。
  - 自动验证：聚合和不存在项目测试通过；`compileall` 通过。
  - 手工验证：隔离工作台已加载项目、环境、节点、实操/笔记/资料摘要，并未触发 LLM 或网络抓取。
  - 遗留问题：application 读取无副作用，但 Gradio `_auto_init` 在调用后仍会预加载课程并启动资料后台抓取，需后续切片拆分。
  - 完成日期：2026-08-27。

- [x] `P1-09` 实现 `update_node_status`
  - 目标文件：`learning_ext/application/projects.py` 或 `study.py`；以当时模块职责选择，避免仅为一个函数建立空模块。
  - 复用位置：`learning_ext/progress/study.py:set_node_status:72`、`get_project_progress:129`。
  - 前置依赖：`P1-03`、`P1-07`。
  - 实施内容：调用现有 service 更新状态，并返回 Page 刷新所需的节点和项目进度结果。
  - 完成标准：状态写入和刷新结果来自同一 application 用例；非法状态行为保持一致。
  - 验证方式：合法状态、非法状态和不存在节点测试。
  - 实际修改：统一调用 `set_node_status` 并返回更新节点和完整工作台；增加项目归属检查。
  - 自动验证：合法、非法和不存在节点测试通过。
  - 手工验证：隔离工作台点击“学习中”后状态、节点下拉标签和项目进度同时刷新。
  - 遗留问题：掌握后的后台内容生成仍由 Page 保留，后续长任务切片再处理。
  - 完成日期：2026-08-27。

- [x] `P1-10` 让 `StudyWorkbenchPage` 使用切片 B
  - 目标文件：`learning_ext/pages/study_workbench.py`。
  - 目标符号：`_auto_init:733`、`_refresh_projects:841`、`_on_project_change:853`、`_set_status:1347`。
  - 前置依赖：`P1-08`、`P1-09`。
  - 实施内容：Page 调用 application；保留 Dropdown、Markdown、`gr.update()` 和页面状态转换。
  - 完成标准：已迁移用例的查询和组合逻辑不再重复留在 Page；页面行为不变。
  - 验证方式：Page 测试和 P0 工作台手工回归。
  - 实际修改：`_auto_init`、`_refresh_projects`、`_on_project_change` 和 `_set_status` 改为调用 application；Gradio 控件适配保留在 Page。
  - 自动验证：`tests/test_pages.py` 36 项通过，退出码 0。
  - 手工验证：隔离工作台完成项目切换后的节点显示与状态更新，见 `P0-12`。
  - 遗留问题：工作台预加载课程/资料副作用仍待后续迁移。
  - 完成日期：2026-08-27。

- [x] `P1-11` 完成切片 B 回归
  - 目标范围：工作台加载、项目切换、节点列表和节点状态更新。
  - 前置依赖：`P1-10`。
  - 实施内容：运行 application、Page 和相关进度测试；执行手工回归。
  - 完成标准：工作台展示与基线一致；节点状态写入后旧页面正确刷新。
  - 验证方式：记录测试命令、退出码和手工结果。
  - 自动验证：`tests/test_application_projects.py` 9 项通过，`tests/test_pages.py` 36 项通过，均退出码 0；`compileall` 通过。
  - 手工验证：隔离工作台显示项目进度、课程列表和节点正文，状态由 pending 更新为 learning 后所有页面状态一致。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （四）Application 边界检查

- [x] `P1-12` 检查 application 依赖方向
  - 目标范围：`learning_ext/application/`。
  - 前置依赖：`P1-11`。
  - 实施内容：确认没有导入 Gradio、Page、FastAPI Router 或前端类型。
  - 完成标准：application 只依赖领域 service、数据模型和必要基础设施。
  - 验证方式：`rg` 依赖扫描和测试导入。
  - 实际修改：无额外改动；确认 application 只依赖 service、模型和基础设施。
  - 自动验证：依赖扫描无 `gradio`、Page、FastAPI Router 或 frontend 命中；import smoke test 通过。
  - 手工验证：代码审阅通过。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P1-13` 检查首批业务逻辑没有复制
  - 目标范围：首批 application 和两个 Page。
  - 前置依赖：`P1-11`。
  - 实施内容：确认项目查询、路线读取、工作台聚合和节点更新没有两套独立实现。
  - 完成标准：Page 只包含 UI 转换；application 是共享业务入口。
  - 验证方式：代码审阅和符号搜索。
  - 实际修改：Page 的项目查询、路线读取、工作台聚合和状态写入已替换为 application 调用；只保留 UI 格式转换及未迁移的生成副作用。
  - 自动验证：`rg` 检查两个 Page 的 application 调用和旧 service 入口；测试通过。
  - 手工验证：代码审阅和隔离 Gradio 对照通过。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （五）P1 完成标准

- [x] `P1-GATE` 完成 P1 阶段门禁
  - 前置依赖：`P1-01` 至 `P1-13`。
  - 完成标准：首批四个 application 用例独立可测；Gradio 已调用 application；新旧行为对齐；未创建重复业务逻辑。
  - 验证方式：完整记录 application 测试、Page 测试和手工回归结果。
  - 实际修改：首批 application、两个 Page 适配和定向测试已完成。
  - 自动验证：application 9 项、Page 36 项测试均退出码 0；依赖扫描和 `compileall` 通过。
  - 手工验证：隔离 Gradio 回归完成项目列表、路线读取、工作台读取和节点状态更新。
  - 遗留问题：工作台读取路径仍保留旧的课程预加载/资料后台抓取，已明确留给 P3/P4 长任务切片，不阻断本次只读/状态接缝。
  - 完成日期：2026-08-27。

## 五、P2：第一条 API 与 Next.js 切片

### （一）FastAPI 最小入口

- [x] `P2-01` 创建 `api/` 包结构
  - 目标文件：`api/__init__.py`、`api/main.py`、`api/routers/`、`api/schemas/`。
  - 前置依赖：`P1-GATE`。
  - 实施内容：建立最小 FastAPI 服务和版本化路由；只创建当前切片需要的模块。
  - 完成标准：API 应用可以独立导入和启动；未提前创建空功能目录。
  - 验证方式：API import smoke test 和本地启动测试。
  - 实际修改：新增 `api/main.py`、`api/dependencies.py`、`api/routers/` 和 `api/schemas/`；入口以生命周期调用既有 `learning_ext.bootstrap.init_learning_ext`，未创建超出本切片的功能模块。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m compileall -q api tests/test_api.py` 退出码 0；`tests/test_api.py` 通过。
  - 手工验证：使用隔离 SQLite 配置启动 `python -m uvicorn api.main:app --host 127.0.0.1 --port 8001`，启动完成；`/openapi.json` 返回 200；测试进程已停止。
  - 遗留问题：开发期浏览器跨域和 API/桌面进程编排留待 P6 统一处理。
  - 完成日期：2026-08-27。

- [x] `P2-02` 定义首批 API Schema
  - 目标文件：`api/schemas/projects.py`、`nodes.py`。
  - 前置依赖：`P2-01`、`P1-03`。
  - 实施内容：定义项目摘要、路线详情、工作台数据和状态更新请求/响应；不直接把 SQLModel 表实体作为 HTTP 契约。
  - 完成标准：Schema 字段来自已确认 application 结果，字段命名稳定。
  - 验证方式：Schema 构造和序列化测试。
  - 实际修改：在 `api/schemas/projects.py`、`api/schemas/nodes.py` 定义项目摘要、路线、工作台、节点状态请求与响应 Pydantic Schema；未暴露 SQLModel 实体。
  - 自动验证：`tests/test_api.py` 的四个读取/写入响应序列化测试通过，退出码 0。
  - 手工验证：通过隔离实例的 `/openapi.json` 确认四个版本化路径已注册。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-03` 建立首批错误响应转换
  - 目标文件：`api/main.py` 或最小错误模块。
  - 前置依赖：`P2-01`。
  - 实施内容：将参数错误、资源不存在和非法状态转换为前端可识别的响应；不把堆栈和内部敏感信息返回前端。
  - 完成标准：首批接口错误行为一致，不在每个 Router 重复 `try/except` 文案。
  - 验证方式：API 契约测试覆盖 400、404、422 等当前实际场景。
  - 实际修改：`api/main.py` 集中将 application 的项目/节点不存在映射为 404，将业务非法状态映射为 400；FastAPI 请求 Schema 校验保留 422。
  - 自动验证：`tests/test_api.py::test_project_reads_return_not_found` 与 `test_patch_node_status_maps_invalid_and_unknown_errors` 覆盖 400、404、422，均通过。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （二）首批 API 路由

- [x] `P2-04` 实现 `GET /api/v1/projects`
  - 目标文件：`api/routers/projects.py`。
  - 前置依赖：`P2-02`、`P1-04`。
  - 实施内容：调用 `list_projects` application 用例并转换为响应 Schema。
  - 完成标准：空列表和多项目排序与 application 一致。
  - 验证方式：FastAPI 契约测试。
  - 实际修改：`api/routers/projects.py` 调用 `list_projects` 并转换结构化摘要响应。
  - 自动验证：`tests/test_api.py::test_list_projects_returns_application_order` 通过；隔离 Uvicorn 的 `/api/v1/projects` 返回 200 和回归项目。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-05` 实现 `GET /api/v1/projects/{project_id}/roadmap`
  - 目标文件：`api/routers/projects.py`。
  - 前置依赖：`P2-02`、`P1-05`。
  - 实施内容：调用 `get_project_roadmap`，返回路线和节点数据。
  - 完成标准：正常项目返回 200，不存在项目返回稳定 404。
  - 验证方式：FastAPI 契约测试。
  - 实际修改：`api/routers/projects.py` 调用 `get_project_roadmap`，由统一错误处理映射不存在项目。
  - 自动验证：`tests/test_api.py::test_get_project_roadmap_returns_node_ids` 与不存在项目断言通过。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-06` 实现 `GET /api/v1/projects/{project_id}/workspace`
  - 目标文件：`api/routers/projects.py`。
  - 前置依赖：`P2-02`、`P1-08`。
  - 实施内容：调用只读的 `get_project_workspace`；不得隐式触发 LLM 或后台资料生成。
  - 完成标准：返回工作台当前数据；无节点和不存在项目行为明确。
  - 验证方式：FastAPI 契约测试并检查无生成函数调用。
  - 实际修改：`api/routers/projects.py` 仅调用 `get_project_workspace`，返回既有数据快照。
  - 自动验证：`tests/test_api.py::test_workspace_read_returns_existing_data_without_generation` 与不存在项目断言通过；对 Router 和 application 的 `generate_`、`ensure_`、线程、聊天调用静态扫描无匹配。
  - 手工验证：无。
  - 遗留问题：空节点项目的前端呈现留待 `P2-13` 覆盖。
  - 完成日期：2026-08-27。

- [x] `P2-07` 实现 `PATCH /api/v1/nodes/{node_id}/status`
  - 目标文件：`api/routers/nodes.py`。
  - 前置依赖：`P2-02`、`P1-09`。
  - 实施内容：校验状态请求，调用 `update_node_status`。
  - 完成标准：合法状态更新成功；非法状态和不存在节点返回稳定错误。
  - 验证方式：FastAPI 契约测试和数据库断言。
  - 实际修改：`api/routers/nodes.py` 校验状态请求并调用 `update_node_status`，响应包含更新节点和刷新后的工作台快照。
  - 自动验证：`tests/test_api.py::test_patch_node_status_persists_and_returns_workspace` 通过并断言数据库已写入；非法和不存在节点断言通过。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-08` 完成首批 API 契约回归
  - 目标范围：P2 四个接口。
  - 前置依赖：`P2-04` 至 `P2-07`。
  - 实施内容：运行全部 API 契约测试，并与 application 结果对比。
  - 完成标准：Router 只做 HTTP 适配，没有复制 Page 编排。
  - 验证方式：测试结果和 Router 代码审阅。
  - 实际修改：新增 `tests/test_api.py`，覆盖项目排序、路线节点、工作台读取、节点状态持久化和 400/404/422 错误。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_application_projects.py tests/test_api.py` 为 `15 passed in 1.48s`，退出码 0；Router 的 Page/service 导入扫描无匹配；`git diff --check` 通过。
  - 手工验证：隔离 Uvicorn 启动、OpenAPI 与项目读取均通过，未触碰用户 SQLite。
  - 遗留问题：Next.js 客户端尚未创建，P2 尚未完成。
  - 完成日期：2026-08-27。

### （三）Next.js 基础工程

- [x] `P2-09` 创建 `frontend/` 工程
  - 目标位置：`frontend/`。
  - 前置依赖：`P2-08`。
  - 实施内容：创建 Next.js + TypeScript 工程，采用项目确认的包管理和代码规范；不先制作营销首页。
  - 完成标准：开发服务器可以启动并显示实际应用外壳。
  - 验证方式：构建、类型检查和浏览器打开验证。
  - 实际修改：新增 Next.js 16 + TypeScript 工程、锁文件和同源 FastAPI 代理配置。
  - 自动验证：`npm run typecheck`、`npm run build` 均退出码 0。
  - 手工验证：隔离环境的 Next 服务启动于 `http://localhost:3000`。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-10` 建立前端路由和应用外壳
  - 目标位置：`frontend/app/`。
  - 前置依赖：`P2-09`。
  - 实施内容：建立项目列表和工作台导航；页面结构面向学习工具，不复刻 Gradio 的框架限制。
  - 完成标准：桌面和移动视口下导航可用，无页面内容重叠。
  - 验证方式：浏览器和响应式截图检查。
  - 实际修改：实现单页学习工作台的项目侧栏、进度区和节点区域。
  - 自动验证：生产构建通过。
  - 手工验证：Chrome DevTools 截图检查桌面和 390px 移动视口，未见应用元素重叠。
  - 遗留问题：Next 开发工具按钮仅在开发截图中出现，生产构建不包含该工具。
  - 完成日期：2026-08-27。

- [x] `P2-11` 建立前端 API client
  - 目标位置：`frontend/lib/`。
  - 前置依赖：`P2-09`、`P2-08`。
  - 实施内容：统一封装基础 URL、JSON 解析和错误对象；不要为 SQLite 创建所谓前端数据库 client。
  - 完成标准：页面不重复拼接 API 地址和解析错误。
  - 验证方式：client 单元测试或集成测试。
  - 实际修改：`frontend/lib/api.ts` 统一封装 JSON、错误和四项 API 调用；`next.config.ts` 统一代理基础地址。
  - 自动验证：`/backend-api/projects`、路线和工作台代理请求均返回隔离 FastAPI 的真实数据。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-12` 实现项目列表页面
  - 目标位置：`frontend/app/` 和 `frontend/features/projects/`。
  - 前置依赖：`P2-10`、`P2-11`、`P2-04`。
  - 实施内容：读取真实项目列表，展示加载、空数据和失败状态；支持进入项目工作台。
  - 完成标准：页面使用真实 API，不使用硬编码业务数据。
  - 验证方式：浏览器操作和前端测试。
  - 实际修改：实现真实项目列表、加载、空数据、错误和重试状态。
  - 自动验证：Chrome DevTools 等待 DOM 后确认隔离项目显示。
  - 手工验证：隔离项目选择后加载对应工作台。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-13` 实现路线与工作台基础页面
  - 目标位置：`frontend/features/workspace/`。
  - 前置依赖：`P2-12`、`P2-05`、`P2-06`。
  - 实施内容：展示路线节点、阶段、进度和当前节点基础信息；参考 Gradio 功能但使用完整前端交互。
  - 完成标准：切换项目和节点不会触发布局错乱；空节点项目可正常展示。
  - 验证方式：桌面/移动浏览器验证和组件测试。
  - 实际修改：展示路线阶段、节点、进度、环境与资料数量，课程正文只显示摘要。
  - 补充修改（2026-08-28）：节点详情加载完成后自动滚动到详情面板，避免详情面板位于长节点列表末尾而看起来无响应。
  - 自动验证：类型检查与生产构建通过。
  - 手工验证：桌面和移动 DevTools DOM 均确认节点和进度存在；浏览器点击首个 Rust 节点后，详情面板自动定位并显示课程内容。
  - 遗留问题：完整课程阅读留待 P4。
  - 完成日期：2026-08-27。

- [x] `P2-14` 实现节点状态更新交互
  - 目标位置：`frontend/features/workspace/`。
  - 前置依赖：`P2-13`、`P2-07`。
  - 实施内容：调用状态更新接口，处理提交中、成功、失败和回滚显示。
  - 完成标准：状态持久化到现有数据库；刷新页面后结果保持。
  - 验证方式：端到端测试和数据库结果确认。
  - 实际修改：实现提交中禁用、乐观更新、失败回滚及成功后项目摘要刷新。
  - 自动验证：Chrome DevTools 点击“已掌握”后 DOM 变为 `100% 已完成`；隔离 FastAPI 工作台返回节点 `mastered`、项目 `1/1`。
  - 手工验证：桌面截图确认更新后的状态和进度同步显示。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （四）第一条端到端闭环

- [x] `P2-15` 对比 Gradio 与 Next.js 项目数据
  - 前置依赖：`P2-14`。
  - 实施内容：在同一数据库上对比项目顺序、路线节点、状态和进度。
  - 完成标准：关键业务数据一致；仅允许 UI 呈现方式不同。
  - 验证方式：手工对照和接口响应记录。
  - 实际修改：无。
  - 自动验证：隔离 SQLite 上的 Chrome DOM 对照确认：Next 显示 `手工回归项目`、`测试节点`、`已掌握` 与 `1/1`；Gradio 路线页显示同一项目，工作台显示同一节点、`已掌握` 与 `1/1`；FastAPI 工作台响应节点状态为 `mastered`、进度为 `1/1`。
  - 手工验证：三端仅在项目标题放置位置和摘要样式上不同，不存在业务数据差异。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P2-16` 完成第一条切片自动验证
  - 前置依赖：`P2-15`。
  - 实施内容：运行 application、Page、API、前端类型检查和关键端到端测试。
  - 完成标准：所有命令结果和退出码已记录；没有遗留运行会话。
  - 验证方式：执行记录。
  - 实际修改：无；新增的 `.tmp/pytest_exit_probe.py` 仅为忽略目录内的诊断脚本，不参与产品运行。
  - 自动验证：`tests/test_application_projects.py tests/test_api.py` 为 `15 passed in 1.63s`、退出码 0；`tests/test_pages.py` 为 `36 passed, 1 warning in 28.89s`、退出码 0；`npm run typecheck`、`npm run build` 均退出码 0；隔离端到端同库对照通过。
  - 手工验证：Next 与 Gradio 通过隔离库完成项目读取、路线/工作台显示及状态更新回读。
  - 遗留问题：Mistral tokenizer 离线回退产生 1 条既有警告，不影响 Fake LLM 回归；测试 session 结束时存在 LanceDB 与资源抓取 daemon 线程，但无子进程，pytest 自然退出。
  - 完成日期：2026-08-27。

### （五）P2 完成标准

- [x] `P2-GATE` 完成 P2 阶段门禁
  - 前置依赖：`P2-01` 至 `P2-16`。
  - 完成标准：Next.js 使用真实 API 完成项目读取、路线展示、工作台读取和节点状态更新；Gradio 仍可用；FastAPI 只调用 application。
  - 验证方式：自动测试与新旧客户端手工对照。
  - 自动测试结果：application/API `15 passed`、Page `36 passed`、前端类型检查和生产构建均退出码 0；边界扫描确认 application 无 Gradio/HTTP 导入、Router 无 Page/service 导入。
  - 手工验证结果：隔离 SQLite 上，Next 与 Gradio 均可用，并与 FastAPI 对照同一项目、节点状态和进度；Next 节点状态写回后刷新仍保持。
  - 修改文件范围：`learning_ext/application/`、两个 Gradio Page、`api/`、`frontend/`、测试和迁移 TODO；未修改 `kotaemon/`、启动器或用户数据。
  - Gradio 可用性：保留且已在隔离配置启动和验证。
  - 行为差异：Next 将完整 Markdown 课程正文摘要化展示；完整学习内容阅读留给 P4，未改变存储或 Gradio 行为。
  - 遗留风险：开发与桌面进程编排尚未迁移，留待 P6；P3 的路线生成仍是 Gradio Page 编排，下一阶段迁移。
  - 下一阶段：可开始 P3。
  - 完成日期：2026-08-27。

## 六、P3：路线创建流程

### （一）路线预览与调整

- [x] `P3-01` 定义路线创建用例契约
  - 现有位置：`path_generator.py:_handle_generate:269`、`_handle_refine:299`、`_handle_save_with_setup:316`。
  - 前置依赖：`P2-GATE`。
  - 实施内容：区分路线预览、路线调整、项目保存和项目内容准备四类结果。
  - 完成标准：失败边界和长任务边界明确，不把 Page Markdown 当业务结果。
  - 验证方式：契约审阅和现有行为对照。
  - 实际修改：在 `learning_ext/application/roadmap.py` 定义 `RoadmapPreview`、`ProjectCreation` 及预览、调整、保存三类用例边界。
  - 自动验证：application 测试覆盖正常与失败边界，退出码 0。
  - 手工验证：现有 Page 的 Markdown 格式化仍保留在 Page。
  - 遗留问题：内容准备的后台可观察状态由 `P3-05` 单独实现。
  - 完成日期：2026-08-27。

- [x] `P3-02` 实现 `generate_roadmap_preview`
  - 目标文件：`learning_ext/application/roadmap.py`。
  - 复用位置：`generate_roadmap:36`、`audit_and_rewrite_roadmap:72`。
  - 前置依赖：`P3-01`。
  - 实施内容：组合路线生成和自动审计，返回结构化路线和审计信息。
  - 完成标准：不依赖 Gradio；两步中任一步失败都有明确错误。
  - 验证方式：Fake LLM application 测试。
  - 实际修改：组合 `generate_roadmap` 与 `audit_and_rewrite_roadmap`，返回结构化路线和审计结果，不写库。
  - 自动验证：Fake LLM 测试断言审计结果且数据库项目列表保持为空，退出码 0。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P3-03` 实现 `refine_roadmap`
  - 目标文件：`learning_ext/application/roadmap.py`。
  - 复用位置：`path_generator/service.py:refine_roadmap:58`。
  - 前置依赖：`P3-01`。
  - 实施内容：根据用户指令调整路线，保留结构校验。
  - 完成标准：输入和输出结构稳定；无效路线不会进入保存流程。
  - 验证方式：Fake LLM 和无效 JSON 测试。
  - 实际修改：新增 `refine_roadmap_preview`，在调用 service 前校验路线节点和调整意见。
  - 自动验证：Fake service、空路线与空调整意见测试通过，退出码 0。
  - 手工验证：无。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

### （二）项目保存与内容准备

- [x] `P3-04` 实现 `create_project`
  - 目标文件：`learning_ext/application/roadmap.py`。
  - 复用位置：`save_roadmap:172`、`generate_env_checklist:439`、`save_env_tasks:487`。
  - 前置依赖：`P3-01`。
  - 实施内容：保存项目、节点和环境任务；明确哪些失败阻止项目创建，哪些失败作为可重试后续步骤。
  - 完成标准：Page 和 API 不再自行组合这些 service。
  - 验证方式：临时数据库 application 测试。
  - 实际修改：新增 `create_project`，将路线持久化视为阻断步骤；环境清单失败作为可重试结果返回，不回滚已创建项目。
  - 自动验证：临时 SQLite 覆盖环境任务成功和失败后项目仍可读取，退出码 0。
  - 手工验证：无。
  - 遗留问题：Page/API 接入留待 `P3-07`、`P3-09`。
  - 完成日期：2026-08-27。

- [x] `P3-05` 实现 `prepare_project_content`
  - 目标文件：`learning_ext/application/roadmap.py` 或 `jobs.py`。
  - 复用位置：`generate_node_summary_to_db:533`、`generate_summaries_background:595`。
  - 前置依赖：`P3-04`。
  - 实施内容：定义首批同步生成与剩余后台生成边界；提供可观察结果，不继续只依赖匿名 daemon thread。
  - 完成标准：调用方可以知道项目已保存、哪些节点已生成、哪些仍在处理和哪些失败。
  - 验证方式：Fake 内容生成器和任务状态测试。
  - 实际修改：新增 `learning_ext/application/jobs.py`，以现有 `Task(task_type=content_preparation)` 保存作业状态；首批节点同步生成，剩余节点由具名 daemon 继续并持续写入生成、失败和待处理节点 ID。
  - 自动验证：`tests/test_application_projects.py` 为 `15 passed in 1.14s`、退出码 0；覆盖同步成功/失败与后台 `doing -> done` 状态转换。
  - 手工验证：无。
  - 遗留问题：当前作业执行器仍是本地单进程后台线程；进程退出后任务保持可查询但不会自动恢复，P6 运行时编排前需决定恢复策略。
  - 完成日期：2026-08-27。

- [x] `P3-06` 实现 `replace_project_roadmap`
  - 目标文件：`learning_ext/application/roadmap.py`。
  - 现有位置：`path_generator.py:_handle_audit_project:522`。
  - 复用位置：`path_generator/service.py:replace_project_roadmap:300`、`regenerate_all_content:668`。
  - 前置依赖：`P3-04`、`P3-05`。
  - 实施内容：提取路线审计、替换和重新生成流程；保留破坏性操作的明确确认边界。
  - 完成标准：替换行为可以独立测试；失败不会被 Page 静默吞掉。
  - 验证方式：临时数据库替换测试和回归测试。
  - 实际修改：新增 application `replace_project_roadmap(..., confirmed=True)`，未确认时在删除前拒绝；确认后复用现有替换 service 并创建内容准备作业。
  - 自动验证：`tests/test_application_projects.py` 为 `16 passed in 1.37s`、退出码 0；断言未确认不变更数据，确认后节点替换且内容作业为可观察状态。
  - 手工验证：未对用户项目执行替换。
  - 遗留问题：Gradio 旧审计入口暂未提供确认输入，`P3-07` 接入 application 时补齐该 UI 边界。
  - 完成日期：2026-08-27。

### （三）Gradio、API 与 Next.js 接入

- [x] `P3-07` 让 `PathGeneratorPage` 使用路线创建 application
  - 目标文件：`learning_ext/pages/path_generator.py`。
  - 前置依赖：`P3-02` 至 `P3-06`。
  - 实施内容：替换 `_handle_generate`、`_handle_refine`、`_handle_save_with_setup` 和 `_handle_audit_project` 中已提取的编排。
  - 完成标准：Gradio 输出和交互保持现有行为；Page 只做 UI 适配。
  - 验证方式：Page 自动测试和完整路线手工回归。
  - 实际修改：生成、调整、保存和内容准备改调用 application；审计替换改用带 `REPLACE` 确认的 application 用例；Page 保留 Markdown、Gradio 组件和流式状态适配。
  - 自动验证：`tests/test_pages.py tests/test_path_generator_batch_audit.py` 为 `37 passed, 1 warning in 27.42s`、退出码 0。
  - 手工验证：未对用户项目执行审计替换；未确认路径会直接返回提示。
  - 遗留问题：离线 Mistral tokenizer 产生既有回退警告。
  - 完成日期：2026-08-27。

- [x] `P3-08` 增加路线预览和调整 API
  - 目标文件：`api/routers/roadmaps.py`、对应 Schema。
  - 前置依赖：`P3-02`、`P3-03`、`P3-07`。
  - 实施内容：增加路线预览和调整端点，返回结构化结果。
  - 完成标准：Router 不复制 LLM 调用顺序。
  - 验证方式：Fake LLM API 契约测试。
  - 实际修改：新增 `POST /api/v1/roadmaps/preview` 和 `POST /api/v1/roadmaps/refine`，Router 仅调用 `generate_roadmap_preview`、`refine_roadmap_preview`；新增请求长度、每周小时数和结构化返回 Schema。
  - 自动验证：`tests/test_api.py` 为 `10 passed`、退出码 0；覆盖预览、调整、无效输入与空路线错误响应。
  - 手工验证：无；端点不写入项目或节点数据。
  - 遗留问题：真实模型、超时和取消策略待 P6 统一运行时编排时验证。
  - 完成日期：2026-08-27。

- [x] `P3-09` 增加项目创建和内容准备 API
  - 目标文件：`api/routers/projects.py`、对应 Schema。
  - 前置依赖：`P3-04`、`P3-05`、`P3-07`。
  - 实施内容：项目保存与内容准备分别提供明确结果；长任务返回状态标识。
  - 完成标准：前端能区分项目保存成功和后续内容准备状态。
  - 验证方式：API 契约与任务状态测试。
  - 实际修改：新增 `POST /api/v1/projects`、`POST /api/v1/projects/{project_id}/content-preparation` 和内容准备状态查询；创建与内容准备分别返回项目、环境和作业状态。
  - 自动验证：`tests/test_api.py` 为 `12 passed in 1.86s`、退出码 0；覆盖 `201` 创建、`202` 内容准备启动、状态查询与未知项目的 `404`。
  - 手工验证：无；测试使用临时 SQLite 和 Fake LLM。
  - 遗留问题：作业执行仍依赖本地进程；进程重启恢复策略留至 P6。
  - 完成日期：2026-08-27。

- [x] `P3-10` 实现 Next.js 路线创建页面
  - 目标位置：`frontend/features/roadmap/`。
  - 前置依赖：`P3-08`、`P3-09`。
  - 实施内容：主题输入、路线预览、调整、确认保存和处理状态展示。
  - 完成标准：真实 API 完成创建；无效输入、生成失败和保存失败可理解。
  - 验证方式：组件测试和端到端测试。
  - 实际修改：新增 `frontend/features/roadmap/RoadmapCreation.tsx` 与 API client 调用；工作台侧栏可进入路线创建，支持预览、自然语言调整、确认保存、内容作业轮询、失败提示和进入新项目。
  - 自动验证：`npm run typecheck`、`npm run build` 均退出码 0；隔离 FastAPI + Fake LLM 的 Chrome DevTools 关键流程返回 `preview=true`、`finished=true`、`created=true`。
  - 手工验证：headless Chrome 在 `localhost` 隔离 Next 服务中填入选题，执行生成、调整、保存和内容准备；未写入用户 SQLite。
  - 遗留问题：本地内容作业重启恢复仍待 P6；开发服务器以 `127.0.0.1` 访问会被 Next 16 的开发源保护阻止，正式浏览器入口和隔离验证使用 `localhost`。
  - 完成日期：2026-08-27。

- [x] `P3-11` 完成路线创建新旧客户端对照
  - 前置依赖：`P3-10`。
  - 实施内容：在相同输入下对比 Gradio 和 Next.js 的路线结构、保存结果和内容准备行为。
  - 完成标准：核心业务结果一致；差异仅限 UI 表达。
  - 验证方式：手工对照记录和数据库检查。
  - 实际修改：无新增业务代码；补充 Page 回归断言，确认 Gradio 生成预览后保存的节点代码与 application 持久化结果一致。
  - 自动验证：`tests/test_pages.py::TestSaveWithSetup tests/test_application_projects.py tests/test_api.py` 为 `33 passed in 16.66s`、退出码 0；隔离浏览器 API 链路另验证了同一 application 路线创建与内容作业。
  - 手工验证：隔离数据库中 Next 创建流程显示路线预览、完成内容作业和“查看新项目”；Gradio 回归仍通过同一 application 保存路线。客户端差异仅为 Markdown/Gradio 与交互式 Next 展示。
  - 遗留问题：未使用真实模型或用户项目做破坏性路线替换。
  - 完成日期：2026-08-27。

### （四）P3 完成标准

- [x] `P3-GATE` 完成 P3 阶段门禁
  - 前置依赖：`P3-01` 至 `P3-11`。
  - 完成标准：路线生成、审计、调整、保存和内容准备共用 application；Next.js 可以创建真实项目；Gradio 回归通过。
  - 验证方式：application、Page、API 和前端端到端测试。
  - 修改文件范围：`learning_ext/application/roadmap.py`、`jobs.py`、`PathGeneratorPage`、`api/routers/roadmaps.py`、项目 Router/Schema、路线创建前端、应用/API/Page 测试和本 TODO。
  - 自动测试结果：`tests/test_application_projects.py tests/test_api.py tests/test_pages.py tests/test_path_generator_batch_audit.py` 为 `66 passed, 1 warning in 31.86s`、退出码 0；`compileall`、`npm run typecheck` 和 `npm run build` 均退出码 0；application/Router 依赖方向扫描无违规命中。
  - 手工验证结果：隔离 SQLite、Fake LLM 和 Chrome DevTools 完成 Next 路线预览、调整、保存及内容作业；Gradio 保存/审计 Page 回归通过。所有临时 API、Next 和 Chrome 进程均已停止。
  - Gradio 可用：是，`PathGeneratorPage` 仍保留并已改为调用相同 application；未删除或替换 Gradio 启动链。
  - 行为差异：客户端只在 UI 表达上不同；API 将项目保存与内容准备拆为两个明确请求，Gradio 保留原有流式进度文本。
  - 遗留风险：内容准备仍依赖本地后台线程，进程重启恢复、真实模型的超时/取消与桌面进程编排留待 P6；离线 Mistral tokenizer 回退警告不影响 Fake LLM 测试。
  - 下一阶段：可以开始 P4-01，先分离节点读取与生成副作用。
  - 完成日期：2026-08-27。

## 七、P4：学习核心功能

### （一）节点详情与课程内容

- [x] `P4-01` 定义节点读取与生成的独立契约
  - 现有位置：`study_workbench.py:_on_node_select:952`、`_ensure_course_content:1005`、`_ensure_resources_background:1079`。
  - 前置依赖：`P3-GATE`。
  - 实施内容：把读取现有数据、生成课程、生成实操、生成资料拆成独立用例。
  - 完成标准：读取操作不隐式调用 LLM 或网络抓取。
  - 验证方式：契约审阅和调用扫描。
  - 实际修改：确定 `get_node_detail` 仅聚合节点、项目、课程正文、实操任务、笔记和已保存资料；`generate_node_content`、`generate_practice_lesson`、`generate_node_resources` 是三个显式写入用例。读取结果不包含 Gradio 组件或生成状态猜测。
  - 自动验证：调用扫描确认历史 `_on_node_select` 同时调用 `_ensure_course_content` 与 `_ensure_resources_background`；P4 新读取用例将不调用这些函数或任何 LLM/HTTP 生成器。
  - 手工验证：无；本任务只固化边界，未改变当前 Gradio 行为。
  - 遗留问题：Gradio 旧读取入口仍有隐式生成，待 `P4-07` 用同一 application 进行替换后消除。
  - 完成日期：2026-08-27。

- [x] `P4-02` 实现 `get_node_detail`
  - 目标文件：`learning_ext/application/study.py`。
  - 复用位置：节点/项目查询、`get_practice_task`、`get_note`、`get_resources`。
  - 前置依赖：`P4-01`。
  - 实施内容：聚合节点当前数据，不进行生成。
  - 完成标准：不存在节点、无课程、无笔记和无资料均有明确结果。
  - 验证方式：application 测试。
  - 实际修改：新增 `learning_ext/application/study.py` 的 `NodeDetail` 和 `get_node_detail`，复用已存在的节点、实操、笔记和资料查询转换；不调用任何生成 service。
  - 自动验证：`tests/test_application_projects.py` 为 `17 passed in 1.34s`、退出码 0；覆盖已有节点、项目归属和空资料的纯读取结果。
  - 手工验证：无；P4-07 接入客户端时统一验证。
  - 遗留问题：Gradio 的旧节点选择仍会在读取后触发生成，待 P4-07 替换。
  - 完成日期：2026-08-27。

- [x] `P4-03` 实现 `generate_node_content`
  - 目标文件：`learning_ext/application/study.py`。
  - 复用位置：`generate_node_summary_to_db:533`。
  - 前置依赖：`P4-01`。
  - 实施内容：生成或强制重新生成单节点教学内容，返回可观察状态。
  - 完成标准：调用方不依赖 bool 猜测失败原因。
  - 验证方式：Fake LLM、已有内容和强制生成测试。
  - 实际修改：新增 `NodeContentGeneration` 与 `generate_node_content`；application 在调用既有生成 service 前检查项目归属和有效内容，返回 `generated`、`skipped` 或 `failed` 及最新节点详情。
  - 自动验证：`tests/test_application_projects.py` 为 `18 passed in 1.38s`、退出码 0；覆盖已有有效内容跳过、生成失败与强制重生成。
  - 手工验证：无；P4-07 接入客户端时统一验证。
  - 遗留问题：底层 service 仍自建 Session，当前 application 通过刷新调用方 Session 获取最新结果；后续不改变数据库模型。
  - 完成日期：2026-08-27。

- [x] `P4-04` 实现 `generate_practice_lesson`
  - 目标文件：`learning_ext/application/study.py`。
  - 复用位置：`generate_practice_lesson_to_db:395`。
  - 前置依赖：`P4-01`。
  - 实施内容：生成节点实操课程并返回任务结果。
  - 完成标准：普通节点和实操型节点行为明确。
  - 验证方式：application 测试。
  - 实际修改：新增 `PracticeLessonGeneration` 和 `generate_practice_lesson`；复用既有任务生成 service，显式请求可用于普通或实操型节点，返回 `generated`、`skipped` 或 `failed` 及最新任务详情。
  - 自动验证：`tests/test_application_projects.py` 为 `19 passed in 1.52s`、退出码 0；覆盖显式生成、已有任务跳过和强制生成失败。
  - 手工验证：无；P4-07 接入客户端时统一验证。
  - 遗留问题：底层 service 仍自建 Session，application 刷新调用方 Session 后读取任务结果。
  - 完成日期：2026-08-27。

- [x] `P4-05` 实现 `generate_node_resources`
  - 目标文件：`learning_ext/application/study.py`。
  - 复用位置：`generate_resources:75`、`save_resources_to_db:138`。
  - 前置依赖：`P4-01`。
  - 实施内容：生成并保存节点资料；保留失败信息和已存在处理规则。
  - 完成标准：资料生成与节点读取分离。
  - 验证方式：Fake LLM/HTTP、已有资料和失败测试。
  - 实际修改：新增 `ResourceGeneration` 和 `generate_node_resources`；显式调用既有资料生成与保存 service，替换 AI 资料、保留手工资料，并返回失败原因和当前详情。
  - 自动验证：`tests/test_application_projects.py` 为 `20 passed in 1.59s`、退出码 0；覆盖 AI 资料替换、手工资料保留和生成失败。
  - 手工验证：无；P4-07 接入客户端时统一验证。
  - 遗留问题：资料抓取本身仍是同步网络调用；P6 运行时编排时需统一超时和取消策略。
  - 完成日期：2026-08-27。

- [x] `P4-06` 实现 `save_node_note`
  - 目标文件：`learning_ext/application/study.py`。
  - 复用位置：`notes/service.py:save_note:39`。
  - 前置依赖：`P4-02`。
  - 实施内容：保存节点笔记并返回最新结果。
  - 完成标准：节点、项目和笔记输入关系明确。
  - 验证方式：创建和更新笔记测试。
  - 实际修改：新增 `NodeNoteSave` 和 `save_node_note`；先验证节点和项目归属，再复用既有笔记 upsert，返回最新笔记与节点详情。
  - 自动验证：`tests/test_application_projects.py` 为 `21 passed in 1.60s`、退出码 0；覆盖笔记创建、更新和稳定 ID。
  - 手工验证：无；P4-07 接入客户端时统一验证。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P4-07` 接入 Gradio、API 和 Next.js 节点详情
  - 目标范围：`StudyWorkbenchPage`、`api/routers/nodes.py`、`frontend/features/workspace/`。
  - 前置依赖：`P4-02` 至 `P4-06`。
  - 实施内容：旧 Page 调用 application；API 将读取和生成设计成不同端点；Next.js 展示课程、实操、笔记和资料。
  - 完成标准：选择节点只读取；用户明确操作才触发生成。
  - 验证方式：新旧客户端回归和端到端测试。
  - 实际修改：FastAPI 新增节点详情、课程生成、实操生成、资料生成与笔记保存端点；Gradio 节点选择和自动首节点加载改为 `get_node_detail` 纯读取，显式按钮调用对应 application；Next.js 新增节点详情、显式生成和笔记保存面板。
  - 自动验证：`tests/test_application_projects.py tests/test_api.py tests/test_pages.py` 为 `71 passed, 1 warning in 31.63s`、退出码 0；`npm run typecheck`、`npm run build` 均退出码 0。
  - 手工验证：隔离 SQLite + Fake LLM 下，Chrome DevTools 验证 Next.js 加载节点详情、依次触发课程/实操/资料三个显式操作；页面真实发出 `PUT /backend-api/nodes/4/note`，服务端读取确认笔记已持久化。Gradio 回归由 `tests/test_pages.py` 覆盖，确认节点选择和自动首节点加载不调用生成函数。
  - 遗留问题：未在真实 LLM 和外网资料源下进行手工端到端验证；资料生成仍为同步网络调用，其任务化与取消边界留待后续运行时迁移。
  - 完成日期：2026-08-27。

### （二）FSRS 复习

- [x] `P4-08` 实现 `get_due_cards` application 用例
  - 目标文件：`learning_ext/application/review.py`。
  - 现有位置：`review.py:_load_next:111`；`fsrs_review/service.py:get_due_cards:164`。
  - 前置依赖：`P3-GATE`。
  - 实施内容：返回待复习卡片和必要上下文，不返回 Gradio 格式。
  - 完成标准：无到期卡片和有到期卡片行为明确。
  - 验证方式：时间固定的 application 测试。
  - 实际修改：新增 `learning_ext/application/review.py` 的 `DueReviewCard`、`DueCards` 和 `get_due_cards`；复用 FSRS 查询 service，保留用户和项目边界，将 SQLModel 卡片转换为客户端无关结果。
  - 自动验证：`tests/test_application_projects.py tests/test_fsrs_review.py` 为 `39 passed in 2.10s`、退出码 0；使用固定 UTC 时间覆盖到期、未来卡片、空队列和非法 limit，断言读取不改变复习次数。
  - 手工验证：无；在 `P4-10` 接入三客户端时统一验证。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P4-09` 实现 `review_fsrs_card` application 用例
  - 目标文件：`learning_ext/application/review.py`。
  - 现有位置：`review.py:_review:128`；`fsrs_review/service.py:review_card:110`。
  - 前置依赖：`P4-08`。
  - 实施内容：提交评分并返回更新后的调度结果和下一张卡片所需信息。
  - 完成标准：评分范围、卡片不存在和调度失败行为明确。
  - 验证方式：FSRS application 测试。
  - 实际修改：新增 `ReviewSubmission` 和 `review_fsrs_card`；application 在调用既有 FSRS 调度 service 前校验卡片用户和可选项目归属，返回已持久化的调度字段及同范围下一张到期卡片。
  - 自动验证：`tests/test_application_projects.py tests/test_fsrs_review.py` 为 `41 passed in 2.52s`、退出码 0；覆盖真实评分后的复习次数/下一次时间、下一张卡片、卡片不存在、跨用户和非法评分。
  - 手工验证：无；在 `P4-10` 接入三客户端时统一验证。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P4-10` 接入 Gradio、API 和 Next.js 复习页
  - 目标范围：`ReviewPage`、复习 Router、`frontend/features/review/`。
  - 前置依赖：`P4-08`、`P4-09`。
  - 实施内容：共享 application；实现卡片显示、翻面、四档评分和下一张卡片加载。
  - 完成标准：复习结果和下一复习时间持久化正确。
  - 验证方式：新旧客户端对照和端到端测试。
  - 实际修改：新增 `/api/v1/reviews/due` 与 `/api/v1/reviews/{card_id}`；Gradio `ReviewPage` 读取和评分改为 application 调用；Next.js 工作台新增按项目加载的到期卡片、翻面、四档评分、空队列、失败和重试状态。
  - 自动验证：`tests/test_pages.py::TestReviewPageLogic tests/test_api.py` 为 `15 passed in 13.26s`、退出码 0；`tests/test_application_projects.py tests/test_fsrs_review.py` 为 `41 passed in 2.89s`、退出码 0；`npm run typecheck`、`npm run build` 均退出码 0。覆盖 Gradio 读取到期卡片、application 评分持久化和 FastAPI 复习契约。
  - 手工验证：隔离 SQLite + Fake LLM 下，Chrome DevTools 验证 Next.js 展示到期卡片、翻面显示答案、提交“良好”评分；卡片随后从队列消失，直接读取隔离数据库确认 `reps=1`，并已更新状态和下次复习时间。
  - 遗留问题：未使用真实生产学习数据进行浏览器验证；该边界不影响隔离功能回归。
  - 完成日期：2026-08-27。

### （三）测验闭环

- [x] `P4-11` 修正测验节点关联闭环
  - 目标文件：`learning_ext/quiz/service.py` 和相关测试。
  - 已知问题：`generate_quiz:56` 创建 `QuizQuestion` 时未写入 `node_id`，而 `grade_answer:119` 只有在 `q.node_id` 存在时才更新掌握度。
  - 前置依赖：`P3-GATE`。
  - 实施内容：明确多节点出题时每道题的节点归属并保存；补迁移兼容和测试。
  - 完成标准：生成的题目可追溯到节点，批改结果能正确回流掌握度。
  - 验证方式：测验生成、批改和掌握度测试。
  - 实际修改：在测验 LLM 契约中要求返回范围内的 `node_id`；`generate_quiz` 写入 `QuizQuestion.node_id`，对旧格式或无效 ID 按输入节点范围稳定轮转回退，并拒绝项目范围不一致的节点。
  - 自动验证：`tests/test_quiz.py` 为 `9 passed in 1.21s`、退出码 0；覆盖单节点、多个节点的显式归属、旧格式/无效 ID 兼容回退、批改记录和掌握度回流。
  - 手工验证：无；在 P4-14 的 Next.js 测验闭环中统一验证。
  - 遗留问题：历史上已经保存且 `node_id` 为空的题目没有可靠的语义来源，保持不回填；新生成题目均具备关联。
  - 完成日期：2026-08-27。

- [x] `P4-12` 实现 `generate_quiz` application 用例
  - 目标文件：`learning_ext/application/quiz.py`。
  - 复用位置：`quiz/service.py:generate_quiz:56`。
  - 前置依赖：`P4-11`。
  - 实施内容：封装出题范围、生成结果和失败行为。
  - 完成标准：用例可由 Page 和 API 调用，不依赖尚未完成的 Gradio 页面。
  - 验证方式：Fake LLM application 测试。
  - 实际修改：新增 `learning_ext/application/quiz.py` 的 `QuizGeneration`、`QuizQuestionResult` 和 `generate_quiz`；application 校验项目、节点归属、题目数量和题型，复用既有 LLM/service，并将已保存题目转换为结构化 DTO。
  - 自动验证：`tests/test_application_projects.py tests/test_quiz.py` 为 `35 passed in 2.08s`、退出码 0；覆盖 Fake LLM 生成、题目节点归属、项目范围和不存在节点。
  - 手工验证：无；在 P4-14 的 Next.js 测验闭环中统一验证。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P4-13` 实现 `submit_quiz_answer` application 用例
  - 目标文件：`learning_ext/application/quiz.py`。
  - 复用位置：`quiz/service.py:grade_answer:119`。
  - 前置依赖：`P4-11`、`P4-12`。
  - 实施内容：提交答案、批改、记录尝试并返回反馈和掌握度变化。
  - 完成标准：错误题目、重复提交和 LLM 失败行为明确。
  - 验证方式：application 测试。
  - 实际修改：新增 `QuizAnswerSubmission` 和 `submit_quiz_answer`；在调用既有批改 service 前校验题目、测验用户和非空答案，返回已保存的尝试 ID、批改反馈、对错、节点和刷新后的掌握度。
  - 自动验证：`tests/test_application_projects.py tests/test_quiz.py` 为 `36 passed in 1.99s`、退出码 0；覆盖 Fake LLM 批改、掌握度回流和空答案拒绝。
  - 手工验证：无；在 P4-14 的 Next.js 测验闭环中统一验证。
  - 遗留问题：同一道题可多次提交，当前保留每次尝试记录并重算掌握度，符合既有 `QuizAttempt` 追加模型。
  - 完成日期：2026-08-27。

- [x] `P4-14` 接入测验 API 和 Next.js 页面
  - 目标范围：测验 Router、Schema、`frontend/features/quiz/`。
  - 前置依赖：`P4-12`、`P4-13`。
  - 实施内容：实现出题、作答、批改反馈和结果展示；Gradio 页面是否补齐只作为过渡验证需求，不阻塞 Next.js。
  - 完成标准：Next.js 完成真实测验闭环。
  - 验证方式：端到端测试和数据库检查。
  - 实际修改：新增 `/api/v1/projects/{project_id}/quizzes` 生成接口和题目答案接口；Router 仅调用 application。Next.js 工作台新增节点范围、题量、题型选择、逐题作答、选择题选项、批改反馈、掌握度和下一题流程。
  - 自动验证：`tests/test_api.py tests/test_application_projects.py tests/test_quiz.py` 为 `51 passed in 3.90s`、退出码 0；`npm run typecheck`、`npm run build` 均退出码 0。
  - 手工验证：隔离 SQLite + Fake LLM 下，Chrome DevTools 验证生成题目、选择答案、提交、反馈展示；读取隔离数据库确认最新 `QuizAttempt` 为正确，题目 `node_id=4`，关联节点掌握度为 `0.4`。
  - 遗留问题：暂不接入仍为占位状态的 Gradio `QuizPage`；该页面不作为 P4-14 的迁移阻塞项，Next.js 是完整测验入口。
  - 完成日期：2026-08-27。

### （四）看板、审计与导出

- [x] `P4-15` 实现 `build_dashboard` application 用例
  - 目标文件：`learning_ext/application/dashboard.py` 或 `projects.py`，按模块规模决定。
  - 现有位置：`dashboard.py:_load_dashboard:83`；`dashboard/service.py:build_dashboard_data:264`。
  - 前置依赖：`P3-GATE`。
  - 实施内容：返回指标、状态统计、热力图和项目摘要的结构化结果。
  - 完成标准：不返回 Gradio Markdown 或 Plot 对象作为业务结果。
  - 验证方式：application 测试。
  - 实际修改：新增 `learning_ext/application/dashboard.py` 的 `Dashboard` 和 `build_dashboard`；application 验证可选项目的用户归属，复用既有聚合 service 并将项目选择项转换为结构化 `label/id` 数据。
  - 自动验证：`tests/test_application_projects.py tests/test_dashboard_project_ops.py` 为 `35 passed in 16.80s`、退出码 0；覆盖项目指标、14 天热力图、结构化项目列表和既有看板回归。
  - 手工验证：无；在 P4-18 接入浏览器看板时统一验证。
  - 遗留问题：无。
  - 完成日期：2026-08-27。

- [x] `P4-16` 实现节点与项目内容审计用例
  - 目标文件：`learning_ext/application/study.py`、`roadmap.py`。
  - 复用位置：`progress/audit.py:audit_node_content:68` 和现有路线审计 service。
  - 前置依赖：`P4-02`、`P3-06`。
  - 实施内容：明确只读审计与替换/重新生成的区别。
  - 完成标准：审计不会隐式执行破坏性替换。
  - 验证方式：application 测试。
  - 实际修改：新增 `NodeContentAudit`、`audit_node_content` 与 `ProjectRoadmapAudit`、`audit_project_roadmap`；节点审计仅调用既有质量审计，项目审计仅返回建议路线。实际替换仍只能通过既有带 `confirmed=True` 的 `replace_project_roadmap`。
  - 自动验证：`tests/test_application_projects.py` 为 `29 passed in 1.92s`、退出码 0；Fake LLM 审计下断言节点正文与项目 `roadmap_json` 在审计后完全不变。
  - 手工验证：无；审计 API/前端不属于当前 P4 明确接入项。
  - 遗留问题：审计调用仍是同步 LLM 请求，后续运行时任务化时需统一超时与取消策略。
  - 完成日期：2026-08-27。

- [x] `P4-17` 实现项目导出 application 用例
  - 目标文件：`learning_ext/application/projects.py` 或独立 `export.py`，按实际规模决定。
  - 复用位置：`export_roadmap_bundle:241`、`exporter/service.py`。
  - 前置依赖：`P3-GATE`。
  - 实施内容：统一路线 JSON、Markdown、进度报告和 Anki 导出入口；保留文件类型和文件名元数据。
  - 完成标准：Page 和 API 不重复拼装导出业务数据。
  - 验证方式：字节内容、文本内容和文件名测试。
  - 实际修改：新增 `learning_ext/application/export.py` 的 `ProjectExport` 与 `export_project`；复用既有路线包、Markdown、HTML 报告与 Anki ZIP service，并统一返回 `filename`、`media_type` 和 `content` 字节。Anki 既有实现实际为 ZIP，明确使用 `.zip` 和 `application/zip`。
  - 自动验证：`tests/test_application_projects.py tests/test_integration.py::TestExport tests/test_path_generator.py` 为 `46 passed in 2.38s`、退出码 0；覆盖四种导出的字节内容、文件扩展名、媒体类型和非法类型拒绝。
  - 手工验证：无；在 P4-18 浏览器下载校验时统一验证。
  - 遗留问题：HTML 报告可由浏览器打印为 PDF，但当前不伪装为 PDF 二进制文件。
  - 完成日期：2026-08-27。

- [x] `P4-18` 接入看板和导出前端
  - 目标范围：看板/导出 Router 与 `frontend/features/dashboard/`。
  - 前置依赖：`P4-15`、`P4-17`。
  - 实施内容：展示统计、状态分布、热力图并提供明确导出操作。
  - 完成标准：数据来自 application；导出文件可正常下载和打开。
  - 验证方式：浏览器测试和导出文件校验。
  - 实际修改：新增看板读取与导出下载 Router；Next.js 工作台新增指标、状态分布、14 天热力图、日报和四种导出控件。Router 仅返回 `Dashboard` DTO 或转发 `ProjectExport` 的内容与下载元数据。
  - 自动验证：`tests/test_api.py tests/test_application_projects.py` 为 `46 passed in 4.15s`、退出码 0；`npm run typecheck`、`npm run build` 均退出码 0。
  - 手工验证：隔离 SQLite + Chrome DevTools 验证 Next.js 显示 14 天热力图；在浏览器同源上下文读取四个下载响应，路线 JSON、Markdown、HTML 报告、Anki ZIP 均返回非空内容和正确的 `Content-Disposition` 文件名、媒体类型。
  - 遗留问题：HTML 报告仍需用户在浏览器打印为 PDF，未提供 PDF 二进制导出。
  - 完成日期：2026-08-27。

### （五）P4 完成标准

- [x] `P4-GATE` 完成 P4 阶段门禁
  - 前置依赖：`P4-01` 至 `P4-18`。
  - 完成标准：工作台、课程、笔记、资料、复习、测验、看板和导出在 Next.js 可用；读取和生成边界清晰；核心结果正确回流。
  - 验证方式：全套 application/API/前端测试和学习闭环手工验证。
  - 自动验证：`tests/test_application_projects.py tests/test_api.py tests/test_fsrs_review.py tests/test_quiz.py tests/test_dashboard_project_ops.py` 为 `78 passed in 26.11s`、退出码 0；P4 Gradio 定向回归 `tests/test_pages.py::TestReviewPageLogic tests/test_pages.py::TestStudyWorkbenchPageLogic tests/test_pages.py::TestStudyWorkbenchService` 为 `22 passed in 18.81s`、退出码 0；`npm run build` 退出码 0。
  - 手工验证：隔离 SQLite + Fake LLM + Chrome DevTools 覆盖节点详情/显式生成/笔记保存、FSRS 翻面和评分、测验生成/作答/反馈、看板热力图和四类导出响应。评分与测验均已通过 SQLite 读回验证持久化。
  - 修改文件范围：`learning_ext/application/`、`learning_ext/pages/review.py`、`learning_ext/pages/study_workbench.py`、`learning_ext/quiz/service.py`、`api/`、`frontend/`、相关测试与迁移 TODO。
  - Gradio 可用性：保留；路线、工作台和复习页面继续调用同一 application 用例，测验旧页仍为历史占位入口，Next.js 是完整测验入口。
  - 行为差异：节点读取不再隐式生成课程或资料；所有生成均需显式请求。Anki 导出准确标识为 ZIP，HTML 报告准确标识为可打印 HTML。
  - 遗留风险：真实 LLM、外网资料抓取和真实用户本地数据库尚未完成完整浏览器回归；审计和资料生成仍为同步调用，后续运行时迁移需统一任务、超时和取消边界。
  - 下一阶段：可以进入 P5；继续保留 Gradio，P7 前不得删除或替换其启动链。
  - 完成日期：2026-08-27。

## 八、P5：Kotaemon 能力迁移

### （一）无 Gradio 技术验证

- [x] `P5-01` 验证 indexing pipeline 的无 Gradio 调用路径
  - 目标位置：项目侧 PoC；参考 `kotaemon/libs/ktem/ktem/index/base.py` 和文件索引实现。
  - 前置依赖：`P4-GATE`。
  - 实施内容：使用样例文档验证索引 pipeline 可以在不构建 Page 的情况下运行。
  - 完成标准：记录初始化依赖、输入、输出、事件和持久化结果。
  - 验证方式：本地样例文档 smoke test。
  - 实际修改：新增隔离 PoC `.tmp/p5_indexing_smoke.py` 与退出码包装器 `.tmp/p5_indexing_runner.cmd`；仅复用 `IndexManager -> FileIndex -> IndexDocumentPipeline.stream`，没有构建或导入 Gradio Page。
  - 初始化依赖：`manual_flowsettings` 指向 `.tmp/manual-app-data` 的 SQLite/文件存储；Kotaemon 真实 Chroma 向量库与 LanceDB 文档库；测试进程内注入确定性 Fake Embedding，避免真实模型和网络调用；`THEFLOW_TEMP_PATH` 定向到 `.tmp`。
  - 输入与输出：输入为隔离 TXT；输出为 `file_ids`、`errors`、解析后的 `docs`，并按 `debug` 与 `index` channel 产出进度事件。
  - 持久化结果：同一 `FileIndex`（ID 4）完成两个样例文件索引，最终 `source_count=2`、`relation_count=4`，每个文件各有一条 document 与一条 vector 关系。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe .tmp/p5_indexing_smoke.py`（由 `.tmp/p5_indexing_runner.cmd` 执行）成功；事件覆盖转换、切分、文档写入、向量写入和完成状态；真实退出码 `0`。
  - 手工验证：不适用（本任务验证无 UI 调用路径）。
  - 遗留问题：底座初始化仍会实例化其配置中的可选嵌入提供方，产生 Mistral tokenizer 与 Chroma telemetry 警告；根目录已有本次首次运行生成的 `.theflow/` 测试运行态，未删除。`chunk_overlap=0` 会回退开发默认值，不能与小于默认 overlap 的 chunk size 组合。
  - 完成日期：2026-08-27。

- [x] `P5-02` 验证 retriever pipeline 的无 Gradio 调用路径
  - 目标位置：项目侧 PoC；参考 `FileIndex.get_retriever_pipelines:462`。
  - 前置依赖：`P5-01`。
  - 实施内容：解决或绕开 `_selector_ui.get_selected_ids` 的 UI 依赖，不修改底座源码。
  - 完成标准：可通过文件/集合 ID 明确选择检索范围。
  - 验证方式：样例查询返回预期文档片段。
  - 实际修改：新增隔离 PoC `.tmp/p5_retrieval_smoke.py` 与 `.tmp/p5_retrieval_runner.cmd`；以 `ExplicitSelectionAdapter` 注入 `_selector_ui`，仅实现 `get_selected_ids`，未实例化 `FileSelector` 或修改 Kotaemon。
  - 调用约定：API 侧传入文件 ID 列表；底座已有的 JSON 编码文件组 ID 列表会由 `DocumentRetrievalPipeline` 展平。构造 retriever 后必须调用组件入口 `retriever(query)`，以应用 `set_run({".doc_ids": ...})` 保存的选择范围，不能直接调用 `run(query)`。
  - 自动验证：复用 `P5-01` 的隔离 FileIndex 和真实 Chroma/LanceDB；直选文件 ID 与 JSON 文件组 ID 各执行一次 vector 检索，均返回包含 `FileIndex persists source, document, and vector relations.` 的片段；包装器记录真实退出码 `0`。
  - 手工验证：不适用（本任务验证无 UI 调用路径）。
  - 遗留问题：当前适配器仍是 PoC 的私有注入，P5-04 需要收敛为项目侧稳定 Adapter 契约；底座仍发出可选嵌入提供方初始化和 Chroma telemetry 警告，且小样例会提示请求结果数大于索引元素数，不影响检索结果。
  - 完成日期：2026-08-27。

- [x] `P5-03` 验证 reasoning pipeline 和流式事件
  - 目标位置：项目侧 PoC；参考 `BaseReasoning.get_pipeline`。
  - 前置依赖：`P5-02`。
  - 实施内容：记录 pipeline 输入、stream 事件类型、最终答案、引用和错误行为。
  - 完成标准：可以设计客户端无关的 RAG Gateway 契约。
  - 验证方式：Fake retriever 契约测试和本地真实 smoke test。
  - 实际修改：新增 `tests/test_kotaemon_reasoning_contract.py`、隔离 PoC `.tmp/p5_reasoning_smoke.py` 和 `.tmp/p5_reasoning_runner.cmd`；测试未构建 Chat Page 或 Gradio 组件。
  - 流式边界：输入为 `message`、`conv_id`、`history` 与显式 retriever；`stream()` 依次产生 `info`（证据展示）和 `chat`（回答分片）事件，并通过生成器返回最终 `Document`，其中包含 citation、mindmap、qa_score 等 metadata。
  - 自动验证：`tests/test_kotaemon_reasoning_contract.py` 为 `2 passed`、退出码 `0`，覆盖 Fake Retriever 的客户端无关 `info/chat/final answer` 契约及异常向调用方传播；`FullQAPipeline.get_pipeline(...).stream(...)` 复用 P5-02 的真实 Chroma/LanceDB 检索器，产生证据事件与两个 chat 分片，最终回答为测试 Fake LLM 的两段拼接，包装器真实退出码 `0`。
  - 引用与错误：本次真实 smoke 显式设为 `highlight_citation=off`，最终 citation 为 `null`；启用引用后的 citation 事件映射待 P5-05 以真实模型再验证。retriever 异常会从生成器抛出，Gateway 应转换为显式 `error` 事件并终止该次流。
  - 手工验证：不适用（本任务验证客户端无关的管线与事件语义）。
  - 遗留问题：底座 `info` 事件当前含 Gradio/HTML 片段，P5-04/05 必须转换为结构化 evidence/citation，而不能直接透传；现有流是同步生成器，HTTP 层需要 SSE/取消/超时边界。
  - 完成日期：2026-08-27。

### （二）项目侧 Kotaemon Adapter

- [x] `P5-04` 定义 `KotaemonRagGateway` 契约
  - 目标文件：`learning_ext/adapters/kotaemon_rag.py` 或等价项目侧位置。
  - 前置依赖：`P5-03`。
  - 实施内容：定义索引、检索、问答和流式事件接口；只抽象已验证的变化点。
  - 完成标准：application 不直接依赖 Chat Page、selector UI 或底座 Manager 的页面状态。
  - 验证方式：Fake Gateway 契约测试。
  - 实际修改：新增 `learning_ext/adapters/kotaemon_rag.py`，定义集合、索引请求/事件、显式检索范围/片段、对话请求和 `evidence`、`answer_delta`、`citation`、`complete`、`error` 五类流事件；新增 `tests/test_kotaemon_rag_gateway_contract.py`。
  - 设计边界：契约只暴露 P5-01 至 P5-03 已验证的索引、显式文件范围检索与回答流，不包含 Chat Page、selector UI、Gradio HTML、Kotaemon Manager 状态或未验证的资源删除/配置能力。
  - 自动验证：`tests/test_kotaemon_rag_gateway_contract.py tests/test_kotaemon_reasoning_contract.py -q` 为 `3 passed in 3.85s`，退出码 `0`；Fake Gateway 覆盖索引 progress/completed、检索片段及完整回答事件序列。
  - 手工验证：不适用（契约与 Fake 实现测试）。
  - 遗留问题：事件尚未绑定 HTTP SSE、取消或任务持久化；P5-05 需要将底座的 `info` HTML 转为 `RetrievedExcerpt`，并把底座异常映射为 `error` 事件。
  - 完成日期：2026-08-27。

- [x] `P5-05` 实现 Kotaemon RAG Adapter
  - 目标文件：项目侧 adapter。
  - 前置依赖：`P5-04`。
  - 实施内容：包装已验证的底层 pipeline；在应用生命周期内管理必要初始化。
  - 完成标准：不修改 `kotaemon/`；不调用 `ChatPage.chat_fn()`。
  - 验证方式：真实样例索引和查询 smoke test。
  - 实际修改：在 `learning_ext/adapters/kotaemon_rag.py` 实现 `KotaemonRagAdapter`；延迟加载既有 FileIndex，使用项目侧显式选择适配器，包装 indexing/retrieval/FullQAPipeline，并把底座 `Document` 转为 `IndexingEvent`、`RetrievedExcerpt` 和 `RagStreamEvent`。
  - 生命周期与边界：Adapter 仅按 collection ID 启动已存在的 Index，不隐式创建索引、上传文件或执行删除；底座导入与 Manager 初始化均在调用时发生。application 只面对 Gateway 契约，不接触 Chat Page、selector UI、Gradio HTML 或 Manager 页面状态。
  - 事件映射：检索结果按 `doc_id` 去重；先产生结构化 `evidence`，只将底座 `chat` channel 映射为 `answer_delta`，引用 metadata 映射为 `citation`，正常结束为 `complete`，底座异常映射为 `error`。
  - 自动验证：`tests/test_kotaemon_rag_gateway_contract.py tests/test_kotaemon_reasoning_contract.py -q` 为 `5 passed in 4.32s`，退出码 `0`；隔离 collection `4` 的真实 Chroma/LanceDB smoke 返回 `evidence -> answer_delta -> answer_delta -> complete`，包含样例资料片段，包装器记录真实退出码 `0`。
  - 手工验证：不适用（Adapter 真实管线 smoke）。
  - 遗留问题：默认 reasoning 使用当前 Kotaemon LLM 配置，真实模型/引用效果需在用户配置模型后验证；HTTP SSE、取消、超时和项目与 collection 的持久化关联由 P5-06 至 P5-09 处理。
  - 完成日期：2026-08-27。

### （三）知识问答和资料库

- [x] `P5-06` 实现 RAG 对话 application 用例
  - 目标文件：`learning_ext/application/chat.py`。
  - 前置依赖：`P5-05`。
  - 实施内容：组织问题、检索范围、历史、回答事件和引用结果。
  - 完成标准：application 只依赖 Gateway 契约。
  - 验证方式：Fake Gateway application 测试。
  - 实际修改：新增 `RagChatRequest` 与 `stream_rag_chat`，并从 `learning_ext.application` 导出；用例只组装 `RagAnswerRequest` 并调用注入的 `KotaemonRagGateway`。
  - 行为边界：空问题、缺失集合或缺失显式资料范围直接产生 `error`；Gateway 流出现 `complete` 或 `error` 后终止；未给终止事件的正常流补发 `complete`；异常转换为 `error`。
  - 自动验证：`tests/test_application_chat.py tests/test_kotaemon_rag_gateway_contract.py tests/test_kotaemon_reasoning_contract.py -q` 为 `7 passed in 4.68s`，退出码 `0`；Fake Gateway 验证 request 归一化与流式事件转发。
  - 手工验证：不适用（application 契约测试）。
  - 遗留问题：collection 与项目的持久化关联、上传后的资源选择范围及 HTTP SSE 尚未实现，分别由 P5-07 至 P5-10 处理。
  - 完成日期：2026-08-27。

- [x] `P5-07` 实现 RAG 流式 API
  - 目标文件：`api/routers/chat.py` 和事件 Schema。
  - 前置依赖：`P5-06`。
  - 实施内容：将 application 事件转换为前端可消费的流式协议；包含完成和失败事件。
  - 完成标准：断开连接、失败和正常结束行为明确。
  - 验证方式：流式 API 契约测试。
  - 实际修改：新增 `api/routers/chat.py`、`api/schemas/chat.py` 与 `get_rag_gateway` 依赖，并在 `api/main.py` 注册 `POST /api/v1/rag/stream`；Router 只负责 schema、Gateway 依赖、调用 `stream_rag_chat` 和 SSE 编码。
  - SSE 协议：每项为 `event: <kind>` 加 JSON `data`，payload 含 `text`、结构化 `excerpts`、`metadata`；application 的 `complete`、`error` 直接成为终止事件。
  - 断连与失败：每次产出前检查 `request.is_disconnected()`，断开后停止枚举；Gateway/application 异常会变为 `error` 事件，正常无终止流由 application 补发 `complete`。
  - 自动验证：`tests/test_api.py tests/test_application_chat.py -q` 为 `19 passed in 3.31s`，退出码 `0`；依赖覆写的 Fake Gateway 验证 `evidence`、`answer_delta`、`complete` SSE 编码及媒体类型。
  - 手工验证：不适用（FastAPI 流式契约测试）。
  - 遗留问题：同步 Gateway 在单次底座调用期间不能立即中断，P5-08 前端会中止读取；P5-09 需将 collection/file ID 改为项目资源的稳定关联。
  - 完成日期：2026-08-27。

- [x] `P5-08` 迁移知识问答前端
  - 目标位置：`frontend/features/chat/`。
  - 前置依赖：`P5-07`。
  - 实施内容：实现问题输入、流式回答、引用展示、停止和重试。
  - 完成标准：回答和引用可读，不依赖 Gradio Chatbot 数据结构。
  - 验证方式：端到端流式测试。
  - 实际修改：`frontend/lib/api.ts` 实现 SSE 解析，`frontend/features/chat/RagChatPanel.tsx` 实现消息、证据、停止、重试和错误状态；问答范围按知识点读取资料列表，只允许选择同一 collection 下已完成索引的资料，不暴露手工 collection/source ID 输入。
  - 自动验证：`npm run typecheck` 与 `npm run build` 均退出码 `0`；后端 RAG/资料/API 回归为 `28 passed in 6.03s`，退出码 `0`。
  - 手工验证：2026-08-28 在生产 Next.js 页面上使用隔离 Fake API 完成端到端验证：已索引资料可选，提问后可显示流式回答和引用；点击重试后产生第二轮完整回答；在 evidence 后、answer_delta 前点击停止，回答读取中止且停止按钮消失。Fake API 仅位于 `.tmp/`，未读写用户 SQLite、文件或模型配置。
  - 遗留问题：真实模型的回答质量、超时和引用相关性依赖用户配置的模型与已上传资料，需在日常使用中另行验证。
  - 完成日期：2026-08-28。

- [x] `P5-09` 实现资料上传和索引 application/API
  - 目标范围：项目侧 application、adapter、资料 Router。
  - 前置依赖：`P5-05`。
  - 实施内容：上传文档、启动索引、读取索引状态和失败信息。
  - 完成标准：调用方可观察索引进度；文件校验和失败状态明确。
  - 验证方式：样例文档端到端测试。
  - 实际修改：扩展 `KotaemonRagGateway` 的集合创建契约，`KotaemonRagAdapter` 在创建 `FileIndex` 时固定当时的默认 embedding；新增 `learning_ext/application/resources.py`，以现有 `KnowledgeNode.collection_ids` 绑定每节点一个集合，以 `NodeResource` 的既有字段记录 `indexing/completed/failed` 状态与 `source_id`，未改变数据库结构；新增本地 multipart 上传与 SSE 索引事件接口、状态读取接口，上传文件限制为 TXT、Markdown、PDF、DOCX、HTML 且最大 20 MB。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_application_resources.py tests/test_kotaemon_rag_gateway_contract.py tests/test_api.py` 为 `24 passed in 2.36s`，退出码 `0`；Fake Gateway 覆盖集合复用、成功/失败状态持久化、SSE、状态读取和格式拒绝。
  - 手工验证：隔离 SQLite、文件存储和确定性 embedding 下运行 `.tmp/p5_resource_upload_smoke.py`，真实链路返回 `started -> progress -> completed`，产生 collection `6`、resource `3` 和 source ID `5ffa18bd-a9cd-4471-91aa-ac77109989fa`，退出码 `0`；首次运行因新集合未锁定 embedding 名称返回 400，已保留为失败状态验证记录，修复后重跑成功。
  - 遗留问题：上传原件保留在 `KH_FILESTORAGE_PATH/learning_uploads`，删除和集合清理由 P5-10 在明确目标边界下实现；真实默认 embedding 与模型配置仍由 P5-12/P5-13 管理；P5-08 前端尚未改为稳定的节点资源选择。
  - 完成日期：2026-08-27。

- [x] `P5-10` 实现资料列表和删除 application/API
  - 目标范围：项目侧 application、adapter、资料 Router。
  - 前置依赖：`P5-09`。
  - 实施内容：查询资料、索引状态、集合关系和删除结果。
  - 完成标准：删除操作有明确目标和确认边界，不影响无关索引。
  - 验证方式：临时资料库测试。
  - 实际修改：新增节点资料列表与索引状态/集合/source 绑定读取，以及删除预览接口；预览返回精确 `resource_id`、资料标题、是否需要删除底座索引和确认短语 `删除资料 {resource_id}`，不执行删除。`DELETE /api/v1/nodes/{node_id}/resources/{resource_id}` 仅在确认短语完全匹配后删除绑定 collection 的单个 `source_id` 及该条 `NodeResource`；不支持批量或集合删除，原始上传文件仍保留。
  - 修复：真实隔离验证发现删除方法属于 Kotaemon 的 `IndexPipeline` 而非 `IndexDocumentPipeline`；`KotaemonRagAdapter` 改为调用 `IndexPipeline.delete_file`，没有复制或修改 Kotaemon 底座逻辑。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_kotaemon_rag_gateway_contract.py tests/test_application_resources.py tests/test_api.py` 为 `27 passed, 1 warning`，退出码 `0`；新增测试验证只把显式 source ID 传给底座基础删除方法。
  - 手工验证：经明确确认后，在 `.tmp/manual-app-data` 隔离 SQLite、docstore 和 vectorstore 中执行 `.tmp/p5_resource_delete_smoke.py`，退出码 `0`。目标 resource `6` 的 Source 从存在且有 `2` 条关系变为不存在且 `0` 条关系；同节点 resource `7` 的 Source 仍存在且保持 `2` 条关系；两份原始临时文件均保留。首次验证暴露错误入口并以退出码 `1` 结束，修复后重跑通过。
  - 遗留问题：真实用户资料的删除会永久移除对应索引，前端继续要求精确确认短语；原始上传文件的保留策略保持不变。
  - 完成日期：2026-08-28。

- [x] `P5-11` 迁移资料库前端
  - 目标位置：`frontend/features/resources/`。
  - 前置依赖：`P5-09`、`P5-10`。
  - 实施内容：上传、进度、列表、失败、重试和删除交互。
  - 完成标准：用户无需进入 Kotaemon Gradio 资料页。
  - 验证方式：浏览器端到端测试。
  - 实际修改：新增 `frontend/features/resources/ResourceLibraryPanel.tsx`，支持按节点选择、上传并消费索引 SSE、索引进度/失败展示、资料列表刷新，以及键入后端预览确认短语的单资料删除交互；不含批量删除。
  - 自动验证：`frontend/npm run typecheck` 和 `frontend/npm run build` 均退出码 `0`；资料列表、上传 SSE 和删除预览的后端回归已包含在 P5-10 的 `29 passed` 中。
  - 手工验证：2026-08-28 在生产 Next.js 页面验证了节点选择、已完成索引资料列表与资料问答范围联动；使用隔离 Fake API 和仅含测试文字的 `.tmp/p5-browser-upload.md` 验证上传后显示“正在建立索引任务”，结束后刷新为“已索引”资料列表。Fake API 未读写用户 SQLite、文件或模型配置；前端布局已修复项目卡片越过侧栏的问题。
  - 手工验证补充：2026-08-28 在生产 Next.js 页面和隔离 Fake API 中验证删除确认流程：初始“确认删除”不可点击，输入精确短语后变为可点击，提交后资料行消失并显示空列表；真实精确删除由 P5-10 的隔离 SQLite/docstore/vectorstore 验证。未在用户资料库中上传或删除资料。
  - 遗留问题：失败后的重试复用上传按钮，真实模型/文件格式导致的索引失败提示仍需随用户实际资料使用观察。
  - 完成日期：2026-08-28。

### （四）必要配置迁移

- [x] `P5-12` 定义模型配置迁移范围
  - 现有位置：`learning_ext/pages/quick_setup.py` 和 Kotaemon 设置页面。
  - 前置依赖：`P5-05`。
  - 实施内容：只列出新前端日常运行必需的配置；自动环境命令执行能力单独评估，不作为普通配置 API。
  - 完成标准：范围不包含未使用或高权限的可选能力。
  - 验证方式：配置项与实际 LLM/RAG 初始化路径对照。
  - 实际修改：确定 P5-13 仅允许管理四个显式字段：OpenAI 兼容 `base_url`、`api_key`（仅写入）、对话 `chat_model`、可选的 `embedding_model`；读取接口只返回配置状态、服务商/地址和模型名，绝不返回密钥。路线、课程、测验、复习卡片与问答都经 `learning_ext.llm` 使用对话模型；资料索引和 RAG 检索使用 FileIndex 固定的 embedding 名称，因此 embedding 仅在资料库启用时必需。连通性测试必须使用请求体内的临时配置，不写 `.env`、不更新运行时池。
  - 排除范围：不迁移 Kotaemon 通用 Settings、向量库/SQLite/文件路径、用户管理、Web Search、reranking、任意自定义类配置、代理/附加请求头、自动环境命令执行或完整 `.env` 查看；这些均超出本地单用户学习闭环，或具有额外权限/安全边界。
  - 自动验证：对照 `learning_ext/pages/quick_setup.py` 的 `.env` 字段读写、`learning_ext/llm/client.py` 的对话调用及 `learning_ext/adapters/kotaemon_rag.py` 的 FileIndex embedding 绑定；静态扫描确认当前 application/API 未提供 `.env` 读取或自动命令执行接口。
  - 手工验证：未执行，且未读取、修改或写入用户 `kotaemon/.env`。
  - 遗留问题：P5-13 会写入用户现有配置并可能更新运行时模型池，属于配置修改，实施和真实连通性测试前必须获得明确确认。
  - 完成日期：2026-08-27。

- [x] `P5-13` 迁移必要模型配置
  - 目标范围：配置 application、API 和前端页面。
  - 前置依赖：`P5-12`。
  - 实施内容：实现配置读取状态、写入和连通性测试；密钥不回显到前端。
  - 完成标准：用户可以配置日常所需模型并完成验证。
  - 验证方式：脱敏测试、配置写入测试和连通性测试。
  - 实际修改：新增 `learning_ext/application/configuration.py`，只管理 `base_url`、仅写入的 `api_key`、`chat_model`、可选 `embedding_model`；读取状态不含密钥，写入后失效 `learning_ext.llm` 缓存，并仅在实际保存时更新名为 `learning-openai` 的 Kotaemon 运行时 LLM/embedding 模型。新增 `GET/PUT /api/v1/model-configuration` 和 `POST /api/v1/model-configuration/test`；后者只使用请求体临时连通性测试，不保存配置。Next.js 新增模型配置面板，密钥输入不回填、保存后立即清空。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_application_configuration.py tests/test_api.py tests/test_application_resources.py tests/test_application_chat.py` 曾为 `28 passed in 3.02s`，退出码 `0`；后续配置/API 回归 `24 passed in 3.09s`，新增 `.env` 换行注入拒绝。覆盖临时 `.env` 写入、其他配置行保留、API Key 脱敏、临时连通性测试和 HTTP 契约。`frontend/npm run typecheck`、`frontend/npm run build` 均退出码 `0`。
  - 手工验证：未对用户 `kotaemon/.env` 或真实模型服务执行保存/连通性调用；测试仅使用临时文件、Fake 运行时模型池和 Fake HTTP 响应。
  - 遗留问题：首次在真实应用保存会改写用户 `.env` 并更新 Kotaemon 模型池，这是由用户点击保存触发的配置操作；真实供应商模型名、密钥和网络连通性仍需用户在本机自行确认。
  - 完成日期：2026-08-27。

### （五）P5 完成标准

- [x] `P5-GATE` 完成 P5 阶段门禁
  - 前置依赖：`P5-01` 至 `P5-13`。
  - 完成标准：问答、资料库和必要配置可在 Next.js 使用；项目 API 不依赖 Kotaemon Page；底座源码未修改。
  - 验证方式：Adapter 契约、真实 RAG smoke test 和前端端到端测试。
  - 实际修改：本阶段新增 Kotaemon RAG Adapter、问答/资料/模型配置 application 与 API、Next.js 资料问答、资料库和模型配置界面；未修改 `kotaemon/`，未替换 Gradio 启动链。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests` 为 `199 passed, 6 skipped, 1 warning in 38.52s`，退出码 `0`；资料/RAG/API 定向测试为 `27 passed, 1 warning`，退出码 `0`；前端 `npm run typecheck` 与 `npm run build` 均退出码 `0`；`git diff --check` 退出码 `0`，仅有既有文件 CRLF 转换警告。
  - 手工验证：隔离真实 FileIndex 上传产生 `started -> progress -> completed`；隔离真实删除验证目标 Source/关系从 `存在/2` 变为 `不存在/0`，另一资料保持 `存在/2`；生产 Next.js 页面验证资料问答流式回答、引用、停止、重试、上传进度和删除确认；隔离 Gradio 在 `http://127.0.0.1:7861` 返回 HTTP `200` 后已停止。当前生产 Next.js `http://127.0.0.1:3006` 与 FastAPI `http://127.0.0.1:8000` 均可用。
  - Gradio 可用性：保留。P5 未删除或移动 Page，也未改动 `custom_app.py`、`launcher.py`、`run.bat` 的 Gradio 主链；隔离 Gradio 启动验证通过。
  - 行为差异：新前端资料删除强制键入精确确认短语，且与现有上传行为一致地保留原始上传文件；模型 Key 读取接口不返回密钥。两项均为有意安全边界。
  - 遗留风险：真实 LLM 的回答质量、模型网络超时、不同文档格式的索引失败及用户资料的永久索引删除仍依赖实际配置和资料；全仓底座测试仍有既有顶层 `index` 导入失败，项目回归范围保持根目录 `tests/`。
  - 下一阶段：可以开始 P6 的开发/桌面启动链迁移，Gradio 继续作为回退入口。
  - 完成日期：2026-08-28。

## 九、P6：浏览器与桌面端切换

> 范围说明（2026-08-28）：本轮只验收浏览器前端和 FastAPI/application 链路。PyWebView、exe、便携版和桌面端矩阵暂不执行，相关条目保持未完成并标记为范围外暂停，不阻塞前后端工作。

### （一）运行模式设计

- [x] `P6-01` 确定开发模式启动方式
  - 目标文件：开发脚本和 README。
  - 前置依赖：`P5-GATE`。
  - 实施内容：明确 FastAPI 和 Next.js 开发服务器的端口、启动顺序和日志位置。
  - 完成标准：一条明确命令可以启动可开发环境；端口冲突行为清楚。
  - 验证方式：全新终端启动和关闭验证。
  - 实际修改：新增 `scripts/start_frontend_dev.py`；使用 Kotaemon venv 启动 FastAPI `127.0.0.1:8000`，使用本地 Node/Next.js 启动 `127.0.0.1:3000`，自动注入与现有启动链一致的 Python 路径、占位模型环境和离线变量，转发输出并写入 `logs/frontend-dev-api.log` 与 `logs/frontend-dev-next.log`。README 增加唯一开发命令、端口、日志和退出说明。
  - 自动验证：脚本语法编译退出码 `0`；在 API 已占用 8000 时脚本明确提示并退出码 `1`；释放端口后全新启动，API、前端和 `/api/v1/projects` 真实请求均返回 HTTP `200`。
  - 手工验证：按 Ctrl+C 停止脚本后，3000/8000 均无监听且子进程不存在。因为由 Ctrl+C 人工中断，外层终端返回退出码 `1`，但脚本已输出“正在停止开发服务”并完成回收。
  - 遗留问题：开发模式仍需要本机安装 Node.js；打包模式不依赖开发 Node 环境的资源方案由 P6-02 决定。
  - 完成日期：2026-08-28。

- [x] `P6-02` 确定打包模式前端资源方式
  - 目标范围：Next.js 构建配置、launcher 和打包脚本。
  - 前置依赖：`P6-01`。
  - 实施内容：确定静态导出或本地 Node 服务方案，以实际功能和打包约束为依据。
  - 完成标准：方案支持 PyWebView、离线启动和便携版分发。
  - 验证方式：最小打包 PoC。
  - 实际修改：`frontend/next.config.ts` 改用 `output: "export"`；前端统一通过 `NEXT_PUBLIC_LEARNING_API_BASE` 获取 API 基址，发布态默认为同源 `/api/v1`，开发脚本显式指向 `http://127.0.0.1:8000/api/v1`；FastAPI 在 `frontend/out` 存在时托管静态页面，并仅允许本机 Next.js 开发端口 CORS。新增 API 回归测试覆盖配置目录下静态首页的托管；忽略生成的 `frontend/out/`。
  - 方案结论：选择 Next.js 静态导出，不在 exe/便携版中引入 Node 常驻服务。原因是现有页面全部在客户端请求数据，不依赖 Next 服务器能力；Next 静态导出不支持 rewrites，故移除 `/backend-api` 代理，由 FastAPI 提供同源 API 和静态资源。PyWebView 只需打开 FastAPI 本机地址。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_api.py` 退出码 `0`，`21 passed`；`npm run typecheck` 退出码 `0`；`npm run build` 退出码 `0`，生成 `frontend/out/index.html` 和静态资源。
  - 手工验证：使用 `scripts/start_frontend_dev.py` 启动后，`http://127.0.0.1:8000/`、`http://127.0.0.1:8000/api/v1/projects` 和 `http://127.0.0.1:3000/` 均返回 HTTP `200`；监听进程分别为 FastAPI 和 Next.js。
  - 遗留问题：静态资源已在当前工作区生成但尚未纳入 exe/便携版构建清单；这由后续启动器和打包脚本任务完成。Gradio 主链未修改。
  - 完成日期：2026-08-28。

### （二）Launcher 切换

- [x] `P6-03` 调整 `launcher.py` 后端进程编排
  - 目标文件：`launcher.py`。
  - 前置依赖：`P6-02`。
  - 实施内容：启动 API 和所需前端资源服务，执行就绪等待，并保留清晰日志。
  - 完成标准：不再把 Gradio 端口作为新 UI 的唯一入口。
  - 验证方式：浏览器模式启动和进程检查。
  - 实际修改：`launcher.py` 新增 `start_api_backend`，使用 Kotaemon venv 启动 `uvicorn api.main:app`，继承占位模型变量、项目和 Kotaemon 路径，转发 API 日志；默认 UI 改为 FastAPI 静态前端，端口默认 `8000`。保留 `start_gradio_backend`，通过 `LE_UI=gradio` 显式选择原 Gradio 回退服务。
  - 自动验证：`kotaemon/.venv/Scripts/python.exe -m pytest -q tests/test_launcher_windowed.py tests/test_api.py` 退出码 `0`，`26 passed`；启动器模块语法编译退出码 `0`；隔离端口 `8012` 上由 `launcher.start_api_backend` 启动的真实服务对 `/` 和 `/api/v1/projects` 均返回 HTTP `200`，随后正常终止子进程。
  - 手工验证：当前 FastAPI 静态前端运行于 `http://127.0.0.1:8000/`；开发态 Next.js 已验证可由脚本启动于 `http://127.0.0.1:3000/`，当前未常驻。PyWebView 窗口实际交互留给 P6-04 的专门验证。
  - 遗留问题：启动器失败时的静态资源缺失、进程提前退出与端口场景尚未覆盖，后续 P6-05 专门处理；Gradio 未删除。
  - 完成日期：2026-08-28。

- [x] `P6-04` 调整浏览器和 PyWebView 打开地址
  - 目标文件：`launcher.py`。
  - 前置依赖：`P6-03`。
  - 实施内容：浏览器和窗口加载同一个 Next.js 地址；保持现有窗口尺寸和降级行为。
  - 完成标准：两种模式看到同一 UI。
  - 验证方式：浏览器和 PyWebView 手工验证。
  - 实际修改：浏览器和 PyWebView 均使用启动器选定的 FastAPI 地址；窗口尺寸和浏览器降级逻辑保留。
  - 自动验证：隔离启动器首页返回静态 Next.js HTML。
  - 手工验证：浏览器入口 `http://127.0.0.1:8000/` 已打开并可见；PyWebView 真窗口留待有桌面会话时复核。
  - 遗留问题：PyWebView 实际窗口交互尚未在当前无头环境执行。
  - 完成日期：2026-08-28。

- [x] `P6-05` 完善启动失败和端口占用处理
  - 目标文件：`launcher.py` 和相关测试。
  - 前置依赖：`P6-03`、`P6-04`。
  - 实施内容：覆盖端口占用、API 未就绪、前端资源缺失和子进程提前退出。
  - 完成标准：失败信息可定位，不打开空白窗口。
  - 验证方式：自动测试和故障注入。
  - 实际修改：启动前检查静态首页，端口池耗尽立即报错；等待期间监测子进程提前退出并验证首页 HTTP `200`。
  - 自动验证：资源缺失、子进程退出、端口冲突和启动器路径测试通过。
  - 手工验证：正常启动和隔离端口服务首页均返回 `200`。
  - 遗留问题：未执行系统级全部端口占用注入。
  - 完成日期：2026-08-28。

- [x] `P6-06` 完善子进程退出和日志转发
  - 目标文件：`launcher.py` 和相关测试。
  - 前置依赖：`P6-03`。
  - 实施内容：窗口或浏览器模式退出时回收本次启动的进程；保留 API 和前端日志。
  - 完成标准：不遗留本次启动的 Python/Node 进程。
  - 验证方式：进程检查和测试。
  - 实际修改：API 日志持续转发；窗口关闭或 Ctrl+C 后终止并等待子进程，超时再强制结束。
  - 自动验证：开发脚本停止后 3000/8000 无监听；隔离 API 子进程正常终止。
  - 手工验证：已确认本次启动的服务可回收，未触碰其他进程。
  - 遗留问题：PyWebView 关闭事件需桌面会话复核。
  - 完成日期：2026-08-28。

### （三）构建和便携版

- [x] `P6-07` 更新开发启动脚本
  - 目标文件：`run.bat`、`start.bat` 或最终确认的脚本。
  - 前置依赖：`P6-01`、`P6-03`。
  - 实施内容：按新启动链启动服务；保留明确错误输出。
  - 完成标准：开发者无需手工启动多个未说明的终端。
  - 验证方式：Windows 命令行启动测试。
  - 实际修改：README 固定使用 `scripts/start_frontend_dev.py`，按 API 就绪后启动 Next.js，统一输出和清理。
  - 自动验证：脚本语法、端口冲突、全新启动、真实 API 请求和 Ctrl+C 回收均已验证。
  - 手工验证：Windows PowerShell 启动链验证通过。
  - 遗留问题：exe/便携版实际构建仍待确认后执行。
  - 完成日期：2026-08-28。

- [ ] `P6-08` 更新 exe 构建脚本
  - 目标文件：`build_exe.bat` 和 PyInstaller 配置。
  - 前置依赖：`P6-02`、`P6-04`。
  - 实施内容：包含新后端入口和前端资源；移除已不需要的旧入口只留到 P7。
  - 完成标准：构建成功，产物能打开新 UI。
  - 验证方式：干净构建和 exe smoke test。
  - 执行状态：构建脚本已更新，等待确认后执行会清理 `build/`、`dist/`。
  - 当前范围：暂停，桌面发布不属于本轮前后端交付。

- [ ] `P6-09` 更新便携版打包脚本
  - 目标文件：`pack_portable.bat`。
  - 前置依赖：`P6-08`。
  - 实施内容：包含前端静态资源、API 代码和必要运行时；不遗漏离线资源。
  - 完成标准：便携目录在预期机器环境可启动。
  - 验证方式：独立目录 smoke test 和文件清单检查。
  - 执行状态：脚本已加入 API 与静态前端复制，等待确认后执行会清理并重建 `dist/LearnEverything-Portable`。
  - 当前范围：暂停，便携版不属于本轮前后端交付。

- [ ] `P6-10` 完成桌面端矩阵验证
  - 前置依赖：`P6-05` 至 `P6-09`。
  - 实施内容：验证浏览器、PyWebView、exe、便携版、端口占用、首次启动、离线启动和关闭回收。
  - 完成标准：所有场景记录实际结果和剩余风险。
  - 验证方式：测试矩阵执行记录。
  - 执行状态：暂停，桌面端不属于本轮前后端交付。

### （四）P6 完成标准

- [ ] `P6-GATE` 完成 P6 阶段门禁
  - 前置依赖：`P6-01` 至 `P6-10`。
  - 完成标准：浏览器和 exe 共用 Next.js；启动、关闭、日志和便携版验证通过；Gradio 仍保留为最后回退入口。
  - 验证方式：桌面端测试矩阵。
  - 执行状态：本轮不执行；前后端交付不以桌面端门禁为条件。

## 十、P7：移除 Gradio

### （一）删除前置审计

- [ ] `P7-01` 审计所有用户流程覆盖情况
  - 目标范围：迁移计划中的项目、路线、工作台、复习、测验、看板、问答、资料库和配置。
  - 前置依赖：`P6-GATE`。
  - 实施内容：逐项确认 Next.js 功能、API、application 和测试覆盖。
  - 完成标准：没有日常流程只能在 Gradio 完成。
  - 验证方式：功能矩阵审阅和端到端测试。

- [ ] `P7-02` 审计 FastAPI 对 Gradio 的依赖
  - 目标范围：`api/`、`learning_ext/application/`。
  - 前置依赖：`P7-01`。
  - 实施内容：扫描 Page、Gradio 组件、`gr.update()` 和 `ChatPage.chat_fn()` 依赖。
  - 完成标准：新主链路不依赖旧 UI。
  - 验证方式：依赖扫描和导入测试。

- [ ] `P7-03` 完成最终 Gradio 对照回归
  - 前置依赖：`P7-01`。
  - 实施内容：在删除前执行最后一次新旧客户端关键行为对照并保存结果。
  - 完成标准：业务差异已解决或明确批准。
  - 验证方式：对照记录。

### （二）旧 UI 和启动链清理

- [ ] `P7-04` 移除学习 Page 注册
  - 目标文件：`learning_ext/app.py` 和 `learning_ext/pages/__init__.py`。
  - 前置依赖：`P7-02`、`P7-03`。
  - 实施内容：移除学习 Tab/Page 注册，不触碰仍被 Kotaemon 底层使用的无关能力。
  - 完成标准：主应用不再构建学习 Gradio 页面。
  - 验证方式：应用启动和导入测试。

- [ ] `P7-05` 移除已替代的 Gradio Page 代码
  - 目标位置：`learning_ext/pages/`。
  - 前置依赖：`P7-04`。
  - 实施内容：按已验证范围删除 Page 和 Gradio 专用适配；删除前确认没有剩余引用。
  - 完成标准：application 和 service 保持完整，API 测试不受影响。
  - 验证方式：引用扫描和全套测试。

- [ ] `P7-06` 移除 Gradio 专用资源注入
  - 目标范围：`custom_app.py`、学习 UI CSS/JS 和模板补丁。
  - 前置依赖：`P7-05`。
  - 实施内容：删除只服务旧页面的 CSS、事件脚本和模板注入；确认新前端是否仍需要对应功能并已有替代。
  - 完成标准：不保留失效的 UI 补丁。
  - 验证方式：引用扫描和前端功能检查。

- [ ] `P7-07` 调整 `custom_app.py` 和主后端入口职责
  - 目标文件：`custom_app.py`、API 入口和 launcher。
  - 前置依赖：`P7-04`、`P7-06`。
  - 实施内容：让主启动链只启动实际需要的 API/RAG 能力；移除 Gradio launch。
  - 完成标准：正常运行不创建 Gradio 服务。
  - 验证方式：进程、端口和启动日志检查。

- [ ] `P7-08` 清理不再需要的 Gradio 直接依赖
  - 目标文件：依赖清单和打包配置。
  - 前置依赖：`P7-07`。
  - 实施内容：只清理项目不再需要且 Kotaemon 底层也不要求的依赖；先做引用和打包验证。
  - 完成标准：依赖清理不会破坏 Kotaemon RAG 能力。
  - 验证方式：干净环境安装、测试和打包。

### （三）文档与最终验证

- [ ] `P7-09` 更新架构和开发文档
  - 目标文件：`docs/ARCHITECTURE.md`、`README.md`、`learning_ext/README.md` 和相关指南。
  - 前置依赖：`P7-07`。
  - 实施内容：更新真实启动链、目录职责、开发命令、测试命令和故障排查。
  - 完成标准：文档中没有把 Gradio 描述为当前主 UI。
  - 验证方式：活动文档路径和关键词扫描。

- [ ] `P7-10` 完成最终全链路测试
  - 前置依赖：`P7-08`、`P7-09`。
  - 实施内容：运行 Python、API、前端、RAG、桌面端、exe 和便携版验证。
  - 完成标准：所有必需测试正常退出；失败项有明确处理结论。
  - 验证方式：最终测试报告。

- [ ] `P7-11` 关闭迁移风险和遗留问题
  - 目标位置：本文档“问题登记”。
  - 前置依赖：`P7-10`。
  - 实施内容：关闭已解决问题；未解决问题必须明确影响、负责人、后续计划和是否阻塞发布。
  - 完成标准：没有未分类的高风险问题。
  - 验证方式：风险审阅。

### （四）P7 完成标准

- [ ] `P7-GATE` 完成前端重构迁移
  - 前置依赖：`P7-01` 至 `P7-11`。
  - 完成标准：浏览器和桌面端使用同一套 Next.js；FastAPI 通过 application 调用核心逻辑；Gradio 不再位于主运行链路；文档和测试同步完成。
  - 验证方式：最终验收报告和里程碑审阅。

## 十一、持续问题登记

### （一）初始风险清单

| 编号 | 问题 | 影响阶段 | 计划处理 | 状态 |
|---|---|---|---|---|
| `R-001` | 工作台读取当前可能触发课程和资料生成 | P1、P4 | 将读取和生成拆分为独立 application 用例 | 待处理 |
| `R-002` | 部分内容生成函数内部创建 Session 并自行提交 | P3、P4 | 仅在具体用例需要统一事务时调整对应 service | 待处理 |
| `R-003` | 后台生成使用匿名 daemon thread，缺少任务状态 | P3、P4 | 为长任务增加可观察的 application/任务结果 | 待处理 |
| `R-004` | 测验题目未稳定关联 `node_id` | P4 | 先修正 service 和测试，再迁移测验 UI | 待处理 |
| `R-005` | Kotaemon 文件检索 pipeline 依赖 selector UI | P5 | 先完成无 Gradio PoC，再建立 adapter | 待处理 |
| `R-006` | 全仓库 pytest 收集与项目测试边界不清 | P0、P7 | 分开记录项目测试和底座测试入口 | 待处理 |
| `R-007` | 项目测试曾输出通过后不自动退出 | P0 | 定位残留线程/资源并记录实际退出码 | 待处理 |
| `R-008` | 当前工作区存在用户已有未提交变更 | 全阶段 | 每阶段开始前记录范围，不覆盖无关变更 | 持续约束 |
| `R-009` | 正式 SQLite 第 1 页头部在 schema 字段处出现 `WARNING: All log messages before absl::InitializeLog()` 普通文本，SQLite 连接返回 `unsupported file format` | 前后端真实数据回归 | 保留原文件只读取证；在用户确认恢复方案前不覆盖正式数据库，当前使用隔离恢复库验证前后端 | 阻塞 |
| `R-010` | 内容准备首批节点在 HTTP 请求内同步生成，剩余节点由匿名 daemon 线程生成；单节点课程、实操和 AI 资料接口也同步等待 LLM/网络调用 | 前后端长任务体验 | 统一任务 ID、状态查询、失败原因、取消/超时和进程重启边界；读取接口不得触发生成 | 待处理 |

### （二）新增问题模板

```markdown
| `R-009` | 问题描述 | 影响阶段 | 处理方案 | 待处理 |
```

问题状态使用：`待处理`、`处理中`、`已解决`、`已接受`、`阻塞`。

## 十二、最终完成定义

前端重构只有同时满足以下条件才算完成：

- [ ] 所有用户日常流程均可在 Next.js 完成。
- [ ] Gradio Page 和 FastAPI 没有维护两套独立业务逻辑。
- [ ] Application 是 Gradio 迁移期和最终 FastAPI 的共享业务入口。
- [ ] 核心路线、进度、FSRS、测验、笔记、看板和导出逻辑继续复用现有 service。
- [ ] Kotaemon 的索引、检索和问答通过项目侧 adapter 使用，未修改底座源码。
- [ ] 浏览器和 Windows exe 使用同一套 Next.js UI。
- [ ] 主启动链不再启动或渲染 Gradio。
- [ ] Python、API、前端、RAG、桌面端和打包验证均有最终结果。
- [ ] 架构、开发、启动、打包和故障排查文档已同步。
- [ ] 所有阻塞风险均已解决，剩余风险已有明确接受记录。
