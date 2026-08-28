"""学习推进 service：知识点状态机、学习摘要生成、下一个可学节点。"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from sqlmodel import Session, select

from learning_ext.db.models import (
    KnowledgeEdge,
    KnowledgeNode,
    LearningProject,
    Task,
)
from learning_ext.llm import chat

logger = logging.getLogger(__name__)

# 状态机
STATUS_PENDING = "pending"
STATUS_LEARNING = "learning"
STATUS_MASTERED = "mastered"
STATUS_WEAK = "weak"
STATUS_SKIPPED = "skipped"

# 允许的状态转移
_VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_LEARNING,
    STATUS_MASTERED,
    STATUS_WEAK,
    STATUS_SKIPPED,
}

PRACTICE_KEYWORDS = (
    "微调",
    "fine-tune",
    "finetune",
    "训练",
    "部署",
    "api",
    "sdk",
    "数据集",
    "实操",
    "实践",
    "项目",
    "推理",
    "评估",
    "代码",
    "workflow",
    "pipeline",
)


def course_code_sort_key(code: str) -> tuple:
    """Sort course codes by numeric segments, e.g. 2.10 after 2.9."""
    parts = re.split(r"([0-9]+)", str(code or ""))
    key = []
    for part in parts:
        if part == "":
            continue
        key.append((0, int(part)) if part.isdigit() else (1, part.lower()))
    return tuple(key)


def sort_nodes_by_code(nodes: List[KnowledgeNode]) -> List[KnowledgeNode]:
    return sorted(nodes, key=lambda node: course_code_sort_key(node.code))


def set_node_status(session: Session, node_id: int, status: str) -> KnowledgeNode:
    """更新知识点状态。"""
    if status not in _VALID_STATUSES:
        raise ValueError(f"非法状态: {status}，允许: {_VALID_STATUSES}")
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise ValueError(f"知识点 {node_id} 不存在")
    node.status = status
    session.commit()
    session.refresh(node)
    return node


def get_next_learnable_nodes(
    session: Session, project_id: int, limit: int = 5
) -> List[KnowledgeNode]:
    """获取下一个可学的知识点（前置依赖已掌握/跳过的节点，且自身未掌握）。"""
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    edges = session.exec(
        select(KnowledgeEdge).where(KnowledgeEdge.project_id == project_id)
    ).all()

    # 节点 id -> 已完成状态
    done = {n.id for n in nodes if n.status in (STATUS_MASTERED, STATUS_SKIPPED)}
    # 节点 id -> 前置依赖 id 列表
    deps: dict[int, list[int]] = {}
    for e in edges:
        deps.setdefault(e.source_id, []).append(e.target_id)

    learnable: List[KnowledgeNode] = []
    # 先取"学习中"的
    ordered_nodes = sort_nodes_by_code(list(nodes))
    learning = [n for n in ordered_nodes if n.status == STATUS_LEARNING]
    learnable.extend(learning)
    # 再取"待学且依赖已满足"的
    for n in ordered_nodes:
        if n.status != STATUS_PENDING:
            continue
        prereqs = deps.get(n.id, [])
        if all(p in done for p in prereqs):
            learnable.append(n)
        if len(learnable) >= limit:
            break
    # 去重保序
    seen = set()
    out = []
    for n in learnable:
        if n.id not in seen:
            seen.add(n.id)
            out.append(n)
        if len(out) >= limit:
            break
    return out


def get_project_progress(session: Session, project_id: int) -> dict:
    """项目进度统计。"""
    nodes = session.exec(
        select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
    ).all()
    total = len(nodes)
    if total == 0:
        return {"total": 0, "done": 0, "learning": 0, "pending": 0, "pct": 0.0}
    done = sum(1 for n in nodes if n.status == STATUS_MASTERED)
    learning = sum(1 for n in nodes if n.status == STATUS_LEARNING)
    pending = sum(1 for n in nodes if n.status == STATUS_PENDING)
    weak = sum(1 for n in nodes if n.status == STATUS_WEAK)
    skipped = sum(1 for n in nodes if n.status == STATUS_SKIPPED)
    return {
        "total": total,
        "done": done,
        "learning": learning,
        "pending": pending,
        "weak": weak,
        "skipped": skipped,
        "pct": round(done / total * 100, 1),
    }


def generate_node_summary(
    node: KnowledgeNode,
    project_topic: str,
    *,
    learning_goal: str = "",
    environment_context: str = "",
    model_name: Optional[str] = None,
) -> str:
    """为单个知识点生成完整、充实的多级笔记式教学内容。

    要求 AI 产出一份可以直接当教材用的、结构化的、内容详尽的 Markdown 笔记，
    而不是简短的摘要。包含概念、原理、示例、代码、对比、易错点、练习。
    """
    prompt = f"""你正在为一门「{project_topic}」的课程编写**第 {node.code} 节课的完整教学内容**。
