# AI Agent Systems Learning Source

这套源码是 `docs/learning_routes/ai_agent_systems_plain_language_guide.docx` 的配套练习代码。

它不是一个生产级 Agent 框架，而是一组可以直接阅读、运行、改造的小例子。目标是把学习路线里的核心概念跑起来：Chatbot 与 Agent 的区别、LLM/API 调用、工具注册、状态管理、失败回退、RAG、证据链、安全批准门控，以及最终的 evidence-first research agent。

## 怎么运行

在仓库根目录执行：

```powershell
kotaemon\.venv\Scripts\python.exe examples\ai_agent_systems\06_final_research_agent\run_demo.py
```

运行测试：

```powershell
kotaemon\.venv\Scripts\python.exe -m pytest tests\test_ai_agent_systems_examples.py
```

## 目录对应关系

| 目录 | 对应路线 | 你会看到什么 |
|---|---|---|
| `01_agent_vs_chatbot` | 1.1、1.3 | 普通 Chatbot 与最小 Agent 循环的区别 |
| `02_llm_api_basics` | 1.2 | 一个可替换成真实 API 的 LLM 客户端接口 |
| `03_tools_and_state` | 2.2、2.3、2.9 | 工具注册、状态、失败回退 |
| `04_rag_memory_evidence` | 2.7、2.8、2.10、2.11 | 最小 RAG、记忆和证据记录 |
| `05_mcp_safe_tools` | 2.4、3.5 | 一个简化版 MCP-like 安全工具服务 |
| `06_final_research_agent` | 3.3 到 3.9 | 证据优先 research agent 的端到端演示 |

## 学习建议

1. 先运行 `01_agent_vs_chatbot/simple_agent.py`，看 Agent 为什么不只是“回答文本”。
2. 再看 `03_tools_and_state/tool_registry.py`，理解工具为什么要有 schema 和错误边界。
3. 然后看 `04_rag_memory_evidence/mini_rag.py` 和 `evidence_log.py`，理解“先找证据再回答”。
4. 最后运行 `06_final_research_agent/run_demo.py`，把前面的能力串成一个小闭环。

所有示例都刻意保持短小、确定性和可测试，方便你逐节改造。
