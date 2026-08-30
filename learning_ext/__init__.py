"""
learning_ext - 学习 Agent 的学习特化模块

本包包含 Kotaemon 底座之外的所有学习增强功能：
    - path_generator: 选题 → AI 学习路线生成
    - fsrs_review:    艾宾浩斯记忆曲线复习 (基于 FSRS v6)
    - quiz:           查漏补缺测验引擎
    - progress:       学习进度跟踪 + 掌握度模型
    - feynman:        费曼对话 + 苏格拉底引导
    - practice:       环境/实操辅助
    - exporter:       导出 Anki / Markdown / PDF
    - db:             学习相关数据模型 (复用 Kotaemon 的 SQLite engine)
    - llm:            LLM 调用封装 (复用 Kotaemon 的 LLM 配置)

设计原则：
    1. 本模块与 Kotaemon 底座解耦，便于阶段 5 迁移到独立 Next.js 前端
    2. 所有持久化复用 Kotaemon 的 KH_DATABASE (SQLite) 与 KH_FILESTORAGE_PATH
    3. LLM 调用复用 Kotaemon 已配置的模型，不重复造轮子
"""

import os as _os

# Kotaemon 底座实例化 cohere/voyage/mistral/google 等 LLM 时直接读 os.environ 校验 key，
# 本地未配置这些服务时注入占位值避免 import 崩溃 (实际不使用这些服务)
for _k in ("COHERE_API_KEY", "VOYAGE_API_KEY", "MISTRAL_API_KEY", "GOOGLE_API_KEY"):
    _os.environ.setdefault(_k, "placeholder-key-1234567890")

__version__ = "0.1.0"
