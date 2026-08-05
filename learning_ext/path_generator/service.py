"""路线生成 Agent。

输入：选题 + 背景 + 目标 + 可用时间
输出：学习路线 JSON (含阶段、知识 DAG 节点、依赖边)
持久化：写入 LearningProject + KnowledgeNode + KnowledgeEdge
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from sqlmodel import select

from learning_ext.db.models import (
    KnowledgeEdge,
    KnowledgeNode,
    LearningProject,
)
from learning_ext.llm import chat_json
from learning_ext.path_generator.prompts import (
    REFINE_SYSTEM,
    REFINE_USER_TEMPLATE,
    SYSTEM,
    USER_TEMPLATE,
)
from learning_ext.progress.study import course_code_sort_key
from learning_ext.project_ops import clear_project_learning_data

ROADMAP_BUNDLE_KIND = "learn-everything.roadmap"
ROADMAP_BUNDLE_SCHEMA_VERSION = 1
_REPO_ROOT = Path(__file__).resolve().parents[2]
BUILTIN_ROADMAPS_DIR = _REPO_ROOT / "docs" / "learning_routes"
BUILTIN_ROADMAPS_MANIFEST = BUILTIN_ROADMAPS_DIR / "manifest.json"


def generate_roadmap(
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    *,
    model_name: Optional[str] = None,
) -> dict:
    """调用 LLM 生成学习路线 (纯函数，不落库)。

    Returns:
        路线 dict，结构见 prompts.SYSTEM
    """
    prompt = USER_TEMPLATE.format(
        topic=topic,
        background=background or "无特殊背景，默认初学者",
        goal=goal or "掌握该主题的核心知识并能应用",
        weekly_hours=weekly_hours,
    )
    return chat_json(prompt, system=SYSTEM, model_name=model_name)


def refine_roadmap(
    current_roadmap: dict,
    instruction: str,
    *,
    model_name: Optional[str] = None,
) -> dict:
    """根据用户意见调整已有路线。"""
    prompt = REFINE_USER_TEMPLATE.format(
        current_roadmap=json.dumps(current_roadmap, ensure_ascii=False, indent=2),
        instruction=instruction,
    )
    return chat_json(prompt, system=REFINE_SYSTEM, model_name=model_name)


def audit_and_rewrite_roadmap(
    roadmap: dict,
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    *,
    model_name: Optional[str] = None,
) -> dict:
    """Audit a generated roadmap and return an improved full roadmap."""
    prompt = f"""请审计并修订下面这条学习路线。目标不是润色，而是确保路线完整、系统、可执行。

【选题】{topic}
【学习者背景】{background or "无特殊背景，默认初学者"}
【学习目标】{goal or "掌握该主题的核心知识并能应用"}
【每周可投入时间】{weekly_hours} 小时

【初版路线 JSON】
{json.dumps(roadmap, ensure_ascii=False, indent=2)}

请先在脑中审计这条路线是否存在：
- 核心前置知识缺失
- 关键分支/实践环节缺失
- 节点过粗，需要拆成多个小节
- 节点过细或重复
- 难度跃迁太大
- 依赖关系不合理
- 与学习目标不匹配

然后直接输出一个 JSON 对象，格式如下：
{{
  "audit": {{
    "score": 0-100,
    "verdict": "可以使用|需要小修|需要重构",
    "problems": ["问题1", "问题2"],
    "changes": ["改动1", "改动2"]
  }},
  "roadmap": {{
    "summary": "对修订后学习路线的简短总体说明",
    "stages": [
      {{"name": "阶段名", "stage": "base|strengthen|sprint", "goal": "本阶段目标"}}
    ],
    "nodes": [
      {{
        "code": "1.1",
        "title": "知识点标题",
        "description": "这个知识点要学什么、学到什么程度",
        "stage": "base",
        "est_hours": 2.0,
        "difficulty": 3,
        "prerequisites": []
      }}
    ]
  }}
}}

