"""学习工作台 (从零重写, 干净可靠版)。

设计原则：
    1. 全部事件用普通函数 return (不用 generator, 不用 @gr.render)
    2. UI 组件只创建一次, 事件绑定到 UI 中的组件实例
    3. demo.load() 在页面加载后自动填充项目下拉框
    4. 三栏布局: 左(项目+课程) / 中(内容+笔记+资料) / 右(AI对话)

三栏每列内部独立滚动, 高度限制为视窗高度。
"""

from __future__ import annotations

import logging

import gradio as gr
from ktem.app import BasePage
from ktem.db.engine import engine
from sqlmodel import Session, select

from learning_ext.application import (
    generate_node_content,
    generate_node_resources,
    generate_practice_lesson,
    get_node_detail,
    get_project_workspace,
    list_projects,
    save_node_note,
    update_node_status,
)
from learning_ext.db.models import (
    KnowledgeEdge,
    KnowledgeNode,
    LearningProject,
    NodeResource,
    Task,
)
from learning_ext.notes import (
    explain_term,
    fetch_preview,
    generate_resources,
    get_note,
    get_resources,
    save_note,
    save_resources_to_db,
)
from learning_ext.progress.study import (
    STATUS_LEARNING,
    STATUS_MASTERED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    generate_node_summary_to_db,
    generate_practice_lesson_to_db,
    generate_summaries_background,
    get_practice_task,
    get_next_learnable_nodes,
    get_nodes_without_content,
    get_project_progress,
    is_content_valid,
    sort_nodes_by_code,
    regenerate_all_content,
)
from learning_ext.progress.audit import audit_node_content

logger = logging.getLogger(__name__)

STATUS_LABEL = {
    STATUS_PENDING: "⏳待学",
    STATUS_LEARNING: "📖学习中",
    STATUS_MASTERED: "✅已掌握",
    "weak": "⚠️薄弱",
    STATUS_SKIPPED: "⏭跳过",
}
STAGE_NAMES = {"base": "🌱 基础", "strengthen": "💪 强化", "sprint": "🔥 冲刺"}

RESOURCE_ICON = {
    "doc": "📄",
    "html": "🌐",
    "pdf": "📕",
    "video": "🎬",
    "book": "📖",
    "article": "📰",
    "tool": "🔧",
    "search": "🔍",
    "summary": "🧠",
}

RESOURCE_EMPTY_MD = "*点「拉取参考资料」自动抓取本节正文引用来源*"

# 划词解释主脚本由 custom_app.py 内联到 Gradio 初始模板。这里保留 Gradio
# 事件侧的轻量兜底: 如果事件 JS 可用, 重新确认监听器已安装。
WORD_LOOKUP_JS = """
function(...args){
  if (window.__leInstallWordLookup) window.__leInstallWordLookup();
  return args;
}
"""

WORKBENCH_CSS = """
<style>
#learning-workbench-tab {
    max-width: none !important;
    width: 100% !important;
}
#learning-workbench-tab > .tabitem {
    max-width: none !important;
    width: 100% !important;
}
#le-workbench-row {
    display: flex !important;
    align-items: stretch !important;
    gap: 12px !important;
    flex-wrap: nowrap !important;
    overflow-x: hidden !important;
}
#le-left-col, #le-center-col, #le-right-col {
    height: calc(100vh - 160px) !important;
    max-height: calc(100vh - 160px) !important;
    min-height: 500px !important;
    min-width: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding-right: 4px !important;
    flex-wrap: nowrap !important;
    align-content: stretch !important;
}
#le-left-col {
    min-width: 300px !important;
}
#le-center-col {
    flex-direction: column !important;
    min-width: 400px !important;
}
#le-right-col {
    min-width: 430px !important;
}
#le-center-col > * {
    flex: 0 0 auto !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
}
#le-content-tabs, #le-guide-md {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
}
#le-term-result {
    display: none !important;
}
#le-guide-md {
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
}
#le-selected-term {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
}
#le-left-col::-webkit-scrollbar, #le-center-col::-webkit-scrollbar, #le-right-col::-webkit-scrollbar {
    width: 6px;
}
#le-left-col::-webkit-scrollbar-thumb, #le-center-col::-webkit-scrollbar-thumb, #le-right-col::-webkit-scrollbar-thumb {
    background: #D1D5DB;
    border-radius: 3px;
}
</style>
"""


