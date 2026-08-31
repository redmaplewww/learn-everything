"""查漏补缺测验引擎。

流程：
    1. 根据掌握度/薄弱点选题范围 (weak nodes 优先)
    2. AI 出题 (选择/填空/简答/实操)
    3. 用户作答 → AI 批改 → 更新掌握度
"""

from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlmodel import select

from learning_ext.db.models import (
    KnowledgeNode,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from learning_ext.llm import chat_json
from learning_ext.progress.service import update_mastery

SYSTEM = """你是一位严谨的命题专家。根据知识点信息出测验题。
返回 JSON 数组，每题格式：
{
  "qtype": "choice|fill|short|practice",
  "stem": "题干",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],  // 仅 choice 有
  "answer": "标准答案 (choice 填字母如 'B'，fill/short 填文本，practice 填参考步骤)",
  "explanation": "解析说明",
  "difficulty": 1-5,
  "node_id": 知识点 ID
}
规则：
- choice 必须有 4 个选项，answer 填对应字母
- fill 留空 options，answer 填标准答案
- short 留空 options，answer 填要点式参考答案
- practice 留空 options，answer 填参考操作步骤
- node_id 必须填写本题对应的知识点 ID，只能使用输入知识点列表中的 ID
- 只返回 JSON 数组，不要额外说明"""

GRADE_SYSTEM = """你是阅卷老师。判断用户答案是否正确。
返回 JSON：
{
  "is_correct": true|false,
  "feedback": "点评 (指出对错原因，2-3 句)"
}
- choice：完全匹配字母即正确
- fill：语义等价即正确，允许表述差异
- short：按要点给分，关键要点覆盖 70% 算正确
- practice：按步骤合理性判断
只返回 JSON。"""


def generate_quiz(
    session: Session,
    user_id: str,
    node_ids: List[int],
    *,
    project_id: Optional[int] = None,
    count: int = 5,
    qtype: str = "mixed",
    model_name: Optional[str] = None,
) -> Quiz:
    """AI 出题生成测验。

    Args:
        node_ids: 出题范围的知识点 id
        count: 题目数量
        qtype: choice|fill|short|practice|mixed
    """
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.id.in_(node_ids))
    ).all()
    if not nodes:
        raise ValueError("未找到指定知识点")

    nodes_text = "\n".join(
        f"- [ID={n.id}, {n.code}] {n.title} (难度{n.difficulty}): {n.description}" for n in nodes
    )
    allowed_node_ids = {node.id for node in nodes}
    if project_id is not None and any(node.project_id != project_id for node in nodes):
        raise ValueError("知识点不属于指定项目")
    prompt = f"""请为以下知识点出 {count} 道测验题。
题型偏好：{qtype}

【知识点】
{nodes_text}

返回 {count} 题的 JSON 数组。"""

    result = chat_json(prompt, system=SYSTEM, model_name=model_name)
    questions = result if isinstance(result, list) else result.get("questions", [])

    quiz = Quiz(
        project_id=project_id,
        user_id=user_id,
        quiz_type=qtype,
        scope_node_ids=",".join(str(i) for i in node_ids),
        title=f"测验 ({len(questions)}题)",
    )
    session.add(quiz)
    session.flush()

    for index, q in enumerate(questions):
        requested_node_id = q.get("node_id")
        try:
            node_id = int(requested_node_id)
        except (TypeError, ValueError):
            node_id = None
        if node_id not in allowed_node_ids:
            node_id = nodes[index % len(nodes)].id
        qq = QuizQuestion(
            quiz_id=quiz.id,
            node_id=node_id,
            qtype=q.get("qtype", "short"),
            stem=q.get("stem", ""),
            options=json.dumps(q.get("options", []), ensure_ascii=False),
            answer=q.get("answer", ""),
            explanation=q.get("explanation", ""),
            difficulty=int(q.get("difficulty", 3)),
        )
        session.add(qq)

    session.commit()
    return quiz


def grade_answer(
    session: Session,
    question_id: int,
    user_answer: str,
    user_id: str = "default",
    *,
    model_name: Optional[str] = None,
) -> QuizAttempt:
    """AI 批改单题答案，并回写掌握度。"""
    q = session.get(QuizQuestion, question_id)
    if q is None:
        raise ValueError(f"Question {question_id} not found")

    prompt = f"""【题型】{q.qtype}
【题目】{q.stem}
【标准答案】{q.answer}
【用户答案】{user_answer}

请判断对错。"""
    result = chat_json(prompt, system=GRADE_SYSTEM, model_name=model_name)
    is_correct = bool(result.get("is_correct", False))
    feedback = result.get("feedback", "")

    attempt = QuizAttempt(
        question_id=question_id,
        user_id=user_id,
        user_answer=user_answer,
        is_correct=is_correct,
        feedback=feedback,
    )
    session.add(attempt)

    # 回写掌握度
    if q.node_id:
        update_mastery(session, q.node_id, correct=is_correct)

    session.commit()
    return attempt


def get_weak_nodes(
    session: Session,
    project_id: int,
    *,
    threshold: float = 0.5,
    limit: int = 10,
) -> List[KnowledgeNode]:
    """获取薄弱知识点 (掌握度低于阈值)，测验/复习优先针对这些。"""
    stmt = (
        select(KnowledgeNode)
        .where(KnowledgeNode.project_id == project_id)
        .where(KnowledgeNode.status != "mastered")
        .where(KnowledgeNode.mastery < threshold)
        .order_by(KnowledgeNode.mastery.asc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())