这节课题目是「{node.title}」。

请像一位资深讲师那样，写出一份**详尽、系统、可直接用于自学**的课程笔记。
目标读者：{f"难度{node.difficulty}/5 的学习者（" + ("零基础" if node.difficulty <= 2 else "有一定基础" if node.difficulty <= 3 else "进阶") + "）"}
学习目标：{learning_goal or "掌握该主题的核心知识并能应用到真实任务"}
建议学时：{node.est_hours} 小时
知识点定位：{node.description or "（本节核心内容，请自行展开）"}
环境配置上下文：
{environment_context or "未提供具体环境清单。请根据学习主题和本节内容自行给出可落地的最小环境假设。"}

# 输出要求（严格遵守）

**必须**输出一份**多级结构**的 Markdown 笔记，包含以下所有章节（缺一不可）。
每个章节都要**充实展开**，不能只有一两句话敷衍。

---

## 📌 本节导览
（用 3-5 行说明：这节课学什么、为什么重要、学完能做什么、和前后课的衔接）

## 🎯 学习目标
（用 bullet 列出 3-5 条本节课结束后学习者应该掌握的具体能力，每条用可验证的动词开头，如"能解释..."、"能写出..."、"能区分..."）

## 🧠 核心概念详解
### 概念引入
（从生活/已知场景类比引入，让读者建立直觉。**至少 150 字**）
### 正式定义
（给出严谨的定义/概念，用 > 引用块标注关键定义。**至少 100 字**）
### 为什么需要它
（说明这个知识点解决什么问题、它的价值。**至少 100 字**）

## 📖 知识点深入
（这是本节的主体。把这个知识点拆解成 3-5 个子主题，每个子主题用 ### 小标题。
每个子主题都要包含：解释 + 示例 + （如适用）代码/公式/图表描述。
**这是最重要的部分，总篇幅至少 600 字**）

### 子主题 1
（详细讲解...）

### 子主题 2
（详细讲解...）

### ...

## 💻 代码示例 / 实操
这一节必须从“配置好环境以后，学习者马上能做什么”出发，而不是为了凑篇幅写一段单纯计算数据的小代码。

如果主题涉及编程、AI 工具、开发环境、数据分析、自动化、模型调用或任何可操作工具：
- 必须给出 2-3 个**真实可运行**的实操代码/命令，每个示例都要服务于本节课题和学习目标。
- 必须显式写出运行前提、文件名、安装命令、启动命令、环境变量或本地服务地址。
- 必须围绕本节课程内容设计任务，不得只写 1+1、随机数、玩具加法器、纯粹循环打印等脱离课程目标的示例。
- 如果学习主题或环境配置中出现 LM Studio，必须给出 OpenAI Compatible Server 的调用示例，并使用 `http://localhost:1234/v1`。
- 如果学习主题或环境配置中出现 Ollama，必须给出 Ollama HTTP API 或 Python SDK 调用示例，并使用 `http://localhost:11434`。
- 每段代码后写“这段代码验证了什么”和“常见报错怎么排查”。

如果主题不适合写代码，也必须给出 2 个可执行的实操任务/分析模板/练习流程，用清单或伪代码呈现。

## ⚖️ 对比与辨析
（用表格或对比的方式，把本节概念与相关/易混概念区分清楚）

