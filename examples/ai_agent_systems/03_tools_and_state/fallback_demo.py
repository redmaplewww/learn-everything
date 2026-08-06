from __future__ import annotations

from tool_registry import ToolRegistry, ToolSpec


def primary_search(_: dict) -> dict:
    raise TimeoutError("主搜索服务超时")


def backup_search(args: dict) -> dict:
    return {"source": "backup", "matches": [f"备用结果：{args['query']}"]}


def search_with_fallback(query: str) -> dict:
    registry = ToolRegistry()
    registry.register(
        ToolSpec("primary_search", "主搜索工具", ("query",), primary_search)
    )
    registry.register(
        ToolSpec("backup_search", "备用搜索工具", ("query",), backup_search)
    )

    first = registry.call("primary_search", {"query": query})
    if first["ok"]:
        return first["result"]
    second = registry.call("backup_search", {"query": query})
    return {
        "used_fallback": True,
        "primary_error": first["error"],
        "result": second["result"] if second["ok"] else second["error"],
    }


if __name__ == "__main__":
    print(search_with_fallback("Agent 工具失败怎么办"))
