"""LLM 与 RAG 模型配置接口。"""

from typing import Literal

from fastapi import APIRouter, Depends

from api.dependencies import get_model_configuration_service
from api.schemas.configuration import (
    ModelConfigurationResponse,
    ModelConnectivityResponse,
    ModelEndpointWriteRequest,
    ModelProfileCreateRequest,
)
from learning_ext.application.configuration import (
    ModelConfigurationService,
    ModelEndpointInput,
)

ConfigurationKind = Literal["llm", "rag"]
router = APIRouter(prefix="/model-configuration", tags=["configuration"])


@router.get("", response_model=ModelConfigurationResponse)
def read_model_configuration(
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.get_status().to_dict()


@router.post("/{kind}/profiles", response_model=ModelConfigurationResponse)
def create_model_profile(
    kind: ConfigurationKind,
    payload: ModelProfileCreateRequest,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.create_profile(kind, payload.name).to_dict()


@router.put("/{kind}/profiles/{profile_id}", response_model=ModelConfigurationResponse)
def save_model_profile(
    kind: ConfigurationKind,
    profile_id: str,
    payload: ModelEndpointWriteRequest,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.save(kind, profile_id, _to_input(payload)).to_dict()


@router.post(
    "/{kind}/profiles/{profile_id}/activate", response_model=ModelConfigurationResponse
)
def activate_model_profile(
    kind: ConfigurationKind,
    profile_id: str,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.activate(kind, profile_id).to_dict()


@router.delete(
    "/{kind}/profiles/{profile_id}", response_model=ModelConfigurationResponse
)
def delete_model_profile(
    kind: ConfigurationKind,
    profile_id: str,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.delete_profile(kind, profile_id).to_dict()


@router.post("/{kind}/test", response_model=ModelConnectivityResponse)
def test_model_profile(
    kind: ConfigurationKind,
    payload: ModelEndpointWriteRequest,
    profile_id: str | None = None,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.test(kind, _to_input(payload), profile_id).to_dict()


def _to_input(payload: ModelEndpointWriteRequest) -> ModelEndpointInput:
    return ModelEndpointInput(**payload.model_dump())
