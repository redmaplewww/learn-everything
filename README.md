# 学习 Agent (Learn Everything)

> 给任意选题，AI 制定学习路线 + 辅助搭建系统环境 + 给出实操；带知识库、文献管理、学习进度跟踪、艾宾浩斯记忆曲线复习、查漏补缺测验。当前日常开发和使用入口是本机浏览器应用。

基于开源 [Kotaemon](https://github.com/Cinnamon/kotaemon) (RAG 底座) + FSRS v6 (记忆算法) + 自建学习特化模块。

## 快速开始

### 首次使用（开发者/高级用户）
1. **初始化环境**（需联网，约 5-15 分钟）：双击 `setup.bat`
2. **配置 LLM**：编辑 `kotaemon\.env`，填入任一 API key（DeepSeek 推荐）
3. **启动**：双击 `start.bat`

### 浏览器开发模式

浏览器前端使用 Next.js + FastAPI。源码目录中的 `start.bat` 会执行下列命令：

```powershell
kotaemon\.venv\Scripts\python.exe scripts\start_frontend_dev.py
```

脚本会启动 Next.js 前端 `http://127.0.0.1:3000` 和 FastAPI API `http://127.0.0.1:8000`。开发时应始终访问 `http://127.0.0.1:3000`；8000 只提供 `/api/v1/*` 接口，不提供 UI。日志写入 `logs/frontend-dev-api.log` 与 `logs/frontend-dev-next.log`；按 `Ctrl+C` 会回收两个子进程。端口已被占用时脚本会拒绝启动并提示对应端口。

浏览器开发服务默认使用 `kotaemon/ktem_app_data` 的正式 SQLite。需要用隔离数据进行开发或回归时，先设置 `LEARNING_DEV_DATA_DIR`，再运行启动命令；该变量会将服务切换到指定的数据目录，而不会改写正式 SQLite。

### 静态页面与桌面打包

执行 `frontend` 目录中的 `npm run build` 后，`launcher.py` 和打包 exe 会由 FastAPI 在 `http://127.0.0.1:8000/` 提供 `frontend/out` 的静态页面。该路径用于构建/打包验证，不是日常源码开发入口；桌面分发当前仍处于暂停演进状态。

### 打包成 exe 分发
1. `build_exe.bat` — PyInstaller 打包 launcher 为 `LearnEverything.exe`
2. `pack_portable.bat` — 组装完整便携版（含运行时，解压即用）

## 文件说明

| 文件 | 作用 |
|---|---|
| `start.bat` | 推荐启动入口：同时启动 Next.js（3000）与 FastAPI（8000） |
| `scripts/start_frontend_dev.py` | 本地开发服务编排与日志转发 |
| `launcher.py` | 构建/桌面启动器：启动 FastAPI 静态前端 + PyWebView 窗口 |
| `custom_app.py` | 后端入口：加载 LearningApp（Kotaemon + 学习 Tab） |
| `setup.bat` | 首次环境初始化（装 uv + venv + 依赖） |
| `build_exe.bat` | 打包 launcher.exe |
| `pack_portable.bat` | 组装可分发的完整便携版 |
| `learning_ext/` | 学习特化代码（路线/复习/测验/看板等） |
| `kotaemon/` | RAG 底座（fork，不改动） |

## 功能矩阵

| 功能 | 状态 | 说明 |
|---|---|---|
| 🎯 选题→学习路线 | ✅ 阶段1 | AI 拆知识 DAG，分阶段，可调整重生成 |
| 💬 知识库 RAG 问答 | ✅ 底座 | 上传 PDF/文献，带引用溯源 |
| 🔄 艾宾浩斯复习 | 🔜 阶段2 | FSRS v6 调度，4 档评分 |
| 📝 查漏测验 | ⏳ 阶段3 | AI 按薄弱点出题批改 |
| 📊 学习看板 | ⏳ 阶段3 | 热力图/甘特/掌握度/日报 |
| 🧑‍🏫 费曼对话 | ⏳ 阶段4 | AI 扮小白逼你讲解 |
| 🛠️ 实操辅助 | ⏳ 阶段4 | 编程选题自动出环境清单+练习 |
| 📤 导出 | ⏳ 阶段4 | Anki 牌组 / Markdown / PDF 报告 |

## 技术栈
- **底座**: Kotaemon (Gradio + SQLite + Chroma + LanceDB)
- **记忆**: fsrs (FSRS v6)
- **桌面**: PyWebView (Edge WebView2)
- **打包**: PyInstaller
- **LLM**: DeepSeek / GLM / 通义 / OpenAI / Ollama (任选)

## 项目结构
详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