| 方面 | 概念A | 概念B |
|------|-------|-------|
| ... | ... | ... |

## ⚠️ 常见误区与陷阱
（列出 3-5 个初学者**最容易犯的错**，每个误区用 ❌ 标记错误做法，✅ 标记正确做法，并解释原因）

## 🔑 关键要点速记
（用简洁的 bullet 把本节**必须记住**的要点列出来，5-8 条，方便复习）

## 📝 自测练习
（出 3-5 道题让学习者自测，题型：选择/填空/简答/实操 混合。附上答案或解题思路，用折叠或单独段落给出）

## 🚀 拓展提升
（对想深入的学习者，推荐 2-3 个进阶方向、扩展阅读、关联知识点）

## 🔗 衔接下一节
（简述本节内容如何衔接到后续课程，2-3 句）

---

# 写作规范
1. **使用真实的、具体的内容**，不要写"这里应该写XX""此处省略"之类的占位文字
2. **多用示例**：抽象概念配具体例子，例子要贴切且完整
3. **多级标题**：用 ## ### #### 建立层次，让笔记结构清晰
4. **善用 Markdown 元素**：代码块、表格、引用、加粗、emoji 标记重点
5. **篇幅**：本节内容总篇幅应在 **2000-4000 字**，宁可详细也不要简略
6. **语气**：像朋友讲解，平实准确，避免空话套话
7. 如果知识点确实简单（如基础概念），也要通过**丰富的例子和练习**充实内容，而不是敷衍

直接输出 Markdown 内容，不要任何前言或解释。"""

    return chat(
        prompt,
        system=(
            "你是一位顶级的技术讲师和教材作者。你的笔记以"
            "结构清晰、内容详实、例子丰富、循序渐进著称。"
            "你从不敷衍，每个知识点都讲到学习者真正能理解、能上手为止。"
            "你输出的内容会被直接渲染成教学页面，所以必须用规范的 Markdown 格式。"
        ),
        model_name=model_name,
        temperature=0.5,
        max_tokens=4000,
    )


def is_practice_heavy_node(node: KnowledgeNode, project_topic: str = "") -> bool:
    """Return whether a node deserves a separate practical lesson."""
    if int(node.difficulty or 0) >= 4:
        return True
    if float(node.est_hours or 0) >= 3:
        return True
    haystack = " ".join(
        [
            project_topic or "",
            node.title or "",
            node.description or "",
            node.stage or "",
        ]
    ).lower()
    return any(keyword in haystack for keyword in PRACTICE_KEYWORDS)


def get_practice_task(session: Session, node_id: int) -> Optional[Task]:
    return session.exec(
        select(Task)
        .where(Task.node_id == node_id)
        .where(Task.task_type == "practice")
        .order_by(Task.id.desc())
    ).first()


def generate_practice_lesson(
    node: KnowledgeNode,
    project_topic: str,
    *,
    learning_goal: str = "",
    environment_context: str = "",
    model_name: Optional[str] = None,
) -> str:
    """Generate a separate hands-on lesson for a practice-heavy node."""
    prompt = f"""你正在为「{project_topic}」课程的「{node.title} ({node.code})」编写一份**单独的实操课程**。

这不是概念课件，而是学习者可以跟着一步一步做完的实操流程。

【学习目标】{learning_goal or "完成一个能验证本知识点的真实小实验"}
【难度】{node.difficulty}/5
【建议学时】{node.est_hours} 小时
【课程说明】
{(node.description or "请根据标题和主题设计实操。")[:1800]}

【环境上下文】
{environment_context or "未提供环境清单。请给出最小可运行环境，并明确假设。"}

请输出 Markdown，必须包含：

## 实操目标
- 本实操要完成什么可验证成果

## 前置条件
- 软件、账号、模型、数据、硬件、环境变量
- 安装命令和版本建议

## 项目目录结构
用代码块给出目录树。

## 完整流程
按步骤写清楚，每一步包含目的、命令或代码、预期输出。

## 关键代码
给出可以复制运行的代码。若主题是模型微调，必须包含：
- 数据集样例或数据格式
- 训练脚本
- 启动命令
- 保存/加载模型
- 简单评估或推理验证