路线要求：
- 节点数允许扩展到 18-40 个；复杂主题宁可拆细，不要硬塞进 12-25 个节点
- 每个节点应该是 1-4 小时可学完的粒度
- 必须包含必要实践/项目/自测节点
- prerequisites 只能引用存在的 code
- 只返回 JSON，不要 markdown 代码块。"""
    result = chat_json(
        prompt,
        system="你是严苛的课程路线审计员，会自动补齐遗漏、拆分过粗节点、修正依赖关系。",
        model_name=model_name,
    )
    if not isinstance(result, dict):
        raise ValueError("路线审计未返回 JSON 对象")
    audited = result.get("roadmap") if isinstance(result.get("roadmap"), dict) else None
    if audited is None and isinstance(result.get("nodes"), list):
        audited = result
    if not audited:
        raise ValueError("路线审计结果缺少 roadmap")
    audited["_audit"] = result.get("audit", {})
    return audited


def audit_existing_roadmap(
    roadmap: dict,
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    *,
    model_name: Optional[str] = None,
) -> tuple[dict, dict]:
    """Return (audit, improved_roadmap) for an existing project roadmap."""
    improved = audit_and_rewrite_roadmap(
        roadmap=roadmap,
        topic=topic,
        background=background,
        goal=goal,
        weekly_hours=weekly_hours,
        model_name=model_name,
    )
    audit = improved.pop("_audit", {})
    return audit, improved


def save_roadmap(
    session: Session,
    user_id: str,
    topic: str,
    background: str,
    goal: str,
    weekly_hours: float,
    roadmap: dict,
    title: Optional[str] = None,
) -> LearningProject:
    """把路线 JSON 落库为 Project + Nodes + Edges。

    Returns:
        创建的 LearningProject
    """
    project = LearningProject(
        user_id=user_id,
        title=title or roadmap.get("summary", topic)[:80] or topic,
        topic=topic,
        background=background,
        goal=goal,
        weekly_hours=weekly_hours,
        roadmap_json=json.dumps(roadmap, ensure_ascii=False),
        status="active",
    )
    session.add(project)
    session.flush()  # 拿到 project.id

    # code -> node_id 映射，用于建边
    code_to_id: dict[str, int] = {}

    for node_data in roadmap.get("nodes", []):
        node = KnowledgeNode(
            project_id=project.id,
            code=node_data["code"],
            title=node_data["title"],
            description=node_data.get("description", ""),
            stage=node_data.get("stage", "base"),
            est_hours=float(node_data.get("est_hours", 2.0)),
            difficulty=int(node_data.get("difficulty", 3)),
            mastery=0.0,
            status="pending",
        )
        session.add(node)
        session.flush()
        code_to_id[node.code] = node.id

    # 建依赖边：node 的 prerequisites 中的 code 是前置
    for node_data in roadmap.get("nodes", []):
        source_code = node_data["code"]
        source_id = code_to_id.get(source_code)
        if source_id is None:
            continue
        for prereq_code in node_data.get("prerequisites", []):
            target_id = code_to_id.get(prereq_code)
            if target_id is None or target_id == source_id:
                continue
            edge = KnowledgeEdge(
                project_id=project.id,
                source_id=source_id,
                target_id=target_id,
                relation="prerequisite",
            )
            session.add(edge)

    session.commit()
    return project


def export_roadmap_bundle(session: Session, project_id: int) -> str:
    """Export a formatted, self-contained learning route JSON bundle."""
    project = session.get(LearningProject, int(project_id))
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    roadmap = load_roadmap(session, project.id)
    payload = {
        "kind": ROADMAP_BUNDLE_KIND,
        "schema_version": ROADMAP_BUNDLE_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "title": project.title,
            "topic": project.topic,
            "background": project.background,
            "goal": project.goal,
            "weekly_hours": project.weekly_hours,
            "status": project.status,
        },
        "roadmap": roadmap,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def import_roadmap_bundle(
    session: Session, payload: str | dict, *, user_id: str = "default"
) -> LearningProject:
    """Import a route bundle or raw roadmap JSON as a new learning project."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"学习路线 JSON 解析失败: {e}") from e
    elif isinstance(payload, dict):
        data = payload
    else:
        raise ValueError("学习路线导入内容必须是 JSON 字符串或对象")

    if data.get("kind") == ROADMAP_BUNDLE_KIND:
        project_data = data.get("project") or {}
        roadmap = data.get("roadmap") or {}
    else:
        project_data = {}
        roadmap = data

    _validate_roadmap_for_exchange(roadmap)
    topic = str(project_data.get("topic") or roadmap.get("summary") or "导入的学习路线")
    return save_roadmap(
        session=session,
        user_id=user_id,
        topic=topic,
        background=str(project_data.get("background") or ""),
        goal=str(project_data.get("goal") or ""),
        weekly_hours=float(project_data.get("weekly_hours") or 10.0),
        roadmap=roadmap,
        title=str(project_data.get("title") or roadmap.get("summary") or topic),
    )


def list_builtin_roadmaps() -> list[dict]:
    """List learning route bundles shipped with the application."""
    if not BUILTIN_ROADMAPS_MANIFEST.exists():
        return []
    try:
        manifest = json.loads(BUILTIN_ROADMAPS_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"内置学习路线清单解析失败: {e}") from e

    routes = []
    for item in manifest.get("routes", []) or []:
        if not isinstance(item, dict):
            continue
        file_value = str(item.get("file") or "").strip()
        if not file_value:
            continue
        route_id = str(item.get("id") or Path(file_value).stem).strip()
        if not route_id:
            continue
        route = dict(item)
        route["id"] = route_id
        route["file"] = file_value
        routes.append(route)
    return routes


