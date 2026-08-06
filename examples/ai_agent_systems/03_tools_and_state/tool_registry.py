from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


ToolFn = Callable[[dict], dict]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    required: tuple[str, ...]
    fn: ToolFn


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具已存在：{spec.name}")
        self._tools[spec.name] = spec

    def call(self, name: str, args: dict) -> dict:
        spec = self._tools.get(name)
        if spec is None:
            return {"ok": False, "error": f"未知工具：{name}"}
        missing = [key for key in spec.required if key not in args]
        if missing:
            return {"ok": False, "error": f"缺少参数：{', '.join(missing)}"}
        try:
            return {"ok": True, "result": spec.fn(args)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="calculator",
            description="计算两个数字的和",
            required=("a", "b"),
            fn=lambda args: {"sum": float(args["a"]) + float(args["b"])},
        )
    )
    registry.register(
        ToolSpec(
            name="keyword_search",
            description="在小型资料库里搜索关键词",
            required=("query",),
            fn=lambda args: {"matches": [f"包含 {args['query']} 的资料片段"]},
        )
    )
    return registry
