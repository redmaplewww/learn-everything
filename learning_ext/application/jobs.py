"""学习内容准备作业。"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from learning_ext.application.projects import _get_project
from learning_ext.db.models import KnowledgeNode, LearningProject, Task
from learning_ext.progress.study import sort_nodes_by_code

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"done", "blocked", "cancelled"}
_ACTIVE_JOBS: dict[int, threading.Event] = {}
_ACTIVE_JOBS_LOCK = threading.Lock()


@dataclass(frozen=True)
class ContentPreparation:
    job_id: int
    project_id: int
    generated_node_ids: list[int]
    failed_node_ids: list[int]
    pending_node_ids: list[int]
    status: str
    attempts: int = 1
    error: str | None = None
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_project_content(
    session: Session,
    project_id: int,
    *,
    user_id: str = "default",
    initial_count: int = 3,
) -> ContentPreparation:
    """同步准备首批内容，并把剩余节点交给可查询作业。"""
    project = _get_project(session, project_id, user_id)
    nodes = sort_nodes_by_code(
        list(session.exec(select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)).all())
    )
    node_ids = [node.id for node in nodes if node.id is not None]
    job = Task(
        project_id=project_id,
        title="学习内容准备",
        description=f"为项目 {project.title} 准备教学内容",
        task_type="content_preparation",
        status="doing",
        output="",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    sync_ids = node_ids[: max(0, initial_count)]
    pending_ids = node_ids[len(sync_ids):]
    generated, failed = _generate_nodes(
        sync_ids, project.topic, project.goal, session.get_bind()
    )
    if pending_ids:
        _write_job_state(session, job.id, "doing", generated, failed, pending_ids)
        _start_content_job(
            session.get_bind(), job.id, pending_ids, project.topic, project.goal
        )
        status = "doing"
    else:
        status = "done" if not failed else "blocked"
        _write_job_state(
            session,
            job.id,
            status,
            generated,
            failed,
            [],
            error="首批节点生成失败，可点击重试" if failed else None,
        )
    return ContentPreparation(
        job.id,
        project_id,
        generated,
        failed,
        pending_ids,
        status,
        attempts=1,
        error="首批节点生成失败，可点击重试" if failed else None,
    )


def get_content_preparation(session: Session, job_id: int) -> ContentPreparation:
    """读取内容准备作业的当前状态。"""
    job = session.get(Task, job_id)
    if job is None or job.task_type != "content_preparation":
        raise ValueError(f"内容准备作业 {job_id} 不存在")
    return _content_preparation_from_task(job)


def cancel_content_preparation(
    session: Session, project_id: int, job_id: int, *, user_id: str = "default"
) -> ContentPreparation:
    """请求取消内容准备；正在进行的单次 LLM 调用会在其超时或返回后停止后续节点。"""
    job = _get_content_job(session, project_id, job_id, user_id)
    if job.status in _TERMINAL_STATUSES:
        return _content_preparation_from_task(job)
    state = _read_state(job)
    state["cancel_requested"] = True
    state["error"] = "用户请求取消，等待当前节点结束"
    _write_job_state(
        session,
        job.id,
        "cancelling",
        state["generated_node_ids"],
        state["failed_node_ids"],
        state["pending_node_ids"],
        attempts=state["attempts"],
        error=state["error"],
        cancel_requested=True,
    )
    with _ACTIVE_JOBS_LOCK:
        event = _ACTIVE_JOBS.get(job_id)
    if event is not None:
        event.set()
    logger.info("内容准备作业 %s 收到取消请求", job_id)
    session.refresh(job)
    return _content_preparation_from_task(job)


def retry_content_preparation(
    session: Session, project_id: int, job_id: int, *, user_id: str = "default"
) -> ContentPreparation:
    """重新排队失败或取消后尚未完成的节点。"""
    job = _get_content_job(session, project_id, job_id, user_id)
    if job.status not in _TERMINAL_STATUSES:
        raise ValueError("只有已完成、受阻或已取消的内容准备作业才能重试")
    state = _read_state(job)
    retry_ids = list(dict.fromkeys(state["failed_node_ids"] + state["pending_node_ids"]))
    if not retry_ids:
        return _content_preparation_from_task(job)
    project = _get_project(session, project_id, user_id)
    attempts = int(state.get("attempts", 1)) + 1
    _write_job_state(
        session,
        job.id,
        "doing",
        state["generated_node_ids"],
        [],
        retry_ids,
        attempts=attempts,
        error=None,
        cancel_requested=False,
    )
    _start_content_job(session.get_bind(), job.id, retry_ids, project.topic, project.goal)
    session.refresh(job)
    logger.info("内容准备作业 %s 已重试，第 %s 次，节点数 %s", job_id, attempts, len(retry_ids))
    return _content_preparation_from_task(job)


def resume_content_preparation_jobs(session: Session) -> int:
    """服务启动时恢复上次进程中断的内容准备作业。"""
    resumed = 0
    jobs = session.exec(
        select(Task)
        .where(Task.task_type == "content_preparation")
        .where(Task.status.in_(["doing", "cancelling"]))
    ).all()
    for job in jobs:
        state = _read_state(job)
        if job.status == "cancelling" or state.get("cancel_requested"):
            _write_job_state(
                session,
                job.id,
                "cancelled",
                state["generated_node_ids"],
                state["failed_node_ids"],
                state["pending_node_ids"],
                attempts=state["attempts"],
                error="服务重启前任务已请求取消",
                cancel_requested=True,
            )
            continue
        if not state["pending_node_ids"]:
            _write_job_state(
                session,
                job.id,
                "done" if not state["failed_node_ids"] else "blocked",
                state["generated_node_ids"],
                state["failed_node_ids"],
                [],
                attempts=state["attempts"],
                error=state.get("error"),
            )
            continue
        project = session.get(LearningProject, job.project_id)
        if project is None:
            _write_job_state(
                session,
                job.id,
                "blocked",
                state["generated_node_ids"],
                state["failed_node_ids"],
                state["pending_node_ids"],
                attempts=state["attempts"],
                error="项目不存在，无法恢复内容准备",
            )
            continue
        _start_content_job(
            session.get_bind(),
            job.id,
            state["pending_node_ids"],
            project.topic,
            project.goal,
        )
        resumed += 1
        logger.warning("服务启动恢复内容准备作业 %s，剩余节点 %s", job.id, len(state["pending_node_ids"]))
    return resumed


def shutdown_content_preparation_jobs() -> None:
    """记录进程关闭，让未完成作业在下一次启动时从持久化状态恢复。"""
    with _ACTIVE_JOBS_LOCK:
        active_count = len(_ACTIVE_JOBS)
    if active_count:
        logger.warning("服务关闭时保留 %s 个内容准备作业，下一次启动将恢复", active_count)


def _generate_nodes(node_ids: list[int], topic: str, goal: str, bind) -> tuple[list[int], list[int]]:
    from learning_ext.progress.study import generate_node_summary_to_db

    generated, failed = [], []
    for node_id in node_ids:
        try:
            if generate_node_summary_to_db(
                node_id, topic, learning_goal=goal, engine=bind
            ):
                generated.append(node_id)
            else:
                failed.append(node_id)
        except Exception:
            logger.exception("内容准备节点 %s 生成异常", node_id)
            failed.append(node_id)
    return generated, failed


def _finish_content_job(bind, job_id, node_ids, topic, goal, cancel_event) -> None:
    try:
        for index, node_id in enumerate(node_ids):
            with Session(bind) as session:
                job = session.get(Task, job_id)
                if job is None:
                    logger.error("内容准备作业 %s 不存在，停止执行", job_id)
                    return
                state = _read_state(job)
                if cancel_event.is_set() or state.get("cancel_requested"):
                    _write_job_state(
                        session,
                        job_id,
                        "cancelled",
                        state["generated_node_ids"],
                        state["failed_node_ids"],
                        state["pending_node_ids"],
                        attempts=state["attempts"],
                        error="任务已取消，未处理节点保留待重试",
                        cancel_requested=True,
                    )
                    logger.info("内容准备作业 %s 已取消，剩余节点 %s", job_id, len(state["pending_node_ids"]))
                    return
            generated_now, failed_now = _generate_nodes([node_id], topic, goal, bind)
            with Session(bind) as session:
                job = session.get(Task, job_id)
                if job is None:
                    return
                state = _read_state(job)
                generated = list(dict.fromkeys(state["generated_node_ids"] + generated_now))
                failed = list(dict.fromkeys(state["failed_node_ids"] + failed_now))
                pending = [item for item in state["pending_node_ids"] if item != node_id]
                status = "doing" if pending else ("blocked" if failed else "done")
                _write_job_state(
                    session,
                    job_id,
                    status,
                    generated,
                    failed,
                    pending,
                    attempts=state["attempts"],
                    error="存在节点生成失败，可点击重试" if failed else None,
                )
                logger.info(
                    "内容准备作业 %s 进度 %s/%s，节点 %s %s",
                    job_id,
                    index + 1,
                    len(node_ids),
                    node_id,
                    "完成" if generated_now else "失败",
                )
    except Exception:
        logger.warning("内容准备作业 %s 写回状态失败", job_id, exc_info=True)
        try:
            with Session(bind) as session:
                job = session.get(Task, job_id)
                if job is not None:
                    state = _read_state(job)
                    _write_job_state(
                        session,
                        job_id,
                        "blocked",
                        state["generated_node_ids"],
                        state["failed_node_ids"],
                        state["pending_node_ids"],
                        attempts=state["attempts"],
                        error="后台任务异常中断，请查看日志后重试",
                    )
        except Exception:
            logger.exception("内容准备作业 %s 异常状态写回失败", job_id)
    finally:
        with _ACTIVE_JOBS_LOCK:
            _ACTIVE_JOBS.pop(job_id, None)


def _start_content_job(bind, job_id: int, node_ids: list[int], topic: str, goal: str) -> None:
    with _ACTIVE_JOBS_LOCK:
        if job_id in _ACTIVE_JOBS:
            return
        cancel_event = threading.Event()
        _ACTIVE_JOBS[job_id] = cancel_event
    thread = threading.Thread(
        target=_finish_content_job,
        args=(bind, job_id, list(node_ids), topic, goal, cancel_event),
        daemon=True,
        name=f"le-content-job-{job_id}",
    )
    thread.start()


def _get_content_job(session: Session, project_id: int, job_id: int, user_id: str) -> Task:
    project = _get_project(session, project_id, user_id)
    job = session.get(Task, job_id)
    if job is None or job.project_id != project.id or job.task_type != "content_preparation":
        raise ValueError(f"内容准备作业 {job_id} 不属于项目 {project_id}")
    return job


def _read_state(job: Task) -> dict[str, Any]:
    try:
        raw = json.loads(job.output or "{}")
    except (TypeError, json.JSONDecodeError):
        raw = {}
    return {
        "generated_node_ids": list(raw.get("generated_node_ids", [])),
        "failed_node_ids": list(raw.get("failed_node_ids", [])),
        "pending_node_ids": list(raw.get("pending_node_ids", [])),
        "attempts": int(raw.get("attempts", 1)),
        "error": raw.get("error"),
        "cancel_requested": bool(raw.get("cancel_requested", False)),
        "updated_at": raw.get("updated_at"),
    }


def _content_preparation_from_task(job: Task) -> ContentPreparation:
    state = _read_state(job)
    return ContentPreparation(
        job_id=job.id,
        project_id=job.project_id,
        generated_node_ids=state["generated_node_ids"],
        failed_node_ids=state["failed_node_ids"],
        pending_node_ids=state["pending_node_ids"],
        status=job.status,
        attempts=state["attempts"],
        error=state["error"],
        cancel_requested=state["cancel_requested"],
    )


def _write_job_state(
    session,
    job_id,
    status,
    generated,
    failed,
    pending,
    *,
    attempts: int = 1,
    error: str | None = None,
    cancel_requested: bool = False,
) -> None:
    job = session.get(Task, job_id)
    if job is None:
        return
    job.status = status
    job.output = json.dumps(
        {
            "generated_node_ids": generated,
            "failed_node_ids": failed,
            "pending_node_ids": pending,
            "attempts": attempts,
            "error": error,
            "cancel_requested": cancel_requested,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    session.add(job)
    session.commit()
