# AGENTS.md - 开发代理指南

## 项目概述
学习 Agent：基于 Kotaemon RAG 底座 + FSRS 记忆算法的自建学习平台。
**Windows 桌面应用**，双击 exe 运行，PyWebView 包装窗口。

## 关键路径
- 学习特化代码: `learning_ext/`
- Kotaemon 底座(只读): `kotaemon/`
- 后端入口: `custom_app.py`
- 桌面启动器: `launcher.py`
- 本地配置: `kotaemon/.env`
- 架构文档: `docs/ARCHITECTURE.md`

## 开发命令
```bash
# 首次初始化 (联网装依赖，5-15分钟)
setup.bat

# 启动 (开发模式，浏览器或 PyWebView 窗口)
start.bat
# 或直接: kotaemon\.venv\Scripts\python.exe scripts\start_frontend_dev.py

# 查看后端日志: 启动时控制台实时输出
# 数据落: kotaemon\ktem_app_data\

# 打包 exe
build_exe.bat      # 打 launcher.exe
pack_portable.bat  # 组装完整便携版

# 停止: 关闭桌面窗口或 Ctrl+C
```

## 代码约定
- 学习特化模块全部放 `learning_ext/`，不修改 `kotaemon/` 底座
- service 函数第一参数恒为 `session: Session`
- LLM 调用走 `learning_ext.llm.chat/chat_json`
- 新增 Tab: `learning_ext/pages/` 加 BasePage 子类 + `app.py._build_learning_tabs` 注册
- 提示词放各模块 `prompts.py`
- 不写注释（除非复杂逻辑必要）

## 架构关键点
- **双 Python 进程**: launcher.exe (PyWebView) 用子进程跑 Kotaemon venv 的 python
- **路径**: custom_app.py 把 `kotaemon/` 加入 sys.path，因 Kotaemon 用 `import flowsettings`
- **环境变量占位**: cohere/voyage/mistral 缺 key 会崩，learning_ext/__init__.py 注入占位
- **离线模式**: HF_HUB_OFFLINE=1 避免启动访问 huggingface.co 超时

## 阶段路线
- [x] 阶段0: 脚手架 (Docker + 底座 + learning_ext 骨架 + 数据模型 + 路线Tab)
- [x] **切换: 改为 Windows 桌面 exe 方案** (launcher + PyWebView + PyInstaller)
- [ ] 阶段1: 路线闭环 (Agent调优 + 图谱可视化 + 节点状态机)
- [ ] 阶段2: 认知巩固 (FSRS复习UI + AI卡片提炼)
- [ ] 阶段3: 查漏+看板 (测验 + 错题本 + 热力图 + 日报)
- [ ] 阶段4: 增强 (费曼 + 苏格拉底 + 实操 + 导出)
- [ ] 阶段5: 演进 (Next.js 前端 + Kotaemon 作 RAG 微服务)

## 已知问题
- LSP 报错(ktem/theflow/sqlmodel 未解析)是本机 IDE 没识别 kotaemon/.venv，代码在 venv 内运行，忽略
- 首次启动慢 (~30-60s)，因加载 chromadb/langchain 等重库
- 国内网络需设 HF_HUB_OFFLINE=1 (custom_app.py 已默认设)
- 学习路线等功能需配 LLM key 后在 Resources 页或 .env 配置
