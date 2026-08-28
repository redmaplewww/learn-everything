"""学习路线 Tab - 选题 → AI 拆知识 DAG → 可视化展示。

这是阶段 1 的核心 Tab，演示如何把 learning_ext 业务模块接入 Kotaemon 的 BasePage。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import gradio as gr
from ktem.app import BasePage
from ktem.db.engine import engine
from sqlmodel import Session, select

from learning_ext.application import (
    create_project,
    generate_roadmap_preview,
    get_project_roadmap,
    list_projects,
    prepare_project_content,
    refine_roadmap_preview,
    replace_project_roadmap as replace_project_roadmap_application,
)
from learning_ext.db.models import LearningProject
from learning_ext.path_generator import (
    audit_existing_roadmap,
    export_roadmap_bundle,
    import_roadmap_bundle,
    load_roadmap,
)
from learning_ext.progress.study import course_code_sort_key

logger = logging.getLogger(__name__)


class PathGeneratorPage(BasePage):
    """学习路线生成与展示页面"""

    public_events = ["onProjectCreated", "onProjectSwitched"]

    def __init__(self, app):
        super().__init__(app)
        # 当前项目 id 状态
        self.current_project_id = gr.State(None)

    def on_building_ui(self):
        gr.Markdown(
            "# 🎯 学习路线规划\n输入任意选题，AI 帮你拆解成**带依赖关系的分阶段学习路线**（知识图谱）。"
        )
        gr.Markdown(
            "> 💡 **三步上手**：① 在「⚡模型配置」填好 API Key → ② 下方输入选题点「生成路线」→ "
            "> ③ 满意后点「💾 保存并开始学习」，系统会**自动搜集资料、生成环境清单**，"
            "> 然后去「📚 学习工作台」逐个知识点推进。"
        )

        with gr.Row():
            with gr.Column(scale=3):
                self.topic_input = gr.Textbox(
                    label="选题",
                    placeholder="例如：从零学习 Transformer 原理 / 学 Rust / 准备考研数学",
                    lines=2,
                )
            with gr.Column(scale=2):
                self.background_input = gr.Textbox(
                    label="你的背景 (可选)",
                    placeholder="如：有 Python 基础，懂基本神经网络",
                    lines=2,
                )

        with gr.Row():
            self.goal_input = gr.Textbox(
                label="学习目标 (可选)",
                placeholder="如：能看懂论文、能自己实现一个小 GPT",
                scale=2,
            )
            self.hours_input = gr.Slider(
                label="每周可投入时间 (小时)",
                minimum=1,
                maximum=40,
                value=10,
                step=1,
            )

        with gr.Row():
            self.generate_btn = gr.Button("🚀 生成学习路线", variant="primary")
            self.regenerate_btn = gr.Button("🔄 重新生成")

        # ===== 显眼的保存区 (生成后才会启用) =====
        gr.Markdown("---\n### 💾 保存路线")
        gr.Markdown(
            '<span style="color:#6B7280;">生成路线后，点击下方按钮保存。保存时会自动：</span>'
            '<br><span style="color:#6B7280;">① 为每个知识点搜集学习资料要点 ② 生成学习环境配置清单（需你确认后应用）</span>'
        )
        with gr.Row():
            self.save_btn = gr.Button(
                "💾 保存并开始学习（自动搜集资料 + 配置环境）",
                variant="primary",
                size="lg",
            )
        # 保存进度（搜集资料/环境时实时显示）
        self.save_progress = gr.Markdown("")

        # 路线展示区
        self.roadmap_output = gr.Markdown(
            label="学习路线",
            value="*点击「生成学习路线」后，路线会显示在这里*",
            elem_classes=["learning-roadmap"],
        )

        # 高级：原始 JSON + 调整
        with gr.Accordion("🔧 高级：调整路线 / 查看 JSON", open=False):
            self.roadmap_json = gr.Code(language="json", label="路线 JSON")
            self.refine_input = gr.Textbox(
                label="调整意见 (自然语言)",
                placeholder="如：增加分布式训练的内容；删掉 RNN 部分；把难度调低",
            )
            self.refine_btn = gr.Button("✏️ 按意见调整路线")

        gr.Markdown("---\n### 📂 我的学习项目")
        self.project_list = gr.Dataframe(
            headers=["ID", "标题", "选题", "进度", "状态", "创建时间"],
            datatype=["number", "str", "str", "str", "str", "str"],
            interactive=False,
            value=[],
        )
        with gr.Row():
            self.refresh_btn = gr.Button("🔄 刷新项目列表")
            self.load_project_id = gr.Number(label="加载项目 ID", value=0, precision=0)
            self.load_btn = gr.Button("📂 加载该项目路线")
        with gr.Accordion("📦 导入 / 导出学习路线", open=False):
            gr.Markdown(
                "导出会生成格式化 JSON 文件，包含项目元信息和完整路线；导入会新建一个学习项目。"
            )
            with gr.Row():
                self.export_project_id = gr.Number(
                    label="导出项目 ID", value=0, precision=0
                )
                self.export_roadmap_btn = gr.Button("📤 导出学习路线")
            self.export_roadmap_file = gr.File(
                label="下载导出的学习路线 JSON", interactive=False
            )
            self.import_roadmap_file = gr.File(
                label="导入学习路线 JSON", file_types=[".json"]
            )
            self.import_roadmap_btn = gr.Button("📥 导入学习路线", variant="primary")
        with gr.Accordion("🧭 批量审计旧路线", open=False):
            gr.Markdown(
                "对已有项目执行路线完整性审计。系统会自动重写路线，并按新路线批量重新生成课程内容。"
                "可输入单个 ID、多个 ID（逗号/空格分隔），或留空审计全部项目。"
            )
            with gr.Row():
                self.audit_project_id = gr.Textbox(
                    label="项目 ID（留空=全部）",
                    placeholder="例如：3 或 3,5,8",
                    lines=1,
                )
                self.audit_confirm = gr.Textbox(
                    label="确认替换", placeholder="REPLACE", lines=1
                )
                self.audit_project_btn = gr.Button(
                    "🧭 审计并重生成该项目", variant="primary"
                )
            self.audit_project_output = gr.Markdown("")
        with gr.Accordion("🗑 删除项目", open=False):
            gr.Markdown("输入项目 ID，并输入 `DELETE` 确认后删除。")
            with gr.Row():
                self.delete_project_id = gr.Number(
                    label="删除项目 ID", value=0, precision=0
                )
                self.delete_confirm = gr.Textbox(
                    label="确认文本", placeholder="DELETE", lines=1
                )
                self.delete_btn = gr.Button("删除项目", variant="stop")

        self.status = gr.Markdown("")

    def on_register_events(self):
        """绑定按钮事件"""
        self.generate_btn.click(
            fn=self._handle_generate,
            inputs=[
                self.topic_input,
                self.background_input,
                self.goal_input,
                self.hours_input,
            ],
            outputs=[self.roadmap_output, self.roadmap_json, self.status],
        ).then(
            fn=self._refresh_projects,
            outputs=[self.project_list],
        )

        self.regenerate_btn.click(
            fn=self._handle_generate,
            inputs=[
                self.topic_input,
                self.background_input,
                self.goal_input,
                self.hours_input,
            ],
            outputs=[self.roadmap_output, self.roadmap_json, self.status],
        )

        self.refine_btn.click(
            fn=self._handle_refine,
            inputs=[self.roadmap_json, self.refine_input],
            outputs=[self.roadmap_output, self.roadmap_json, self.status],
        )

        # 保存：生成器流式输出进度 (自动搜集资料 + 生成环境清单)
        self.save_btn.click(
            fn=self._handle_save_with_setup,
            inputs=[
                self.topic_input,
                self.background_input,
                self.goal_input,
                self.hours_input,
                self.roadmap_json,
            ],
            outputs=[self.current_project_id, self.save_progress, self.status],
        ).then(
            fn=self._refresh_projects,
            outputs=[self.project_list],
        )

        self.refresh_btn.click(fn=self._refresh_projects, outputs=[self.project_list])

        self.load_btn.click(
            fn=self._handle_load,
            inputs=[self.load_project_id],
            outputs=[
                self.roadmap_output,
                self.roadmap_json,
                self.current_project_id,
                self.status,
            ],
        )
        self.export_roadmap_btn.click(
            fn=self._handle_export_roadmap,
            inputs=[self.export_project_id],
            outputs=[self.export_roadmap_file, self.status],
        )
        self.import_roadmap_btn.click(
            fn=self._handle_import_roadmap,
            inputs=[self.import_roadmap_file],
            outputs=[
                self.project_list,
                self.roadmap_output,
                self.roadmap_json,
                self.current_project_id,
                self.status,
            ],
        )
        self.delete_btn.click(
            fn=self._handle_delete_project,
            inputs=[self.delete_project_id, self.delete_confirm],
            outputs=[self.project_list, self.status],
        )
        self.audit_project_btn.click(
            fn=self._handle_audit_project,
            inputs=[self.audit_project_id, self.audit_confirm],
            outputs=[
                self.project_list,
                self.roadmap_output,
                self.roadmap_json,
                self.audit_project_output,
                self.status,
            ],
        )

    # ---- 业务处理函数 ----

    def _handle_generate(self, topic, background, goal, hours):
        """生成路线"""
        if not topic or not topic.strip():
            return "", "{}", "⚠️ 请输入选题"
        try:
            preview = generate_roadmap_preview(
                topic.strip(), background or "", goal or "", float(hours) if hours else 10.0
            )
            audited_md = self._roadmap_to_markdown(preview.roadmap)
            audit_md = self._audit_to_markdown(preview.audit)
            return (
                f"{audit_md}\n\n---\n\n{audited_md}",
                json.dumps(preview.roadmap, ensure_ascii=False, indent=2),
                "✅ 路线已生成，并已自动审计补全，可保存为项目",
            )
        except Exception as e:
            logger.exception("生成路线失败")
            return "", "{}", f"❌ 生成失败: {e}"

    def _handle_refine(self, current_json, instruction):
        """按意见调整路线"""
        if not instruction or not instruction.strip():
            return "", current_json, "⚠️ 请输入调整意见"
        try:
            current = json.loads(current_json) if current_json else {}
            refined = refine_roadmap_preview(current, instruction.strip())
            md = self._roadmap_to_markdown(refined)
            return (
                md,
                json.dumps(refined, ensure_ascii=False, indent=2),
                "✅ 路线已调整",
            )
        except Exception as e:
            logger.exception("调整路线失败")
            return "", current_json, f"❌ 调整失败: {e}"

    def _handle_save_with_setup(self, topic, background, goal, hours, roadmap_json):
        """保存为项目 + 自动搜集资料 + 生成环境清单 (生成器，流式输出进度)。

        步骤：
            1. 保存项目 + 知识点到库
            2. 生成学习环境配置清单 (落库为 Task，待用户确认)
            3. 为每个知识点生成学习摘要 (存入 description)
            4. 提示去学习工作台
        """
        if not roadmap_json or roadmap_json == "{}":
            yield None, "", "⚠️ 请先生成路线"
            return
        try:
            roadmap = json.loads(roadmap_json)
        except json.JSONDecodeError as e:
            yield None, "", f"❌ 路线 JSON 解析失败: {e}"
            return

        yield None, "⏳ 正在保存学习路线...", ""
        try:
            with Session(engine) as session:
                created = create_project(
                    session,
                    topic or "未命名选题",
                    background or "",
                    goal or "",
                    float(hours) if hours else 10.0,
                    roadmap,
                )
            progress_md = (
                f"✅ **步骤 1/3 完成**：已保存项目 #{created.project_id}「{created.title}」，"
                f"共 {created.node_count} 个知识点\n\n"
            )
            if created.environment_status == "ready":
                progress_md += "✅ **步骤 2/3 完成**：学习环境配置清单已生成\n\n"
            else:
                progress_md += f"⚠️ 环境清单生成失败（不影响学习）: {created.environment_error}\n\n"
            yield created.project_id, progress_md + "⏳ 正在准备首批教学内容...", ""
            with Session(engine) as session:
                preparation = prepare_project_content(session, created.project_id)
            pending_note = (
                f"，剩余 {len(preparation.pending_node_ids)} 节后台生成中"
                if preparation.pending_node_ids
                else ""
            )
            final_md = (
                progress_md
                + f"✅ **步骤 3/3 完成**：已生成 {len(preparation.generated_node_ids)} 节教学内容{pending_note}\n\n"
                + "---\n### 🎉 准备就绪！\n\n"
                + f"现在请点击顶部 **「📚 学习工作台」** Tab，选择项目 #{created.project_id}。"
            )
            yield created.project_id, final_md, f"✅ 项目 #{created.project_id} 已就绪，去「📚 学习工作台」开始学习吧！"
            return
        except Exception as e:
            logger.exception("保存项目失败")
            yield None, f"❌ 保存失败: {e}", ""
            return

    def _handle_load(self, project_id):
        """加载已有项目"""
        if not project_id or int(project_id) <= 0:
            return "", "{}", None, "⚠️ 请输入有效的项目 ID"
        try:
            with Session(engine) as session:
                roadmap = get_project_roadmap(session, int(project_id)).to_dict()
                md = self._roadmap_to_markdown(roadmap)
                return (
                    md,
                    json.dumps(roadmap, ensure_ascii=False, indent=2),
                    int(project_id),
                    f"✅ 已加载项目 #{int(project_id)}",
                )
        except Exception as e:
            logger.exception("加载项目失败")
            return "", "{}", None, f"❌ 加载失败: {e}"

    def _handle_export_roadmap(self, project_id):
        """导出项目学习路线为格式化 JSON 文件。"""
        if not project_id or int(project_id) <= 0:
            return None, "⚠️ 请输入有效的项目 ID"
        try:
            with Session(engine) as session:
                payload = export_roadmap_bundle(session, int(project_id))
            export_dir = Path(".tmp") / "roadmap_exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            path = export_dir / f"learning_route_{int(project_id)}.json"
            path.write_text(payload, encoding="utf-8")
            return str(path), f"✅ 已导出项目 #{int(project_id)} 的学习路线"
        except Exception as e:
            logger.exception("导出学习路线失败")
            return None, f"❌ 导出失败: {e}"

    def _handle_import_roadmap(self, file_obj):
        """导入格式化学习路线 JSON，创建新项目。"""
        if file_obj is None:
            return self._refresh_projects(), gr.update(), gr.update(), None, "⚠️ 请先选择 JSON 文件"
        try:
            path = getattr(file_obj, "name", None) or str(file_obj)
            payload = Path(path).read_text(encoding="utf-8")
            with Session(engine) as session:
                project = import_roadmap_bundle(session, payload, user_id="default")
                roadmap = load_roadmap(session, project.id)
                md = self._roadmap_to_markdown(roadmap)
                return (
                    self._refresh_projects(),
                    md,
                    json.dumps(roadmap, ensure_ascii=False, indent=2),
                    project.id,
                    f"✅ 已导入学习路线并创建项目 #{project.id}",
                )
        except Exception as e:
            logger.exception("导入学习路线失败")
            return self._refresh_projects(), gr.update(), gr.update(), None, f"❌ 导入失败: {e}"

    def _handle_delete_project(self, project_id, confirm):
        """删除项目及其学习数据"""
        if not project_id or int(project_id) <= 0:
            return self._refresh_projects(), "⚠️ 请输入有效的项目 ID"
        if (confirm or "").strip() != "DELETE":
            return self._refresh_projects(), "⚠️ 如需删除，请在确认文本中输入 DELETE"
        try:
            from learning_ext.project_ops import delete_project

            with Session(engine) as session:
                result = delete_project(session, int(project_id))
            deleted = result["deleted"]
            total = sum(deleted.values())
            return (
                self._refresh_projects(),
                f"✅ 已删除项目 #{int(project_id)}，清理 {total} 条相关数据",
            )
        except Exception as e:
            logger.exception("删除项目失败")
            return self._refresh_projects(), f"❌ 删除失败: {e}"

    def _handle_audit_project(self, project_id, confirm=""):
        """审计旧项目路线，替换路线并批量重生成课程内容。"""
        if (confirm or "").strip() != "REPLACE":
            return (
                self._refresh_projects(),
                gr.update(),
                gr.update(),
                "⚠️ 路线替换会清除既有学习数据，请输入 REPLACE 确认。",
                "⚠️ 未执行路线替换。",
            )
        try:
            project_ids = self._parse_audit_project_ids(project_id)
            with Session(engine) as session:
                if not project_ids:
                    project_ids = [
                        p.id
                        for p in session.exec(
                            select(LearningProject).order_by(LearningProject.id)
                        ).all()
                        if p.id is not None
                    ]
                if not project_ids:
                    return (
                        self._refresh_projects(),
                        gr.update(),
                        gr.update(),
                        "⚠️ 当前没有可审计的项目",
                        "⚠️ 当前没有可审计的项目",
                    )

            results = []
            last_improved = None
            last_md = ""
            for pid in project_ids:
                with Session(engine) as session:
                    project = session.get(LearningProject, pid)
                    if project is None:
                        raise ValueError(f"项目 #{pid} 不存在")
                    current = load_roadmap(session, pid)
                    audit, improved = audit_existing_roadmap(
                        roadmap=current,
                        topic=project.topic,
                        background=project.background,
                        goal=project.goal,
                        weekly_hours=project.weekly_hours,
                    )
                    replacement = replace_project_roadmap_application(
                        session, pid, improved, confirmed=True
                    )
                audit_md = self._audit_to_markdown(audit)
                md = self._roadmap_to_markdown(improved)
                results.append(
                    {
                        "project_id": pid,
                        "topic": project.topic,
                        "title": project.title,
                        "audit": audit,
                        "audit_md": audit_md,
                        "roadmap": improved,
                        "roadmap_md": md,
                        "queued": len(replacement.content_preparation.pending_node_ids),
                    }
                )
                last_improved = improved
                last_md = md

            if len(results) == 1:
                result = results[0]
                status = (
                    f"✅ 项目 #{result['project_id']} 已完成路线审计并替换路线。"
                    f"课程内容已排队强制重生成：{result['queued']} 节。"
                )
                return (
                    self._refresh_projects(),
                    f"{result['audit_md']}\n\n---\n\n{result['roadmap_md']}",
                    json.dumps(result["roadmap"], ensure_ascii=False, indent=2),
                    result["audit_md"],
                    status,
                )

            total_queued = sum(r["queued"] for r in results)
            summary_lines = ["## 🧭 批量路线审计结果"]
            for result in results:
                audit = result["audit"] or {}
                summary_lines.append(
                    f"- 项目 #{result['project_id']} {result['topic']}："
                    f"评分 {audit.get('score', '未知')}，"
                    f"结论 {audit.get('verdict', '未知')}，已排队 {result['queued']} 节"
                )
            audit_report = "\n\n".join(
                [
                    f"### 项目 #{result['project_id']}\n\n{result['audit_md']}"
                    for result in results
                ]
            )
            roadmap_md = "\n\n---\n\n".join(
                [
                    "\n".join(summary_lines),
                    last_md or "*路线为空*",
                ]
            )
            payload = {
                "projects": [
                    {
                        "project_id": result["project_id"],
                        "audit": result["audit"],
                        "roadmap": result["roadmap"],
                    }
                    for result in results
                ],
                "last_roadmap": last_improved,
            }
            id_list = ", ".join(f"#{result['project_id']}" for result in results)
            status = (
                f"✅ 已完成 {len(results)} 个项目（{id_list}）的路线审计和替换，"
                f"课程内容已排队强制重生成：{total_queued} 节。"
            )
            return (
                self._refresh_projects(),
                roadmap_md,
                json.dumps(payload, ensure_ascii=False, indent=2),
                audit_report,
                status,
            )
        except Exception as e:
            logger.exception("项目路线审计失败")
            return (
                self._refresh_projects(),
                gr.update(),
                gr.update(),
                f"❌ 审计失败: {e}",
                f"❌ 审计失败: {e}",
            )

    @staticmethod
    def _parse_audit_project_ids(project_id) -> list[int]:
        if project_id is None:
            return []
        if isinstance(project_id, (int, float)):
            value = int(project_id)
            return [value] if value > 0 else []
        raw = str(project_id).strip()
        if not raw or raw in {"0", "0.0"}:
            return []
        for sep in [",", "，", ";", "；", "\n", "\t"]:
            raw = raw.replace(sep, " ")
        ids: list[int] = []
        for part in raw.split():
            value = int(float(part))
            if value > 0 and value not in ids:
                ids.append(value)
        return ids

    def _refresh_projects(self):
        """刷新项目列表"""
        try:
            with Session(engine) as session:
                projects = list_projects(session)
                rows = []
                for p in projects:
                    rows.append(
                        [
                            p.id,
                            p.title,
                            p.topic[:40],
                            f"{p.progress['done']}/{p.progress['total']} ({p.progress['pct']}%)",
                            p.status,
                            p.created_at.strftime("%Y-%m-%d %H:%M"),
                        ]
                    )
                return rows
        except Exception:
            return []

    @staticmethod
    def _audit_to_markdown(audit: dict) -> str:
        if not audit:
            return "## 🧭 路线审计\n\n*审计结果为空，已保留生成路线。*"
        lines = [
            "## 🧭 路线自动审计",
            f"- **评分**：{audit.get('score', '未知')}",
            f"- **结论**：{audit.get('verdict', '未知')}",
        ]
        problems = audit.get("problems") or []
        if problems:
            lines.append("\n### 发现的问题")
            lines.extend(f"- {p}" for p in problems)
        changes = audit.get("changes") or []
        if changes:
            lines.append("\n### 自动改动")
            lines.extend(f"- {c}" for c in changes)
        return "\n".join(lines)

    @staticmethod
    def _roadmap_to_markdown(roadmap: dict) -> str:
        """把路线 JSON 转成 markdown (含 markmap mindmap 语法，Kotaemon 自动渲染)"""
        if not roadmap or "nodes" not in roadmap:
            return "*路线为空*"

        lines = [f"# {roadmap.get('summary', '学习路线')}\n"]

        # 按 stage 分组
        stages: dict[str, list] = {}
        for node in roadmap.get("nodes", []):
            stages.setdefault(node.get("stage", "base"), []).append(node)

        stage_names = {
            "base": "🌱 基础阶段",
            "strengthen": "💪 强化阶段",
            "sprint": "🔥 冲刺阶段",
        }

        for stage_key in ["base", "strengthen", "sprint"]:
            nodes = stages.get(stage_key, [])
            if not nodes:
                continue
            lines.append(f"## {stage_names.get(stage_key, stage_key)}\n")
            for node in sorted(
                nodes, key=lambda x: course_code_sort_key(x.get("code", ""))
            ):
                mastery_pct = ""
                if "mastery" in node:
                    mastery_pct = f" _(掌握 {node['mastery']:.0%})_"
                status_icon = {
                    "mastered": "✅",
                    "reviewing": "🔄",
                    "learning": "📖",
                    "weak": "⚠️",
                    "pending": "⏳",
                }.get(node.get("status", "pending"), "⏳")
                prereq = node.get("prerequisites", [])
                prereq_str = f" `需先学: {','.join(prereq)}`" if prereq else ""
                lines.append(
                    f"- {status_icon} **[{node['code']}] {node['title']}** "
                    f"`{node.get('est_hours', 2)}h` `难度{node.get('difficulty', 3)}/5`"
                    f"{prereq_str}{mastery_pct}"
                )
                if node.get("description"):
                    lines.append(f"  - {node['description']}")
            lines.append("")

        lines.append("---")
        lines.append(
            f"_共 {len(roadmap.get('nodes', []))} 个知识点 · "
            f"预估 {sum(n.get('est_hours', 0) for n in roadmap.get('nodes', []))} 小时_"
        )
        return "\n".join(lines)

    def as_gradio_component(self):
        return self.current_project_id
