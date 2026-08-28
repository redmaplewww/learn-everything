# 学习 Agent (Learn Everything)

> 给任意选题，AI 制定学习路线 + 辅助搭建系统环境 + 给出实操；带知识库、文献管理、学习进度跟踪、艾宾浩斯记忆曲线复习、查漏补缺测验。**Windows 桌面应用，双击 exe 即用。**

基于开源 [Kotaemon](https://github.com/Cinnamon/kotaemon) (RAG 底座) + FSRS v6 (记忆算法) + 自建学习特化模块。

## 快速开始

### 首次使用（开发者/高级用户）
1. **初始化环境**（需联网，约 5-15 分钟）：双击 `setup.bat`
2. **配置 LLM**：编辑 `kotaemon\.env`，填入任一 API key（DeepSeek 推荐）
3. **启动**：双击 `run.bat`，或开发模式 `python launcher.py`

### Next.js 开发模式
迁移中的浏览器前端使用 Next.js + FastAPI。先执行 `setup.bat`，再在仓库根目录运行：

```powershell
kotaemon\.venv\Scripts\python.exe scripts\start_frontend_dev.py
```

脚本会启动 FastAPI `http://127.0.0.1:8000` 和 Next.js `http://127.0.0.1:3000`。开发态前端通过本机 CORS 直连 API；构建后的静态页面由 FastAPI 在 `http://127.0.0.1:8000/` 同源提供。日志写入 `logs/frontend-dev-api.log` 与 `logs/frontend-dev-next.log`；按 `Ctrl+C` 会回收两个子进程。端口已被占用时脚本会拒绝启动并提示对应端口。

浏览器开发服务默认使用 `kotaemon/ktem_app_data` 的正式 SQLite。需要用隔离数据进行开发或回归时，先设置 `LEARNING_DEV_DATA_DIR`，再运行启动命令；该变量会将服务切换到指定的数据目录，而不会改写正式 SQLite。

当前 `run.bat` 和 exe 仍打开 Gradio，作为迁移期间的回退入口；桌面启动链将在后续阶段切换为同一套 Next.js 页面。

### 打包成 exe 分发
1. `build_exe.bat` — PyInstaller 打包 launcher 为 `LearnEverything.exe`
2. `pack_portable.bat` — 组装完整便携版（含运行时，解压即用）

## 文件说明

| 文件 | 作用 |
|---|---|
| `launcher.py` | 桌面启动器：启动 FastAPI 静态前端 + PyWebView 桌面窗口，保留 Gradio 回退 |
| `custom_app.py` | 后端入口：加载 LearningApp（Kotaemon + 学习 Tab） |
| `setup.bat` | 首次环境初始化（装 uv + venv + 依赖） |
| `run.bat` | 启动程序 |
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