def load_builtin_roadmap_bundle(route_id: str) -> dict:
    """Load a bundled learning route by manifest id."""
    requested = str(route_id or "").strip()
    if not requested:
        raise ValueError("请选择内置学习路线")

    route = next((r for r in list_builtin_roadmaps() if r["id"] == requested), None)
    if route is None:
        raise ValueError(f"内置学习路线不存在: {requested}")

    route_path = (_REPO_ROOT / route["file"]).resolve()
    if BUILTIN_ROADMAPS_DIR.resolve() not in route_path.parents:
        raise ValueError(f"内置学习路线路径不安全: {route['file']}")
    if not route_path.exists():
        raise ValueError(f"内置学习路线文件不存在: {route['file']}")

    try:
        data = json.loads(route_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"内置学习路线 JSON 解析失败: {e}") from e

    if data.get("kind") == ROADMAP_BUNDLE_KIND:
        _validate_roadmap_for_exchange(data.get("roadmap") or {})
    else:
        _validate_roadmap_for_exchange(data)
    return data


def import_builtin_roadmap(
    session: Session, route_id: str, *, user_id: str = "default"
) -> LearningProject:
    """Import a shipped learning route as a new project."""
    return import_roadmap_bundle(
        session=session,
        payload=load_builtin_roadmap_bundle(route_id),
        user_id=user_id,
    )


def replace_project_roadmap(
    session: Session,
    project_id: int,
    roadmap: dict,
) -> LearningProject:
    """Replace a project's nodes/edges with an audited roadmap."""
    project = session.get(LearningProject, int(project_id))
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    clear_project_learning_data(session, project.id, commit=False)
    session.flush()

    project.title = roadmap.get("summary", project.title)[:80] or project.title
    project.roadmap_json = json.dumps(roadmap, ensure_ascii=False)
    session.add(project)
    session.flush()

    code_to_id: dict[str, int] = {}
    for node_data in roadmap.get("nodes", []):
        node = KnowledgeNode(
            project_id=project.id,
            code=node_data["code"],
            title=node_data["title"],
            description=node_data.get("description", ""),
            stage=node_data.get("stage", "base"),
            est_hours=float(node_data.get("est_hours", 2.0)),
            difficulty=int(node_data.get("difficulty", 3)),
            mastery=0.0,
            status="pending",
        )
        session.add(node)
        session.flush()
        code_to_id[node.code] = node.id

    for node_data in roadmap.get("nodes", []):
        source_id = code_to_id.get(node_data["code"])
        if source_id is None:
            continue
        for prereq_code in node_data.get("prerequisites", []):
            target_id = code_to_id.get(prereq_code)
            if target_id is None or target_id == source_id:
                continue
            session.add(
                KnowledgeEdge(
                    project_id=project.id,
                    source_id=source_id,
                    target_id=target_id,
                    relation="prerequisite",
                )
            )

    session.commit()
    session.refresh(project)
    return project


def load_roadmap(session: Session, project_id: int) -> dict:
    """从库重建路线 JSON (含节点最新状态)。"""
    project = session.get(LearningProject, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    edges = session.exec(
        select(KnowledgeEdge).where(KnowledgeEdge.project_id == project_id)
    ).all()

    # 构造 prerequisites
    prereq_map: dict[str, list[str]] = {}
    code_by_id = {n.id: n.code for n in nodes}
    for e in edges:
        src_code = code_by_id.get(e.source_id, "")
        tgt_code = code_by_id.get(e.target_id, "")
        prereq_map.setdefault(src_code, []).append(tgt_code)

    return {
        "summary": project.title,
        "stages": _distinct_stages(nodes),
        "nodes": [
            {
                "code": n.code,
                "title": n.title,
                "description": n.description,
                "stage": n.stage,
                "est_hours": n.est_hours,
                "difficulty": n.difficulty,
                "prerequisites": prereq_map.get(n.code, []),
                "mastery": n.mastery,
                "status": n.status,
            }
            for n in sorted(nodes, key=lambda x: course_code_sort_key(x.code))
        ],
    }


def _distinct_stages(nodes):
    seen = []
    for n in nodes:
        if n.stage not in [s["stage"] for s in seen]:
            seen.append({"name": n.stage, "stage": n.stage, "goal": ""})
    return seen


def _validate_roadmap_for_exchange(roadmap: dict) -> None:
    if not isinstance(roadmap, dict):
        raise ValueError("学习路线必须是 JSON 对象")
    nodes = roadmap.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("学习路线缺少 nodes")
    codes = set()
    for idx, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            raise ValueError(f"第 {idx} 个节点不是对象")
        for key in ("code", "title"):
            if not str(node.get(key) or "").strip():
                raise ValueError(f"第 {idx} 个节点缺少 {key}")
        code = str(node["code"])
        if code in codes:
            raise ValueError(f"节点编号重复: {code}")
        codes.add(code)
    for node in nodes:
        for prereq in node.get("prerequisites", []) or []:
            if prereq not in codes:
                raise ValueError(f"节点 {node.get('code')} 引用了不存在的前置节点 {prereq}")