## 验收标准
- 学习者如何判断自己做成了

## 常见报错与排查
- 至少 5 个具体错误、原因和修复方法

## 延伸任务
- 2-3 个进阶练习

要求：
1. 不要写占位符，不要说“按需替换”而不给例子。
2. 代码和命令必须服务于当前课程，不要写玩具示例。
3. 如果需要外部 API Key，要给出本地替代方案或 mock 方案。
4. 直接输出 Markdown。"""
    return chat(
        prompt,
        system="你是资深工程实践导师，会把抽象课程转成可执行项目、流程代码和验收标准。",
        model_name=model_name,
        temperature=0.35,
        max_tokens=3500,
    )


def _save_practice_task(
    session: Session, node: KnowledgeNode, content: str, *, force: bool = False
) -> Task:
    existing = get_practice_task(session, node.id)
    if existing and not force:
        return existing
    if existing:
        existing.description = content
        existing.title = f"🧪 实操课程：{node.title}"
        existing.status = "pending"
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    task = Task(
        project_id=node.project_id,
        node_id=node.id,
        title=f"🧪 实操课程：{node.title}",
        description=content,
        task_type="practice",
        status="pending",
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def generate_practice_lesson_to_db(
    node_id: int,
    project_topic: str,
    *,
    force: bool = False,
    learning_goal: str = "",
    environment_context: str = "",
    engine=None,
) -> bool:
    """Generate and persist a practical lesson for a node."""
    try:
        if engine is None:
            from ktem.db.engine import engine as _engine

            engine = _engine

        with Session(engine) as session:
            node = session.get(KnowledgeNode, node_id)
            if not node:
                return False
            if get_practice_task(session, node.id) and not force:
                return True
            if not learning_goal or not environment_context:
                project = session.get(LearningProject, node.project_id)
                if project and not learning_goal:
                    learning_goal = project.goal or ""
                if not environment_context:
                    env_task = session.exec(
                        select(Task)
                        .where(Task.project_id == node.project_id)
                        .where(Task.task_type == "env")
                        .order_by(Task.id.desc())
                    ).first()
                    if env_task:
                        environment_context = env_task.description
            content = generate_practice_lesson(
                node,
                project_topic,
                learning_goal=learning_goal,
                environment_context=environment_context,
            )
            _save_practice_task(session, node, content, force=force)
            return True
    except Exception as e:
        logger.warning(f"生成实操课程失败 (node {node_id}): {e}")
        return False


def generate_env_checklist(
    project_topic: str,
    background: str = "",
    *,
    model_name: Optional[str] = None,
) -> str:
    """为学习主题生成环境配置清单（Markdown）。

    返回包含软件/工具/账号/硬件需求的清单，供用户确认。
    """
    prompt = f"""请为以下学习主题生成一份环境配置清单（Markdown 格式）。

【学习主题】{project_topic}
【学习者背景】{background or "未知"}

判断这个主题是否需要配置开发/学习环境：
- 如果是编程/工具/实验类主题：给出具体的环境配置清单
- 如果是理论/文科类主题：说明"无需特殊环境配置"，给出学习工具建议即可

环境清单格式（如适用）：

## 需要安装的软件
| 软件 | 用途 | 安装方式 | 必要性 |
|------|------|----------|--------|
| ... | ... | ... | 必装/选装 |

## 需要注册的账号
- ...

## 硬件要求
- ...

## 首次配置步骤
1. ...
2. ...

## 学习工具建议
- 笔记软件、练习环境等

