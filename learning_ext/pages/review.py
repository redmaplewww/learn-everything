"""复习 Tab 骨架 - 阶段 2 填充。

功能：每日复习队列、4 档评分、AI 从节点生成卡片。
"""

from __future__ import annotations

import logging

import gradio as gr
from ktem.app import BasePage
from ktem.db.engine import engine
from sqlmodel import Session

from learning_ext.fsrs_review import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    get_review_stats,
)
from learning_ext.application import get_due_cards, review_fsrs_card

logger = logging.getLogger(__name__)


class ReviewPage(BasePage):
    """FSRS 间隔重复复习页面 (阶段 2 填充完整交互)"""

    def __init__(self, app):
        super().__init__(app)
        self.current_card_id = gr.State(None)

    def on_building_ui(self):
        gr.Markdown(
            "# 🔄 间隔复习\n基于 FSRS v6 算法的艾宾浩斯记忆曲线复习。AI 从你学过的知识点提炼卡片，到期自动安排复习。"
        )
        gr.Markdown(
            "> 💡 **使用方法**：点击「加载下一张」拉取到期卡片 → 看正面思考 → 展开看答案 → 用 4 档评分（重来/困难/良好/简单）。算法会根据评分安排下次复习时间。"
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📊 今日复习概况")
                self.stat_total = gr.Markdown("**总卡片数**：0")
                self.stat_due = gr.Markdown("**今日待复习**：0")
            with gr.Column(scale=1):
                gr.Markdown("### 📝 评分说明")
                gr.Markdown(
                    "- 😖 **重来**：完全想不起来，需要重新学习\n"
                    "- 😰 **困难**：想起来了但很费劲\n"
                    "- 🙂 **良好**：正常回忆起来（**多数情况选这个**）\n"
                    "- 😄 **简单**：一眼就会，太简单了"
                )

        gr.Markdown("---\n### 🎴 当前卡片")
        self.card_front = gr.Markdown("*点击下方「加载下一张」开始复习*")
        with gr.Accordion("📌 展开看答案", open=False):
            self.card_back = gr.Markdown("")

        with gr.Row(equal_height=True):
            self.btn_load = gr.Button("📥 加载下一张", variant="primary")
        with gr.Row(equal_height=True):
            self.btn_again = gr.Button("😖 重来", variant="stop")
            self.btn_hard = gr.Button("😰 困难")
            self.btn_good = gr.Button("🙂 良好", variant="primary")
            self.btn_next = gr.Button("😄 简单")

        self.status = gr.Markdown("")

    def on_register_events(self):
        self.btn_load.click(
            fn=self._load_next,
            outputs=[
                self.card_front,
                self.card_back,
                self.current_card_id,
                self.status,
            ],
        )
        self.btn_again.click(
            fn=lambda cid: self._review(cid, RATING_AGAIN),
            inputs=[self.current_card_id],
            outputs=[self.status],
        ).then(
            fn=self._load_next,
            outputs=[
                self.card_front,
                self.card_back,
                self.current_card_id,
                self.status,
            ],
        )
        self.btn_hard.click(
            fn=lambda cid: self._review(cid, RATING_HARD),
            inputs=[self.current_card_id],
            outputs=[self.status],
        )
        self.btn_good.click(
            fn=lambda cid: self._review(cid, RATING_GOOD),
            inputs=[self.current_card_id],
            outputs=[self.status],
        )
        self.btn_next.click(
            fn=lambda cid: self._review(cid, RATING_EASY),
            inputs=[self.current_card_id],
            outputs=[self.status],
        )

    def _load_next(self):
        try:
            with Session(engine) as session:
                queue = get_due_cards(session, user_id="default", limit=1)
                if not queue.cards:
                    return (
                        "*🎉 太棒了！当前没有到期卡片，今天复习任务完成啦！*",
                        "",
                        None,
                        "✅ 今日复习完成",
                    )
                c = queue.cards[0]
                return f"### {c.front}", c.back, c.id, ""
        except Exception as e:
            logger.exception("加载卡片失败")
            return "*加载失败*", "", None, f"❌ {e}"

    def _review(self, card_id, rating):
        if not card_id:
            return "⚠️ 请先点击「加载下一张」"
        try:
            with Session(engine) as session:
                review_fsrs_card(session, int(card_id), rating, user_id="default")
                return "✅ 已记录评分，继续下一张..."
        except Exception as e:
            logger.exception("复习失败")
            return f"❌ {e}"
