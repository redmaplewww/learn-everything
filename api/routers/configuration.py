"""本地单用户必要模型配置接口。"""

from fastapi import APIRouter, Depends

from api.dependencies import get_model_configuration_service
from api.schemas.configuration import (
    ModelConfigurationResponse,
    ModelConfigurationWriteRequest,
    ModelConnectivityResponse,
)
from learning_ext.application.configuration import (
    ModelConfigurationInput,
    ModelConfigurationService,
)

router = APIRouter(prefix="/model-configuration", tags=["configuration"])


@router.get("", response_model=ModelConfigurationResponse)
def read_model_configuration(
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.get_status().to_dict()


@router.put("", response_model=ModelConfigurationResponse)
def save_model_configuration(
    payload: ModelConfigurationWriteRequest,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.save(_to_input(payload)).to_dict()


@router.post("/test", response_model=ModelConnectivityResponse)
def test_model_configuration(
    payload: ModelConfigurationWriteRequest,
    service: ModelConfigurationService = Depends(get_model_configuration_service),
):
    return service.test(_to_input(payload)).to_dict()


def _to_input(payload: ModelConfigurationWriteRequest) -> ModelConfigurationInput:
    return ModelConfigurationInput(**payload.model_dump())