要求：具体可执行，命令用代码块。总长度 400 字以内。"""
    return chat(
        prompt,
        system="你是一位务实的导师，只推荐真正必要的环境配置，避免让初学者陷入装环境的泥潭。",
        model_name=model_name,
        temperature=0.3,
    )


def save_env_tasks(
    session: Session,
    project_id: int,
    env_markdown: str,
) -> List[Task]:
    """把环境配置清单落库为 Task（env 类型）。"""
    # 清理旧的 env 任务
    old = session.exec(
        select(Task).where(Task.project_id == project_id).where(Task.task_type == "env")
    ).all()
    for t in old:
        session.delete(t)
    # 仅保存为一个汇总任务（Markdown 描述）
    t = Task(
        project_id=project_id,
        node_id=None,
        title="🔧 学习环境配置清单",
        description=env_markdown,
        task_type="env",
        status="pending",
    )
    session.add(t)
    session.commit()
    return [t]


# ============== 教学内容预生成 / 后台增量生成 ==============


def get_nodes_without_content(
    session: Session, project_id: int, limit: int = 50
) -> List[KnowledgeNode]:
    """获取还没有教学内容（description 为空/无效）的节点，按 code 排序。"""
    nodes = session.exec(
        select(KnowledgeNode)
        .where(KnowledgeNode.project_id == project_id)
    ).all()
    result = []
    for n in sort_nodes_by_code(list(nodes)):
        if not is_content_valid(n.description):
            result.append(n)
        if len(result) >= limit:
            break
    return result


def generate_node_summary_to_db(
    node_id: int,
    project_topic: str,
    *,
    force: bool = False,
    learning_goal: str = "",
    environment_context: str = "",
    engine=None,
) -> bool:
    """为单个节点生成教学内容并落库 (可在后台线程调用, 自建独立 session)。

    已有有效内容的节点默认会跳过；force=True 时无条件重新生成。
    Returns:
        True 成功/已存在, False 失败
    """
    try:
        if engine is None:
            from ktem.db.engine import engine as _engine

            engine = _engine

        with Session(engine) as s:
            node = s.get(KnowledgeNode, node_id)
            if not node:
                return False
            # 用 is_content_valid 判断是否已有有效内容 (避免跳过路线生成时的简短描述)
            if is_content_valid(node.description) and not force:
                return True
            if not learning_goal or not environment_context:
                project = s.get(LearningProject, node.project_id)
                if project and not learning_goal:
                    learning_goal = project.goal or ""
                if not environment_context:
                    env_task = s.exec(
                        select(Task)
                        .where(Task.project_id == node.project_id)
                        .where(Task.task_type == "env")
                        .order_by(Task.id.desc())
                    ).first()
                    if env_task:
                        environment_context = env_task.description
            summary = generate_node_summary(
                node,
                project_topic,
                learning_goal=learning_goal,
                environment_context=environment_context,
            )
            node.description = summary
            s.add(node)
            s.commit()
            if is_practice_heavy_node(node, project_topic):
                try:
                    generate_practice_lesson_to_db(
                        node.id,
                        project_topic,
                        learning_goal=learning_goal,
                        environment_context=environment_context,
                        engine=engine,
                    )
                except Exception as e:
                    logger.warning(f"自动生成实操课程失败 (node {node_id}): {e}")
        return True
    except Exception as e:
        logger.warning(f"后台生成教学内容失败 (node {node_id}): {e}")
        return False


def generate_summaries_background(
    project_id: int,
    project_topic: str,
    node_ids: List[int],
    max_workers: int = 3,
    *,
    force: bool = False,
    learning_goal: str = "",
    environment_context: str = "",
) -> None:
    """启动后台 daemon 线程池, 并发生成教学内容 (不阻塞 UI)。

    Args:
        max_workers: 并发数, 默认 3 (平衡速度和 API 限流)
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _worker():
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    generate_node_summary_to_db,
                    nid,
                    project_topic,
                    force=force,
                    learning_goal=learning_goal,
                    environment_context=environment_context,
                ): nid
                for nid in node_ids
            }
            done = 0
            total = len(node_ids)
            for fut in as_completed(futures):
                done += 1
                nid = futures[fut]
                try:
                    ok = fut.result()
                    logger.info(
                        f"[后台内容生成] {done}/{total} node#{nid} {'OK' if ok else 'FAIL'}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[后台内容生成] {done}/{total} node#{nid} 异常: {e}"
                    )

    t = threading.Thread(target=_worker, daemon=True, name=f"bg-content-{project_id}")
    t.start()
    logger.info(
        f"已启动后台教学内容生成: project {project_id}, {len(node_ids)} 节, {max_workers} 并发"
    )


