"""导出模块：导出 Anki 牌组 / Markdown 笔记 / PDF 学习报告。"""

from __future__ import annotations

import io
import html
import zipfile
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlmodel import select

from learning_ext.db.models import (
    Card,
    KnowledgeNode,
    LearningProject,
    QuizAttempt,
    QuizQuestion,
    ReviewLog,
)
from learning_ext.progress.service import get_project_overview
from learning_ext.progress.study import sort_nodes_by_code


def export_anki_apkg(session: Session, project_id: int) -> bytes:
    """导出 Anki .apkg 牌组 (简化版：生成可导入 Anki 的 TSV + 媒体 zip)。

    Anki 原生 .apkg 是 SQLite 二进制较复杂，这里生成 Anki 可直接导入的
    "文本分隔符"格式 + 打包成 zip。用户在 Anki 里 文件→导入 即可。
    """
    cards = session.exec(select(Card).where(Card.project_id == project_id)).all()

    # Anki TSV 格式: 正面<TAB>背面<TAB>标签
    lines = ["#separator:tab\n#html:true\n"]
    for c in cards:
        tags = f"project_{project_id}"
        if c.node_id:
            tags += f" node_{c.node_id}"
        line = f"{c.front}\t{c.back}\t{tags}\n"
        lines.append(line)

    tsv_content = "".join(lines)

    # 打包成 zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"project_{project_id}_cards.txt", tsv_content)
        zf.writestr(
            "README.txt",
            "在 Anki 中：文件 → 导入 → 选择 txt 文件。\n"
            "分隔符选 Tab，字段映射：1=正面, 2=背面, 3=标签。\n",
        )
    return buf.getvalue()


def export_markdown(session: Session, project_id: int) -> str:
    """导出完整学习笔记 Markdown。"""
    project = session.get(LearningProject, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    nodes = sort_nodes_by_code(list(nodes))
    cards = session.exec(select(Card).where(Card.project_id == project_id)).all()

    md = f"# {project.title}\n\n"
    md += f"> **选题**: {project.topic}\n\n"
    md += f"> **目标**: {project.goal}\n\n"
    md += f"> **导出时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n\n"
    md += "---\n\n"

    # 知识图谱
    md += "## 知识图谱\n\n"
    overview = get_project_overview(session, project_id)
    md += (
        f"- 知识点总数: {overview['total']}\n"
        f"- 已掌握: {overview['mastered']} ({overview['mastered_pct']:.0%})\n"
        f"- 平均掌握度: {overview['avg_mastery']:.0%}\n"
        f"- 预计总时长: {overview['total_hours']:.1f} 小时\n\n"
    )

    # 各知识点
    md += "## 知识点详情\n\n"
    for n in nodes:
        status_emoji = {
            "mastered": "✅",
            "reviewing": "🔄",
            "learning": "📖",
            "weak": "⚠️",
            "pending": "⏳",
        }.get(n.status, "⏳")
        md += f"### {status_emoji} [{n.code}] {n.title}\n\n"
        md += f"- 阶段: {n.stage} | 难度: {n.difficulty}/5 | 掌握度: {n.mastery:.0%}\n"
        md += f"- 预计学时: {n.est_hours}h\n\n"
        if n.description:
            md += f"{n.description}\n\n"

        # 该节点的卡片
        node_cards = [c for c in cards if c.node_id == n.id]
        if node_cards:
            md += "**复习卡片**:\n\n"
            for c in node_cards:
                md += f"- **Q**: {c.front}\n  **A**: {c.back}\n\n"
        md += "---\n\n"

    return md


def export_progress_report(session: Session, project_id: int) -> str:
    """导出 PDF 友好的学习进度报告 (HTML 格式，可浏览器打印为 PDF)。"""
    project = session.get(LearningProject, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    nodes = sort_nodes_by_code(list(nodes))
    overview = get_project_overview(session, project_id)

    def _escape_html(value: object) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    esc = _escape_html
    report_html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>学习报告 - {esc(project.title)}</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333; }}
h1 {{ border-bottom: 3px solid #4F46E5; padding-bottom: 10px; }}
.print-note {{ padding: 10px 12px; background: #EEF2FF; border-left: 4px solid #4F46E5; }}
.metric {{ display: inline-block; background: #F3F4F6; padding: 12px 20px; margin: 5px; border-radius: 8px; }}
.metric .val {{ font-size: 24px; font-weight: bold; color: #4F46E5; }}
.node {{ margin: 12px 0; padding: 12px; border-left: 4px solid #ddd; background: #fafafa; }}
.node.mastered {{ border-color: #10B981; }}
.node.weak {{ border-color: #EF4444; }}
.bar {{ height: 8px; background: #E5E7EB; border-radius: 4px; margin-top: 4px; }}
.bar > div {{ height: 100%; background: #4F46E5; border-radius: 4px; }}
@media print {{ body {{ margin: 0; max-width: none; }} .print-note {{ display: none; }} }}
</style></head><body>
<h1>📊 学习进度报告</h1>
<p class="print-note">这是 HTML 学习报告。请使用浏览器的“打印”功能，并选择“另存为 PDF”保存。</p>
<p><strong>{esc(project.title)}</strong></p>
<p>选题：{esc(project.topic)}</p>

<div>
  <div class="metric"><div class="val">{overview["total"]}</div>知识点</div>
  <div class="metric"><div class="val">{overview["mastered"]}</div>已掌握</div>
  <div class="metric"><div class="val">{overview["mastered_pct"]:.0%}</div>完成率</div>
  <div class="metric"><div class="val">{overview["avg_mastery"]:.0%}</div>平均掌握</div>
</div>

<h2>知识点掌握详情</h2>
"""
    for n in nodes:
        report_html += f"""<div class="node {esc(n.status)}">
  <strong>[{esc(n.code)}] {esc(n.title)}</strong>
  <span style="float:right;color:#888">{esc(n.status)}</span>
  <div class="bar"><div style="width:{n.mastery * 100:.0f}%"></div></div>
  <small>掌握度 {n.mastery:.0%} | 难度 {n.difficulty}/5 | {n.est_hours}h</small>
</div>
"""
    report_html += f"\n<p style='text-align:center;color:#999;margin-top:40px;'>生成于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} | 学习 Agent</p>\n"
    report_html += "</body></html>"
    return report_html
