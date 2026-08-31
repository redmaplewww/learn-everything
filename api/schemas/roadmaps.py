"""路线生成与调整 HTTP Schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RoadmapPreviewRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    background: str = Field(default="", max_length=4_000)
    goal: str = Field(default="", max_length=4_000)
    weekly_hours: float = Field(gt=0, le=168)


class RoadmapPreviewResponse(BaseModel):
    roadmap: dict[str, Any]
    audit: dict[str, Any]


class RefineRoadmapRequest(BaseModel):
    roadmap: dict[str, Any]
    instruction: str = Field(min_length=1, max_length=4_000)


class RefineRoadmapResponse(BaseModel):
    roadmap: dict[str, Any]