def is_content_valid(description: Optional[str]) -> bool:
    """判断教学内容是否有效 (非空、非占位符、非测试垃圾、足够长)。"""
    if not description:
        return False
    d = description.strip()
    if len(d) < 100:
        return False
    # 排除测试垃圾 / 占位符
    garbage_markers = ["模拟的 LLM", "该知识点暂无", "*暂无", "这是模拟"]
    if any(g in d for g in garbage_markers):
        return False
    # 超过 500 字的就算有效 (LLM 可能格式不完美但内容充实)
    if len(d) >= 500:
        return True
    # 短内容需要有 Markdown 结构 (至少 2 个二级标题)
    if d.count("\n## ") + (1 if d.startswith("## ") else 0) >= 2:
        return True
    return False


def regenerate_all_content(
    project_id: Optional[int] = None,
    *,
    force: bool = False,
) -> dict:
    """批量重新生成教学内容。

    Args:
        project_id: 指定项目, None 则全部项目
        force: True 强制重新生成所有 (含已有的); False 只生成无效/缺失的
    Returns:
        {"total": N, "queued": M, "skipped": K, "details": [...]}
    """
    from ktem.db.engine import engine as _engine

    result = {"total": 0, "queued": 0, "skipped": 0, "details": []}
    with Session(_engine) as session:
        stmt = select(KnowledgeNode)
        if project_id is not None:
            stmt = stmt.where(KnowledgeNode.project_id == project_id)
        nodes = session.exec(stmt).all()
        nodes = sorted(
            list(nodes),
            key=lambda n: (n.project_id, course_code_sort_key(n.code)),
        )

        # 按项目分组, 同项目共用 topic
        proj_topics: dict[int, str] = {}
        to_regen: list[tuple[int, int]] = []  # (project_id, node_id)
        for n in nodes:
            result["total"] += 1
            if n.project_id not in proj_topics:
                proj = session.get(LearningProject, n.project_id)
                proj_topics[n.project_id] = proj.topic if proj else ""
            need = force or not is_content_valid(n.description)
            if need:
                to_regen.append((n.project_id, n.id))
                result["queued"] += 1
                result["details"].append(
                    {
                        "project_id": n.project_id,
                        "code": n.code,
                        "title": n.title,
                        "action": "regenerate",
                    }
                )
            else:
                result["skipped"] += 1

    # 按项目分组启动后台生成
    by_project: dict[int, list[int]] = {}
    for pid, nid in to_regen:
        by_project.setdefault(pid, []).append(nid)
    for pid, nids in by_project.items():
        generate_summaries_background(pid, proj_topics.get(pid, ""), nids, force=force)

    logger.info(
        f"批量重生成: 共 {result['total']} 节, 排队 {result['queued']} 节, "
        f"跳过 {result['skipped']} 节"
    )
    return result


def add_node(
    session: Session,
    project_id: int,
    title: str,
    description: str = "",
    stage: str = "base",
    code: str = "",
    difficulty: int = 3,
    est_hours: float = 2.0,
) -> KnowledgeNode:
    """向已有项目添加一个自定义知识点。

    如果不提供 code, 自动取项目最大 code +1。
    """
    if not code:
        existing = session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
        ).all()
        # 取最大的 code 数字部分 +1
        max_num = 0
        for n in existing:
            parts = n.code.split(".")
            try:
                num = int(parts[-1])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
        # 阶段前缀
        stage_prefix = {"base": "1", "strengthen": "2", "sprint": "3"}.get(stage, "1")
        code = f"{stage_prefix}.{max_num + 1}"

    node = KnowledgeNode(
        project_id=project_id,
        code=code,
        title=title.strip(),
        description=description.strip(),
        stage=stage,
        est_hours=float(est_hours),
        difficulty=int(difficulty),
        mastery=0.0,
        status=STATUS_PENDING,
    )
    session.add(node)
    session.commit()
    session.refresh(node)
    logger.info(f"已添加知识点 [{code}] {title} 到项目 {project_id}")
    return node
