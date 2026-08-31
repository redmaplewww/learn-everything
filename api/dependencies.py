"""API 共享依赖。"""

from collections.abc import Generator

from sqlmodel import Session


def get_session() -> Generator[Session, None, None]:
    from ktem.db.engine import engine

    with Session(engine) as session:
        yield session


def get_rag_gateway():
    from learning_ext.adapters.kotaemon_rag import KotaemonRagAdapter

    return KotaemonRagAdapter()


def get_model_configuration_service():
    from learning_ext.application.configuration import ModelConfigurationService

    return ModelConfigurationService()
