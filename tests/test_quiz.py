"""测验 service 测试。"""

from __future__ import annotations

import pytest
from sqlmodel import select

from learning_ext.db.models import KnowledgeNode, QuizAttempt, QuizQuestion
from learning_ext.quiz import generate_quiz, get_weak_nodes, grade_answer


class TestGenerateQuiz:
    def test_generates_quiz_with_questions(self, session, sample_project, mock_llm):
        node = session.exec(select(KnowledgeNode)).first()
        quiz = generate_quiz(
            session,
            "default",
            [node.id],
            project_id=sample_project.id,
            count=1,
            qtype="choice",
        )
        assert quiz.id is not None
        assert quiz.user_id == "default"
        questions = session.exec(
            select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
        ).all()
        assert len(questions) >= 1
        assert all(question.node_id == node.id for question in questions)

    def test_multi_node_questions_keep_explicit_or_compatible_node_ownership(
        self, session, sample_project, monkeypatch
    ):
        import learning_ext.quiz.service as quiz_service

        nodes = session.exec(
            select(KnowledgeNode)
            .where(KnowledgeNode.project_id == sample_project.id)
            .order_by(KnowledgeNode.id)
        ).all()[:2]
        monkeypatch.setattr(
            quiz_service,
            "chat_json",
            lambda *_args, **_kwargs: [
                {"stem": "第二节点题", "answer": "A", "node_id": nodes[1].id},
                {"stem": "兼容题", "answer": "B"},
                {"stem": "无效 ID", "answer": "C", "node_id": 99999},
            ],
        )

        quiz = generate_quiz(
            session,
            "default",
            [node.id for node in nodes],
            project_id=sample_project.id,
            count=3,
        )
        questions = session.exec(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.id)
        ).all()

        assert [question.node_id for question in questions] == [nodes[1].id, nodes[1].id, nodes[0].id]

    def test_empty_node_ids_raises(self, session):
        with pytest.raises(ValueError, match="未找到"):
            generate_quiz(session, "default", [])

    def test_nonexistent_node_ids_raises(self, session):
        with pytest.raises(ValueError, match="未找到"):
            generate_quiz(session, "default", [99999])


class TestGradeAnswer:
    def test_grade_records_attempt(self, session, sample_project, mock_llm):
        node = session.exec(select(KnowledgeNode)).first()
        quiz = generate_quiz(
            session,
            "default",
            [node.id],
            project_id=sample_project.id,
            count=1,
        )
        q = session.exec(
            select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
        ).first()
        attempt = grade_answer(session, q.id, "我的答案", "default")
        assert attempt.user_answer == "我的答案"
        assert attempt.is_correct is True  # mock 返回 correct
        assert attempt.feedback
        session.expire_all()
        assert session.get(KnowledgeNode, node.id).mastery >= 0.4

    def test_grade_nonexistent_question(self, session):
        with pytest.raises(ValueError, match="not found|不存在"):
            grade_answer(session, 99999, "x", "default")


class TestGetWeakNodes:
    def test_returns_low_mastery_nodes(self, session, sample_project):
        # 把一个节点 mastery 设低
        node = session.exec(select(KnowledgeNode)).first()
        node.mastery = 0.1
        session.add(node)
        session.commit()
        weak = get_weak_nodes(session, sample_project.id, threshold=0.5)
        assert any(n.id == node.id for n in weak)

    def test_excludes_mastered(self, session, sample_project):
        node = session.exec(select(KnowledgeNode)).first()
        node.mastery = 0.1
        node.status = "mastered"
        session.add(node)
        session.commit()
        weak = get_weak_nodes(session, sample_project.id, threshold=0.5)
        assert not any(n.id == node.id for n in weak)

    def test_ordered_by_mastery_asc(self, session, sample_project):
        nodes = session.exec(select(KnowledgeNode)).all()
        nodes[0].mastery = 0.5
        nodes[1].mastery = 0.1
        nodes[2].mastery = 0.3
        session.add_all(nodes)
        session.commit()
        weak = get_weak_nodes(session, sample_project.id, threshold=0.6)
        masteries = [n.mastery for n in weak]
        assert masteries == sorted(masteries)
