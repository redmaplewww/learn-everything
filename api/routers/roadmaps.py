"""路线预览与调整接口。"""

from fastapi import APIRouter

from api.schemas.roadmaps import (
    RefineRoadmapRequest,
    RefineRoadmapResponse,
    RoadmapPreviewRequest,
    RoadmapPreviewResponse,
)
from learning_ext.application import generate_roadmap_preview, refine_roadmap_preview

router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


@router.post("/preview", response_model=RoadmapPreviewResponse)
def preview_roadmap(payload: RoadmapPreviewRequest):
    return generate_roadmap_preview(**payload.model_dump()).to_dict()


@router.post("/refine", response_model=RefineRoadmapResponse)
def refine_roadmap(payload: RefineRoadmapRequest):
    return {"roadmap": refine_roadmap_preview(**payload.model_dump())}