class StudyWorkbenchPage(BasePage):
    """学习工作台"""

    def __init__(self, app):
        super().__init__(app)
        # 仅声明 gr.State, 业务函数都是普通函数
        self.current_node_id = gr.State(None)
        self.current_project_id = gr.State(None)
        self._chat_history = gr.State([])

    # ==================== UI 构建 ====================

    def on_building_ui(self):
        gr.HTML(WORKBENCH_CSS)
        gr.Markdown("# 📚 学习工作台")

        with gr.Row(equal_height=True, elem_id="le-workbench-row"):
            # ============ 左列: 项目 + 课程列表 ============
            with gr.Column(scale=2, min_width=300, elem_id="le-left-col"):
                gr.Markdown("### 📂 项目")
                with gr.Row():
                    self.project_id = gr.Dropdown(
                        label="",
                        choices=[],
                        value=None,
                        scale=3,
                        interactive=True,
                        show_label=False,
                    )
                    self.refresh_btn = gr.Button("🔄", scale=1, size="sm")

                self.progress_display = gr.Markdown("", elem_classes=["le-progress"])

                with gr.Accordion("🔧 环境配置", open=False):
                    self.env_status = gr.Markdown("")
                    with gr.Row():
                        self.auto_setup_btn = gr.Button("🤖自动配置", size="sm")
                        self.apply_env_btn = gr.Button("✅已配好", size="sm")
                    self.auto_setup_output = gr.Code(
                        label="执行日志",
                        language="shell",
                        visible=False,
                        interactive=False,
                    )

                with gr.Accordion("🛠️ 内容管理", open=False):
                    self.regen_all_btn = gr.Button("📦 补全缺失内容", size="sm")
                    self.regen_all_force_btn = gr.Button(
                        "🔄 强制重生成全部", size="sm", variant="stop"
                    )
                    self.regen_all_status = gr.Markdown("")

                gr.Markdown("### 📋 课程列表")
                self.course_drop = gr.Dropdown(
                    label="选择知识点（按阶段分组）",
                    choices=[],
                    value=None,
                    interactive=True,
                )
                self.view_btn = gr.Button("📖 查看课程", variant="primary", size="sm")
                self.load_list_btn = gr.Button("🔁 刷新列表", size="sm")

                # ===== 添加课程 =====
                with gr.Accordion("➕ 添加课程", open=False):
                    self.add_title = gr.Textbox(
                        label="课程标题",
                        placeholder="如：分布式训练进阶",
                        show_label=True,
                        lines=1,
                    )
                    with gr.Row():
                        self.add_stage = gr.Dropdown(
                            label="阶段",
                            choices=[
                                ("🌱 基础", "base"),
                                ("💪 强化", "strengthen"),
                                ("🔥 冲刺", "sprint"),
                            ],
                            value="base",
                            show_label=True,
                        )
                        self.add_code = gr.Textbox(
                            label="编号(可选)",
                            placeholder="如：1.6",
                            show_label=True,
                            lines=1,
                        )
                    with gr.Row():
                        self.add_difficulty = gr.Slider(
                            label="难度",
                            minimum=1,
                            maximum=5,
                            value=3,
                            step=1,
                        )
                        self.add_hours = gr.Number(
                            label="预估学时", value=2, precision=0
                        )
                    self.add_desc = gr.Textbox(
                        label="课程描述/说明",
                        placeholder="这个课程要学什么...",
                        show_label=True,
                        lines=2,
                    )
                    with gr.Row():
                        self.add_ai_btn = gr.Button(
                            "🤖 AI生成教学内容", variant="secondary", size="sm"
                        )
                        self.add_btn = gr.Button(
                            "💾 添加课程", variant="primary", size="sm"
                        )
                    self.add_status = gr.Markdown("")

            # ============ 中列: 学习内容 ============
            with gr.Column(scale=5, min_width=400, elem_id="le-center-col"):
                # 划词解释隐藏输入框 + 浮窗触发
                self.selected_term = gr.Textbox(
                    elem_id="le-selected-term",
                    visible=True,
                    interactive=True,
                    show_label=False,
                )

                gr.Markdown("### 📖 当前知识点")
                self.node_header = gr.Markdown(
                    "*选择左侧课程即可加载*", elem_id="le-center-content"
                )

                with gr.Tabs(elem_id="le-content-tabs"):
                    with gr.TabItem("📋 教学内容", elem_id="le-lookup-zone"):
                        self.node_guide = gr.Markdown(
                            "", elem_id="le-guide-md", elem_classes=["le-lookup-zone"]
                        )
                        with gr.Row():
                            self.regen_node_btn = gr.Button("🔄 重新生成本节", size="sm")
                            self.audit_node_btn = gr.Button(
                                "🧭 审计本节完整性", size="sm"
                            )
                        self.regen_node_status = gr.Markdown("")
                        with gr.Accordion("🧭 完整性审计报告", open=False):
                            self.audit_node_output = gr.Markdown(
                                "*点击「审计本节完整性」，让 AI 检查本节是否讲全、讲深、是否需要拆分或补充。*"
                            )

                    with gr.TabItem("🧪 实操课程", elem_id="le-practice-zone"):
                        gr.Markdown(
                            "> 高难度或偏实操课程会自动生成流程、代码、验收标准和排错清单。"
                        )
                        with gr.Row():
                            self.gen_practice_btn = gr.Button(
                                "🧪 生成实操课程", size="sm"
                            )
                            self.gen_practice_status = gr.Markdown("")
                        self.practice_md = gr.Markdown(
                            "*本节暂无实操课程。高难/实操内容会自动生成，也可以点击按钮手动生成。*"
                        )

                    with gr.TabItem("📝 我的笔记", elem_id="le-note-zone"):
                        gr.Markdown(
                            "> 记录笔记, 会自动保存到当前知识点。支持 Markdown。"
                        )
                        self.note_input = gr.Textbox(
                            label="笔记",
                            placeholder="记录理解、疑问、总结...",
                            lines=12,
                            show_label=False,
                        )
                        with gr.Row():
                            self.save_note_btn = gr.Button(
                                "💾 保存笔记", variant="primary", size="sm"
                            )
                            self.note_status = gr.Markdown("")

                    with gr.TabItem("📚 参考资料", elem_id="le-resource-zone"):
                        gr.Markdown(
                            "> AI 会拉取本节正文用到的参考来源，优先保存 PDF，其次保存网页 HTML。"
                        )
                        with gr.Row():
                            self.gen_resources_btn = gr.Button(
                                "🤖 拉取参考资料", size="sm"
                            )
                            self.gen_resources_status = gr.Markdown("")
                        self.resources_md = gr.Markdown(
                            RESOURCE_EMPTY_MD
                        )
                        with gr.Accordion("手动抓取单个 URL", open=False):
                            self.resource_preview_url = gr.Textbox(
                                label="URL",
                                placeholder="https://...",
                                scale=3,
                                show_label=False,
                            )
                            self.preview_btn = gr.Button(
                                "👁 抓取正文", scale=1, size="sm"
                            )
                            self.resource_preview = gr.Markdown("")

                with gr.Accordion(
                    "🔍 划词解释结果", open=False, elem_id="le-term-result"
                ):
                    gr.Markdown(
                        '<span style="color:#6B7280;">在教学内容中选中名词, 会出现「🔍 AI 解释」浮窗。</span>'
                    )
                    self.term_explain_btn = gr.Button("🔍 解释选中词汇", size="sm")
                    self.term_explain_output = gr.Markdown("", elem_id="le-term-output")

                gr.Markdown("---")
                with gr.Row():
                    self.start_btn = gr.Button(
                        "🚀 学习中", variant="secondary", size="sm"
                    )
                    self.master_btn = gr.Button(
                        "✅ 已掌握", variant="primary", size="sm"
                    )
                    self.skip_btn = gr.Button("⏭ 跳过", size="sm")
                self.action_status = gr.Markdown("")

            # ============ 右列: AI 助教对话 ============
            with gr.Column(scale=3, min_width=430, elem_id="le-right-col"):
                gr.Markdown(
                    "### 💬 AI 助教\n"
                    '<span style="color:#6B7280;font-size:12px;">深入探讨、纠正教学内容、补充知识。</span>'
                )
                self.chatbot = gr.Chatbot(
                    label="",
                    height=480,
                    show_label=False,
                    type="messages",
                )
                self.chat_input = gr.Textbox(
                    label="",
                    placeholder="基于当前知识点提问...",
                    show_label=False,
                    lines=2,
                )
                with gr.Row():
                    self.chat_send_btn = gr.Button("发送", variant="primary", size="sm")
                    self.chat_clear_btn = gr.Button("清空", size="sm")
                self.append_chat_to_lesson_btn = gr.Button(
                    "➕ 并入本节正文", variant="secondary", size="sm"
                )
                self.append_chat_status = gr.Markdown("")

    # ==================== 事件绑定 ====================

    def on_register_events(self):
        # 项目变化: 刷新进度 + 课程下拉框 + 环境状态
        project_outputs = [
            self.progress_display,
            self.course_drop,
            self.current_project_id,
            self.env_status,
        ]
        self.project_id.change(
            fn=self._on_project_change,
            inputs=[self.project_id],
            outputs=project_outputs,
        )
        self.refresh_btn.click(
            fn=self._refresh_projects,
            outputs=[self.project_id],
        ).then(
            fn=self._on_project_change,
            inputs=[self.project_id],
            outputs=project_outputs,
        )
        self.load_list_btn.click(
            fn=self._on_project_change,
            inputs=[self.current_project_id],
            outputs=project_outputs,
        )

        # 课程选择: Dropdown 选课后点「查看课程」按钮加载内容 (解耦: 项目变更不清空内容)
        view_outputs = [
            self.current_node_id,
            self.node_header,
            self.node_guide,
            self.practice_md,
            self.note_input,
            self.resources_md,
            self.chatbot,
            self._chat_history,
        ]
        self.view_btn.click(
            fn=self._on_node_select,
            inputs=[self.course_drop],
            outputs=view_outputs,
        )
        self.course_drop.change(
            fn=self._on_course_change,
            inputs=[self.course_drop],
            outputs=view_outputs,
        )

        # 环境配置
        self.auto_setup_btn.click(
            fn=self._auto_setup,
            inputs=[self.current_project_id],
            outputs=[self.auto_setup_output, self.env_status],
        )
        self.apply_env_btn.click(
            fn=self._apply_env,
            inputs=[self.current_project_id],
            outputs=[self.env_status],
        )

        # 重新生成
        self.regen_node_btn.click(
            fn=self._regen_current_node,
            inputs=[self.current_node_id, self.current_project_id],
            outputs=[self.regen_node_status, self.node_header, self.node_guide],
        )
        self.audit_node_btn.click(
            fn=self._audit_current_node,
            inputs=[self.current_node_id],
            outputs=[self.audit_node_output],
        )
        self.regen_all_btn.click(
            fn=lambda pid: self._regen_all(pid, False),
            inputs=[self.current_project_id],
            outputs=[self.regen_all_status],
        )
        self.regen_all_force_btn.click(
            fn=lambda pid: self._regen_all(pid, True),
            inputs=[self.current_project_id],
            outputs=[self.regen_all_status],
        )

        # 笔记
        self.save_note_btn.click(
            fn=self._save_note,
            inputs=[self.current_node_id, self.current_project_id, self.note_input],
            outputs=[self.note_status],
        )

        # 实操课程
        self.gen_practice_btn.click(
            fn=self._gen_practice_lesson,
            inputs=[self.current_node_id, self.current_project_id],
            outputs=[self.practice_md, self.gen_practice_status],
        )

        # 参考资料
        self.gen_resources_btn.click(
            fn=self._gen_resources,
            inputs=[self.current_node_id, self.current_project_id],
            outputs=[self.resources_md, self.gen_resources_status],
        )
        self.preview_btn.click(
            fn=self._preview_resource,
            inputs=[self.resource_preview_url],
            outputs=[self.resource_preview],
        )

        # 划词解释
        self.selected_term.change(
            fn=self._on_term_selected,
            inputs=[self.selected_term, self.current_node_id],
            outputs=[self.term_explain_output],
        )
        self.term_explain_btn.click(
            fn=self._on_term_selected_manual,
            inputs=[self.selected_term, self.current_node_id],
            outputs=[self.term_explain_output],
        )

        # AI 对话 (用 generator: 先显示用户消息, 再流式回复)
        self.chat_send_btn.click(
            fn=self._chat_send,
            inputs=[self.chat_input, self.current_node_id, self._chat_history],
            outputs=[self.chatbot, self._chat_history, self.chat_input],
        )
        self.chat_input.submit(
            fn=self._chat_send,
            inputs=[self.chat_input, self.current_node_id, self._chat_history],
            outputs=[self.chatbot, self._chat_history, self.chat_input],
        )
        self.chat_clear_btn.click(
            fn=lambda: ([], [], ""),
            outputs=[self.chatbot, self._chat_history, self.chat_input],
        )
        self.append_chat_to_lesson_btn.click(
            fn=self._append_last_assistant_to_node,
            inputs=[self.current_node_id, self._chat_history],
            outputs=[self.node_guide, self.append_chat_status],
        )

        # 添加课程
        add_outputs = [self.add_status, self.course_drop, self.progress_display]
        self.add_btn.click(
            fn=self._add_node,
            inputs=[
                self.current_project_id,
                self.add_title,
                self.add_desc,
                self.add_stage,
                self.add_code,
                self.add_difficulty,
                self.add_hours,
            ],
            outputs=add_outputs,
        )
        # AI 生成教学内容后直接添加
        self.add_ai_btn.click(
            fn=self._add_node_with_ai,
            inputs=[
                self.current_project_id,
                self.add_title,
                self.add_desc,
                self.add_stage,
                self.add_code,
                self.add_difficulty,
                self.add_hours,
            ],
            outputs=add_outputs,
        )

        # 状态操作: 刷新进度 + 3个课程下拉框
        status_outputs = [
            self.action_status,
            self.progress_display,
            self.course_drop,
        ]
        self.start_btn.click(
            fn=lambda nid: self._set_status(nid, STATUS_LEARNING),
            inputs=[self.current_node_id],
            outputs=status_outputs,
        )
        self.master_btn.click(
            fn=lambda nid: self._set_status(nid, STATUS_MASTERED),
            inputs=[self.current_node_id],
            outputs=status_outputs,
        )
        self.skip_btn.click(
            fn=lambda nid: self._set_status(nid, STATUS_SKIPPED),
            inputs=[self.current_node_id],
            outputs=status_outputs,
        )

        # 页面加载后自动初始化: 填充项目+课程+预加载第一节内容
        load_outputs = [
            self.project_id,  # 0: 项目下拉框
            self.progress_display,  # 1: 进度
            self.course_drop,  # 2: 课程下拉框
            self.current_project_id,  # 3
            self.env_status,  # 4
            self.current_node_id,  # 5: 预加载的节点 id
            self.node_header,  # 6: 节点标题
            self.node_guide,  # 7: 教学内容
            self.practice_md,  # 8: 实操课程
            self.note_input,  # 9: 笔记
            self.resources_md,  # 10: 参考资料
            self.chatbot,  # 11
            self._chat_history,  # 12
        ]
        try:
            self._app.app.load(
                fn=self._auto_init,
                outputs=load_outputs,
                js=WORD_LOOKUP_JS,
            )
        except Exception as e:
            logger.warning(f"demo.load 注册失败: {e}")

    # ==================== 业务函数 ====================

    def _build_node_header(self, node, proj):
        return (
            f"### [{node.code}] {node.title}\n\n"
            f"`{node.est_hours}h` `难度{node.difficulty}/5` "
            f"`{STATUS_LABEL.get(node.status, node.status)}`"
        )

    def _build_progress_md(self, prog):
        return (
            f"**进度**: {prog['done']}/{prog['total']} ({prog['pct']}%)\n\n"
            f"✅已掌握 {prog['done']} · 📖学习中 {prog['learning']} · ⏳待学 {prog['pending']}"
        )

    def _build_nodes_data(self, session, pid):
        nodes = session.exec(
            select(KnowledgeNode)
            .where(KnowledgeNode.project_id == pid)
        ).all()
        learnable_ids = {n.id for n in get_next_learnable_nodes(session, pid, limit=50)}
        done_statuses = {STATUS_MASTERED, STATUS_SKIPPED}
        result = []
        for n in sort_nodes_by_code(list(nodes)):
            result.append(
                {
                    "id": n.id,
                    "code": n.code,
                    "title": n.title,
                    "stage": n.stage,
                    "status": n.status,
                    "has_content": is_content_valid(n.description),
                    "learnable": n.id in learnable_ids or n.status in done_statuses,
                }
            )
        return result

    def _build_drop_choices(self, nodes_data):
        """构建单个 Dropdown 的全部选项列表 (按阶段分组, 带状态图标)。"""
        choices = []
        stages_order = ["base", "strengthen", "sprint"]
        grouped: dict[str, list] = {}
        for n in nodes_data:
            grouped.setdefault(n.get("stage", "base"), []).append(n)
        for stage_key in stages_order:
            ns = grouped.get(stage_key, [])
            if not ns:
                continue
            # 添加阶段分隔标题 (作为不可选项, value 留空)
            choices.append(
                (f"──── {STAGE_NAMES.get(stage_key, stage_key)} ────", "__stage__")
            )
            for n in ns:
                status = n.get("status", STATUS_PENDING)
                has_content = n.get("has_content", False)
                learnable = n.get("learnable", False)
                icon = {
                    STATUS_MASTERED: "✅",
                    STATUS_LEARNING: "📖",
                    STATUS_SKIPPED: "⏭",
                    STATUS_PENDING: "🔓" if learnable else "🔒",
                }.get(status, "🔓")
                content_mark = "📝" if has_content else "⏳"
                label = (
                    f"  {icon}{content_mark} [{n.get('code', '')}] {n.get('title', '')}"
                )
                choices.append((label, str(n.get("id", 0))))
        return choices

    def _load_env(self, session, pid):
        env_task = session.exec(
            select(Task).where(Task.project_id == pid).where(Task.task_type == "env")
        ).first()
        if env_task:
            return env_task.description or "", (
                "✅ 环境已配置" if env_task.status == "done" else "⚠️ 环境待配置"
            )
        return "", ""

    @staticmethod
    def _format_environment_status(status):
        return {
            "done": "✅ 环境已配置",
            "pending": "⚠️ 环境待配置",
        }.get(status, "")

    def _render_resources_md(self, resources):
        lines = []
        for r in resources:
            rtype = r.get("rtype", "") if isinstance(r, dict) else r.rtype
            if rtype == "summary":
                continue
            get = r.get if isinstance(r, dict) else lambda key, default="": getattr(r, key, default)
            icon = RESOURCE_ICON.get(rtype, "📄")
            lines.append(f"### {icon} {get('title')}")
            lines.append(f"\n类型：`{(rtype or 'html').upper()}`")
            if get("description"):
                lines.append(f"\n{get('description')}")
            if get("preview"):
                lines.append("\n已拉取正文内容，后台已保存用于审计与后续引用。")
            else:
                lines.append("\n*未能抓取到可读正文。*")
            if get("url"):
                lines.append(f"\n来源：`{get('url')}`")
            lines.append("\n---")
        return "\n".join(lines) if lines else "*暂无可展示参考资料。*"

    def _render_practice_md(self, task):
        description = task.get("description", "") if isinstance(task, dict) else getattr(task, "description", "")
        if not task or not description:
            return "*本节暂无实操课程。高难/实操内容会自动生成，也可以点击「🧪 生成实操课程」。*"
        return description

    # ---- 自动初始化 (页面加载时执行, 预加载第一节内容) ----
    def _auto_init(self):
        """页面加载后: 填充项目/课程下拉框 + 预加载第一个可学节点的教学内容。"""
        try:
            with Session(engine) as s:
                projs = list_projects(s)
                if not projs:
                    return [
                        gr.update(),
                        "",
                        gr.update(),
                        None,
                        "",
                        None,
                        "*请先创建学习路线*",
                        "",
                        "*本节暂无实操课程。*",
                        "",
                        RESOURCE_EMPTY_MD,
                        [],
                        [],
                    ]
                pid = projs[0].id
                dd_update = gr.update(
                    choices=[(f"#{p.id} {p.title[:30]}", str(p.id)) for p in projs],
                    value=str(pid),
                )
                workspace = get_project_workspace(s, pid)
                progress_md = self._build_progress_md(workspace.progress)
                env_status = self._format_environment_status(workspace.environment["status"])
                nodes_data = [node.to_dict() for node in workspace.nodes]
                course_c = self._build_drop_choices(nodes_data)

                # 预加载第一个节点的内容
                first_node_id = None
                header = "*选择课程开始学习*"
                guide = ""
                practice_md = "*本节暂无实操课程。*"
                note_content = ""
                res_md = RESOURCE_EMPTY_MD
                if nodes_data:
                    first = nodes_data[0]
                    first_node_id = first["id"]
                    detail = get_node_detail(s, first_node_id)
                    header = (
                        f"### [{detail.code}] {detail.title}\n\n"
                        f"`{detail.est_hours}h` `难度{detail.difficulty}/5` "
                        f"`{STATUS_LABEL.get(detail.status, detail.status)}`"
                    )
                    guide = self._truncate_guide(
                        detail.description or self._missing_course_content("")
                    )
                    practice_md = self._render_practice_md(detail.practice)
                    note_content = detail.note["content"] if detail.note else ""
                    res_md = (
                        self._render_resources_md(detail.resources)
                        if detail.resources
                        else RESOURCE_EMPTY_MD
                    )
                # 选中第一个节点
                course_update = gr.update(
                    choices=course_c,
                    value=str(first_node_id) if first_node_id else None,
                )

                logger.info(
                    f"[工作台] _auto_init 完成: 项目#{pid}, 预加载节点#{first_node_id}, guide长度={len(guide)}"
                )

                return [
                    dd_update,  # 0: 项目下拉框
                    progress_md,  # 1: 进度
                    course_update,  # 2: 课程下拉框
                    pid,  # 3: current_project_id
                    env_status,  # 4: 环境状态
                    first_node_id,  # 5: current_node_id
                    header,  # 6: 节点标题
                    guide,  # 7: 教学内容
                    practice_md,  # 8: 实操课程
                    note_content,  # 9: 笔记
                    res_md,  # 10: 参考资料
                    [],  # 11: chatbot
                    [],  # 12: chat history
                ]
        except Exception as e:
            logger.exception("_auto_init 失败")
            return [
                gr.update(),
                "",
                gr.update(),
                None,
                "",
                None,
                "*加载失败*",
                "",
                "*本节暂无实操课程。*",
                "",
                RESOURCE_EMPTY_MD,
                [],
                [],
            ]

    # ---- 项目相关 ----
    def _refresh_projects(self):
        try:
            with Session(engine) as session:
                projects = list_projects(session)
                choices = [(f"#{p.id} {p.title[:30]}", str(p.id)) for p in projects]
                cur = str(projects[0].id) if projects else None
                return gr.update(choices=choices, value=cur)
        except Exception:
            return gr.update()

    def _on_project_change(self, project_id):
        if not project_id:
            return "*请先选择项目*", gr.update(), None, ""
        try:
            pid = int(project_id)
        except (ValueError, TypeError):
            return "*ID无效*", gr.update(), None, ""
        try:
            with Session(engine) as session:
                workspace = get_project_workspace(session, pid)
                progress_md = self._build_progress_md(workspace.progress)
                env_status = self._format_environment_status(
                    workspace.environment["status"]
                )
                nodes_data = [node.to_dict() for node in workspace.nodes]
        except Exception:
            return "*项目不存在*", gr.update(), None, ""
        course_c = self._build_drop_choices(nodes_data)
        return (
            progress_md,
            gr.update(choices=course_c, value=None),
            pid,
            env_status,
        )

    # ---- 添加课程 ----
    def _add_node(self, project_id, title, desc, stage, code, difficulty, hours):
        """添加课程 (不含 AI 教学内容, 后续可在工作台生成)。"""
        if not project_id:
            return "⚠️ 请先选择项目", gr.update(), gr.update()
        if not title or not title.strip():
            return "⚠️ 请输入课程标题", gr.update(), gr.update()
        try:
            from learning_ext.progress.study import add_node

            with Session(engine) as s:
                node = add_node(
                    s,
                    int(project_id),
                    title.strip(),
                    description=desc or "",
                    stage=stage or "base",
                    code=code or "",
                    difficulty=difficulty or 3,
                    est_hours=hours or 2,
                )
                pid = int(project_id)
                nodes_data = self._build_nodes_data(s, pid)
                course_c = self._build_drop_choices(nodes_data)
                prog = get_project_progress(s, pid)
                progress_md = self._build_progress_md(prog)
            return (
                f"✅ 已添加课程 [{node.code}] {node.title}。可选中它后点「🔄 重新生成本节」让 AI 生成教学内容。",
                gr.update(choices=course_c, value=str(node.id)),
                progress_md,
            )
        except Exception as e:
            return f"❌ 添加失败: {e}", gr.update(), gr.update()

    def _add_node_with_ai(
        self, project_id, title, desc, stage, code, difficulty, hours
    ):
        """添加课程并立即用 AI 生成教学内容 (同步等待约 30-60 秒)。"""
        if not project_id:
            return "⚠️ 请先选择项目", gr.update(), gr.update()
        if not title or not title.strip():
            return "⚠️ 请输入课程标题", gr.update(), gr.update()
        try:
            from learning_ext.progress.study import (
                add_node,
                generate_node_summary_to_db,
            )

            with Session(engine) as s:
                node = add_node(
                    s,
                    int(project_id),
                    title.strip(),
                    description=desc or "",
                    stage=stage or "base",
                    code=code or "",
                    difficulty=difficulty or 3,
                    est_hours=hours or 2,
                )
                nid = node.id
                pid = int(project_id)
                proj = s.get(LearningProject, pid)
                topic = proj.topic if proj else ""
            # AI 生成教学内容
            ok = generate_node_summary_to_db(nid, topic)
            with Session(engine) as s:
                nodes_data = self._build_nodes_data(s, pid)
                course_c = self._build_drop_choices(nodes_data)
                prog = get_project_progress(s, pid)
                progress_md = self._build_progress_md(prog)
            if ok:
                msg = f"✅ 已添加课程 [{node.code}] {node.title} 并生成完整教学内容！"
            else:
                msg = f"✅ 已添加课程 [{node.code}] {node.title}，教学内容生成失败，可后续重试。"
            return msg, gr.update(choices=course_c, value=str(nid)), progress_md
        except Exception as e:
            return f"❌ 失败: {e}", gr.update(), gr.update()

    # ---- 课程加载 (按钮触发, 普通函数) ----
    def _on_node_select(self, node_id):
        """「查看课程」按钮触发: 读取 Dropdown 选中的节点 ID, 加载教学内容。"""
        logger.info(f"[工作台] _on_node_select 被调用, node_id={node_id!r}")
        if not node_id or node_id == "__stage__":
            return (
                None,
                "*请先在下拉框中选择一节课，再点「查看课程」*",
                "",
                "*本节暂无实操课程。*",
                "",
                RESOURCE_EMPTY_MD,
                [],
                [],
            )
        try:
            nid = int(node_id)
        except (ValueError, TypeError):
            return None, "*ID无效*", "", "*本节暂无实操课程。*", "", RESOURCE_EMPTY_MD, [], []

        try:
            with Session(engine) as session:
                detail = get_node_detail(session, nid)
            header = (
                f"### [{detail.code}] {detail.title}\n\n"
                f"`{detail.est_hours}h` `难度{detail.difficulty}/5` "
                f"`{STATUS_LABEL.get(detail.status, detail.status)}`"
            )
            return (
                nid,
                header,
                self._truncate_guide(detail.description or self._missing_course_content("")),
                self._render_practice_md(detail.practice),
                detail.note["content"] if detail.note else "",
                self._render_resources_md(detail.resources) if detail.resources else RESOURCE_EMPTY_MD,
                [],
                [],
            )
        except Exception as error:
            return None, f"*加载失败: {error}*", "", "*本节暂无实操课程。*", "", RESOURCE_EMPTY_MD, [], []

    def _on_course_change(self, node_id):
        if not node_id or node_id == "__stage__":
            return tuple(gr.update() for _ in range(8))
        return self._on_node_select(node_id)

    def _ensure_course_content(self, node_id: int, topic: str, guide: str | None) -> str:
        current = guide or ""
        if is_content_valid(current):
            return current
        try:
            ok = generate_node_summary_to_db(node_id, topic)
            if ok:
                with Session(engine) as session:
                    node = session.get(KnowledgeNode, node_id)
                    current = node.description if node else current
            else:
                return self._missing_course_content(current)
        except Exception as e:
            return f"*生成失败: {e}*"
        if is_content_valid(current):
            return current
        return self._missing_course_content(current)

    def _missing_course_content(self, brief: str | None) -> str:
        brief = (brief or "").strip()
        lines = [
            "⚠️ **本节完整教学内容还没有生成成功。**",
            "",
            "可以点击「🔄 重新生成本节」重新生成课程正文；右侧 AI 助教仍可基于当前知识点答疑。",
        ]
        if brief:
            lines.extend(["", "#### 路线说明", brief])
        return "\n".join(lines)

    def _truncate_guide(self, guide: str, max_chars: int = 15000) -> str:
        """截断超长教学内容, 在章节边界截断并提示剩余可看。"""
        if len(guide) <= max_chars:
            return guide
        # 在 max_chars 附近找最后一个 ## 标题边界
        cut = guide.rfind("\n## ", 0, max_chars)
        if cut < max_chars * 0.5:
            cut = max_chars  # 找不到合适的边界就硬截
        remaining = len(guide) - cut
        return (
            guide[:cut]
            + f"\n\n---\n\n> 📄 **内容较长已截断显示（剩余约 {remaining} 字）**\n"
            + f"> 完整内容已保存，可在「❓ 追问 AI」中提问查看后续部分。\n"
        )

    # ---- 笔记 ----
    def _save_note(self, node_id, project_id, content):
        if not node_id:
            return "⚠️ 请先选择知识点"
        try:
            with Session(engine) as s:
                save_node_note(s, int(node_id), content)
            return "✅ 笔记已保存"
        except Exception as e:
            return f"❌ {e}"

    # ---- 实操课程 ----
    def _gen_practice_lesson(self, node_id, project_id):
        if not node_id:
            return "*请先选择知识点*", "⚠️ 请先选择知识点"
        try:
            with Session(engine) as s:
                result = generate_practice_lesson(s, int(node_id), force=True)
            if result.status == "failed":
                return "*生成失败，请稍后重试。*", "❌ 生成失败"
            return self._render_practice_md(result.detail.practice), "✅ 已生成实操课程"
        except Exception as e:
            return f"*生成失败: {e}*", f"❌ {e}"

    # ---- 参考资料 ----
    def _ensure_resources_background(self, node_id, project_id):
        if not node_id or not project_id:
            return RESOURCE_EMPTY_MD
        try:
            with Session(engine) as s:
                existing = get_resources(s, int(node_id))
                if existing:
                    return self._render_resources_md(existing)
        except Exception:
            return RESOURCE_EMPTY_MD

        import threading

        def _worker():
            try:
                with Session(engine) as s:
                    node = s.get(KnowledgeNode, int(node_id))
                    proj = (
                        s.get(LearningProject, int(project_id)) if project_id else None
                    )
                    if not node:
                        return
                    topic = proj.topic if proj else ""
                    items = generate_resources(node, topic)
                    save_resources_to_db(s, int(node_id), int(project_id), items)
            except Exception as e:
                logger.warning(f"自动拉取参考资料失败 (node {node_id}): {e}")

        threading.Thread(
            target=_worker,
            daemon=True,
            name=f"le-resources-{node_id}",
        ).start()
        return "⏳ 正在自动拉取参考资料，稍后刷新本节即可查看。"

    def _gen_resources(self, node_id, project_id):
        """生成参考资料 (普通函数, 接受同步等待)。"""
        if not node_id:
            return "*请先选择知识点*", "⚠️ 请先选择知识点"
        try:
            with Session(engine) as s:
                result = generate_node_resources(s, int(node_id))
            if result.status == "failed":
                return self._render_resources_md(result.detail.resources), f"❌ {result.error}"
            res_md = self._render_resources_md(result.detail.resources)
            if result.resource_count == 0:
                return res_md, "⚠️ 未拉取到可展示参考资料"
            return res_md, f"✅ 已拉取 {result.resource_count} 份参考资料"
        except Exception as e:
            return f"*生成失败: {e}*", f"❌ {e}"

    def _preview_resource(self, url):
        if not url or not url.strip():
            return "*请输入 URL*"
        return fetch_preview(url.strip())

    # ---- 划词解释 ----
    def _on_term_selected(self, term, node_id=None):
        if not term or not term.strip():
            return ""
        return self._do_explain(term.strip(), node_id)

    def _on_term_selected_manual(self, term, node_id):
        if not term or not term.strip():
            return "⚠️ 请先选中一个词, 或在此输入要解释的词"
        return self._do_explain(term.strip(), node_id)

    def _do_explain(self, term, node_id=None):
        try:
            with Session(engine) as s:
                nid = int(node_id) if node_id else None
                node = s.get(KnowledgeNode, nid) if nid else None
                proj = s.get(LearningProject, node.project_id) if node else None
                topic = proj.topic if proj else ""
            if not node:
                return f"**{term}**: 请先选择一个知识点, 以获得基于上下文的解释。"
            result = explain_term(term, node, topic)
            return f"### 🔍 {term}\n\n{result}"
        except Exception as e:
            return f"❌ 解释失败: {e}"

    # ---- AI 对话 (generator: 先显示用户消息, 再流式回复) ----
    def _chat_send(self, message, node_id, history):
        if not message or not message.strip():
            yield history, history, ""
            return
        user_msg = message.strip()
        new_history = (history or []) + [{"role": "user", "content": user_msg}]
        yield new_history, new_history, ""
        try:
            from learning_ext.llm import chat

            with Session(engine) as s:
                node = s.get(KnowledgeNode, int(node_id)) if node_id else None
                proj = s.get(LearningProject, node.project_id) if node else None
            ctx = ""
            if node:
                ctx = (
                    f"【学习主题】{proj.topic if proj else ''}\n"
                    f"【当前知识点】{node.title} ({node.code})\n"
                    f"【教学内容摘要】\n{(node.description or '')[:2000]}\n\n"
                )
            recent = (history or [])[-6:]
            ctx += "【对话历史】\n"
            for h in recent:
                role = "学习者" if h["role"] == "user" else "助教"
                ctx += f"{role}: {h['content'][:300]}\n"
            ctx += f"\n【学习者最新消息】{user_msg}\n\n请基于当前知识点教学内容回答。如教学内容有误或需补充, 明确指出。Markdown, 500字内。"
            reply = chat(
                ctx,
                system="你是耐心的学习助教。基于学习者正在学习的知识点和教学内容, 解答疑问、纠正误解、补充知识。",
                temperature=0.4,
            )
            final_history = new_history + [{"role": "assistant", "content": reply}]
            yield final_history, final_history, ""
        except Exception as e:
            err = new_history + [{"role": "assistant", "content": f"❌ 出错了: {e}"}]
            yield err, err, ""

    def _append_last_assistant_to_node(self, node_id, history):
        if not node_id:
            return gr.update(), "⚠️ 请先选择知识点"
        user_question = ""
        assistant_reply = ""
        for item in reversed(history or []):
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role == "assistant" and content and not assistant_reply:
                assistant_reply = content
                continue
            if role == "user" and content and assistant_reply:
                user_question = content
                break
        if not assistant_reply:
            return gr.update(), "⚠️ 还没有可并入正文的 AI 助教回答"
        supplement = self._build_ai_supplement_markdown(user_question, assistant_reply)
        try:
            with Session(engine) as s:
                node = s.get(KnowledgeNode, int(node_id))
                if not node:
                    return gr.update(), "⚠️ 知识点不存在"
                current = (node.description or "").rstrip()
                node.description = f"{current}\n\n{supplement}" if current else supplement
                s.add(node)
                s.commit()
                updated = node.description
            return updated, "✅ 已并入本节正文末尾，原内容未改动"
        except Exception as e:
            return gr.update(), f"❌ 并入失败: {e}"

    @staticmethod
    def _build_ai_supplement_markdown(user_question: str, assistant_reply: str) -> str:
        lines = [
            "---",
            "",
            "## AI 助教补充",
        ]
        if user_question:
            lines.extend(["", f"> 学习者追问：{user_question}"])
        lines.extend(["", assistant_reply.strip()])
        return "\n".join(lines)

    # ---- 环境配置 (generator: 流式显示命令输出) ----
    def _auto_setup(self, project_id):
        if not project_id:
            yield gr.update(visible=False), "⚠️ 请先选择项目"
            return
        try:
            pid = int(project_id)
        except (ValueError, TypeError):
            yield gr.update(visible=False), "⚠️ ID无效"
            return
        with Session(engine) as s:
            proj = s.get(LearningProject, pid)
            env_task = s.exec(
                select(Task)
                .where(Task.project_id == pid)
                .where(Task.task_type == "env")
            ).first()
            if not proj or not env_task or not env_task.description:
                yield gr.update(visible=False), "⚠️ 无环境清单"
                return
            env_md = env_task.description
            bg = proj.background or ""
        yield gr.update(visible=True, value="⏳ 生成命令中..."), "⏳"
        from learning_ext.practice.auto_setup import (
            generate_install_commands,
            run_all_commands,
        )

        try:
            commands = generate_install_commands(env_md, bg)
        except Exception as e:
            yield gr.update(visible=True, value=f"❌ {e}"), f"❌ {e}"
            return
        if not commands:
            yield gr.update(visible=True, value="✅ 无需配置"), "✅"
            return
        log_lines = []
        for chunk in run_all_commands(commands):
            log_lines.append(chunk.rstrip("\n"))
            yield gr.update(visible=True, value="\n".join(log_lines)), "⏳ 执行中..."
        yield gr.update(visible=True, value="\n".join(log_lines)), "✅ 完成"

    def _apply_env(self, project_id):
        if not project_id:
            return "⚠️ 请先选择项目"
        try:
            with Session(engine) as s:
                t = s.exec(
                    select(Task)
                    .where(Task.project_id == int(project_id))
                    .where(Task.task_type == "env")
                ).first()
                if t:
                    t.status = "done"
                    s.add(t)
                    s.commit()
            return "✅ 环境已配置"
        except Exception as e:
            return f"❌ {e}"

    # ---- 重新生成 ----
    def _regen_current_node(self, node_id, project_id):
        """重新生成本节教学内容 (普通函数)。"""
        if not node_id:
            return "⚠️ 请先选择知识点", gr.update(), gr.update()
        try:
            nid = int(node_id)
            with Session(engine) as s:
                result = generate_node_content(s, nid, force=True)
            if result.status == "failed":
                return "❌ 生成失败", gr.update(), gr.update()
            detail = result.detail
            header = (
                f"### [{detail.code}] {detail.title}\n\n"
                f"`{detail.est_hours}h` `难度{detail.difficulty}/5` "
                f"`{STATUS_LABEL.get(detail.status, detail.status)}`"
            )
            guide = detail.description or ""
            return "✅ 已重新生成", header, guide
        except Exception as e:
            return f"❌ {e}", gr.update(), gr.update()

    def _audit_current_node(self, node_id):
        """审计当前教材是否完整全面。"""
        if not node_id:
            return "⚠️ 请先选择知识点"
        try:
            with Session(engine) as s:
                return audit_node_content(s, int(node_id))
        except Exception as e:
            return f"❌ 审计失败: {e}"

    def _regen_all(self, project_id, force=False):
        try:
            pid = int(project_id) if project_id else None
            result = regenerate_all_content(project_id=pid, force=force)
            scope = f"项目#{pid}" if pid else "所有项目"
            mode = "强制重生成" if force else "补全"
            return f"📦 **{mode}** {scope}: 排队{result['queued']}节, 跳过{result['skipped']}节。后台生成中。"
        except Exception as e:
            return f"❌ {e}"

    # ---- 状态 ----
    def _set_status(self, node_id, status):
        if not node_id:
            return (
                "⚠️ 请先选择知识点",
                gr.update(),
                gr.update(),
            )
        try:
            nid = int(node_id)
            with Session(engine) as s:
                result = update_node_status(s, nid, status)
                pid = result.workspace.project["id"]
                proj = s.get(LearningProject, pid)
                topic = proj.topic if proj else ""
                if status == STATUS_MASTERED:
                    pending = get_nodes_without_content(s, pid, limit=3)
                    pids = [n.id for n in pending if n.id != nid]
                    if pids:
                        generate_summaries_background(pid, topic, pids)
                progress_md = self._build_progress_md(result.workspace.progress)
                nodes_data = [node.to_dict() for node in result.workspace.nodes]
            course_c = self._build_drop_choices(nodes_data)
            if status == STATUS_MASTERED:
                msg = "🎉 已掌握！下一节内容正在后台生成。"
            elif status == STATUS_LEARNING:
                msg = "📖 已标记学习中。"
            else:
                msg = "⏭ 已跳过。"
            return (
                msg,
                progress_md,
                gr.update(choices=course_c, value=str(nid)),
            )
        except Exception as e:
            return f"❌ {e}", gr.update(), gr.update()
