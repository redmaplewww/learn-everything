"use client";

import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Plus,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  apiUrl,
  getProjectRoadmap,
  getProjectWorkspace,
  generateNodeContent,
  generateNodeResources,
  generatePracticeLesson,
  getNodeDetail,
  getDueCards,
  generateQuiz,
  getDashboard,
  listProjects,
  saveNodeNote,
  submitReview,
  submitQuizAnswer,
  updateNodeStatus,
  type ProjectRoadmap,
  type ProjectSummary,
  type ProjectWorkspace,
  type NodeDetail,
  type WorkspaceNode,
  type ReviewCard,
  type QuizAnswer,
  type QuizGeneration,
  type Dashboard,
} from "../lib/api";
import { RoadmapCreation } from "../features/roadmap/RoadmapCreation";
import { RagChatPanel } from "../features/chat/RagChatPanel";
import { ModelConfigurationPanel } from "../features/configuration/ModelConfigurationPanel";
import { MarkdownContent } from "../features/markdown/MarkdownContent";
import { ResourceLibraryPanel } from "../features/resources/ResourceLibraryPanel";

type LoadState = "idle" | "loading" | "ready" | "error";
type WorkspaceTab = "dashboard" | "roadmap" | "review" | "rag" | "quiz" | "models";

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "dashboard", label: "学习概览" },
  { id: "roadmap", label: "学习路线" },
  { id: "review", label: "到期复习" },
  { id: "rag", label: "RAG 问答" },
  { id: "quiz", label: "查漏测验" },
  { id: "models", label: "模型配置" },
];

const statusLabels: Record<string, string> = {
  pending: "待开始",
  learning: "学习中",
  mastered: "已掌握",
  weak: "需复习",
  skipped: "已跳过",
};

function formatError(error: unknown) {
  if (error instanceof ApiError) {
    return error.requestId ? `${error.message}（请求编号：${error.requestId}）` : error.message;
  }
  return "无法连接本地学习服务，请确认 FastAPI 已启动。";
}

function nodePreview(description: string) {
  const plainText = description.replace(/^#{1,6}\s+/gm, "").replace(/\s+/g, " ").trim();
  return plainText.length > 260 ? `${plainText.slice(0, 260)}...` : plainText || "尚未准备学习内容。";
}

function ProjectList({
  projects,
  selectedId,
  state,
  error,
  onSelect,
  onRetry,
  onCreate,
}: {
  projects: ProjectSummary[];
  selectedId: number | null;
  state: LoadState;
  error: string | null;
  onSelect: (projectId: number) => void;
  onRetry: () => void;
  onCreate: () => void;
}) {
  return (
    <aside className="project-rail" aria-label="项目列表">
      <div className="rail-title-row">
        <div>
          <p className="eyebrow">LOCAL STUDY</p>
          <h1>学习轨迹</h1>
        </div>
        <button className="icon-button" type="button" onClick={onRetry} title="刷新项目">
          <RefreshCw size={18} aria-hidden="true" />
          <span className="sr-only">刷新项目</span>
        </button>
      </div>

      {state === "loading" && <div className="rail-message"><LoaderCircle className="spin" size={18} /> 正在读取项目</div>}
      {state === "error" && (
        <div className="rail-message error-message">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button type="button" className="text-action" onClick={onRetry}>重试</button>
        </div>
      )}
      {state === "ready" && projects.length === 0 && (
        <div className="rail-message">还没有学习项目。请先通过现有路线页创建一个项目。</div>
      )}
      <nav className="project-list">
        {projects.map((project) => {
          const isSelected = project.id === selectedId;
          return (
            <button
              key={project.id}
              type="button"
              className={`project-item ${isSelected ? "selected" : ""}`}
              onClick={() => onSelect(project.id)}
              aria-current={isSelected ? "page" : undefined}
            >
              <span className="project-title">{project.title}</span>
              <span className="project-topic">{project.topic}</span>
              <span className="project-metric">{project.progress.done}/{project.progress.total} 已完成</span>
            </button>
          );
        })}
      </nav>
      <button className="new-project-button" type="button" onClick={onCreate}><Plus size={17} />新建学习路线</button>
    </aside>
  );
}

type StatusNode = Pick<WorkspaceNode, "id" | "title" | "status">;

function StatusButton({
  node,
  pending,
  onUpdate,
}: {
  node: StatusNode;
  pending: boolean;
  onUpdate: (status: string) => void;
}) {
  const options = ["pending", "learning", "mastered", "weak"];
  return (
    <div className="status-control" aria-label={`${node.title} 的学习状态`}>
      {options.map((status) => (
        <button
          key={status}
          type="button"
          className={`status-button ${node.status === status ? "active" : ""}`}
          disabled={pending}
          onClick={() => onUpdate(status)}
        >
          {statusLabels[status]}
        </button>
      ))}
    </div>
  );
}

function ReviewPanel({ projectId }: { projectId: number }) {
  const [card, setCard] = useState<ReviewCard | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [showBack, setShowBack] = useState(false);
  const load = useCallback(async () => {
    setState("loading"); setError(null);
    try { const queue = await getDueCards(projectId); setCard(queue.cards[0] ?? null); setShowBack(false); setState("ready"); }
    catch (loadError) { setError(formatError(loadError)); setState("error"); }
  }, [projectId]);
  useEffect(() => { void load(); }, [load]);
  const review = async (rating: number) => {
    if (!card) return;
    setState("loading");
    try { const result = await submitReview(card.id, rating, projectId); setCard(result.next_card); setShowBack(false); setState("ready"); }
    catch (reviewError) { setError(formatError(reviewError)); setState("error"); }
  };
  return <section className="review-panel">
    <div className="section-heading"><div><p className="eyebrow">FSRS REVIEW</p><h3>到期复习</h3></div><button type="button" className="text-action" onClick={() => void load()}>刷新</button></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在读取复习卡片</div>}
    {state === "error" && <div className="review-state detail-error"><AlertCircle size={18} />{error}<button type="button" className="text-action" onClick={() => void load()}>重试</button></div>}
    {state === "ready" && !card && <div className="review-state">当前没有到期卡片。</div>}
    {state === "ready" && card && <div className="review-card"><strong>{card.front}</strong>{showBack && <p>{card.back}</p>}<button type="button" className="secondary-button" onClick={() => setShowBack((value) => !value)}>{showBack ? "隐藏答案" : "查看答案"}</button><div className="review-actions"><button type="button" onClick={() => void review(1)}>重来</button><button type="button" onClick={() => void review(2)}>困难</button><button type="button" onClick={() => void review(3)}>良好</button><button type="button" onClick={() => void review(4)}>简单</button></div></div>}
  </section>;
}

function QuizPanel({ projectId, nodes }: { projectId: number; nodes: WorkspaceNode[] }) {
  const [selectedNodeIds, setSelectedNodeIds] = useState<number[]>([]);
  const [count, setCount] = useState(3);
  const [qtype, setQtype] = useState("mixed");
  const [quiz, setQuiz] = useState<QuizGeneration | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<QuizAnswer | null>(null);
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setSelectedNodeIds(nodes.map((node) => node.id)); setQuiz(null); setIndex(0); setFeedback(null); }, [projectId, nodes]);
  const question = quiz?.questions[index] ?? null;
  const generate = async () => {
    if (!selectedNodeIds.length) { setError("请至少选择一个知识点"); return; }
    setState("loading"); setError(null);
    try { const next = await generateQuiz(projectId, { node_ids: selectedNodeIds, count, qtype }); setQuiz(next); setIndex(0); setAnswer(""); setFeedback(null); setState("ready"); }
    catch (generationError) { setError(formatError(generationError)); setState("error"); }
  };
  const submit = async () => {
    if (!question || !answer.trim()) { setError("请输入答案后再提交"); return; }
    setState("loading"); setError(null);
    try { setFeedback(await submitQuizAnswer(projectId, question.id, answer)); setState("ready"); }
    catch (submissionError) { setError(formatError(submissionError)); setState("error"); }
  };
  const next = () => { setIndex((value) => value + 1); setAnswer(""); setFeedback(null); setError(null); };
  return <section className="quiz-panel">
    <div className="section-heading"><div><p className="eyebrow">KNOWLEDGE CHECK</p><h3>查漏测验</h3></div></div>
    <div className="quiz-form"><label>知识点<select multiple value={selectedNodeIds.map(String)} onChange={(event) => setSelectedNodeIds([...event.currentTarget.selectedOptions].map((item) => Number(item.value)))}>{nodes.map((node) => <option value={node.id} key={node.id}>{node.code} {node.title}</option>)}</select></label><label>题目数量<input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Number(event.target.value))} /></label><label>题型<select value={qtype} onChange={(event) => setQtype(event.target.value)}><option value="mixed">混合</option><option value="choice">选择</option><option value="fill">填空</option><option value="short">简答</option><option value="practice">实操</option></select></label><button type="button" className="command-button" onClick={() => void generate()} disabled={state === "loading"}>生成测验</button></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在处理测验</div>}
    {error && <div className="review-state detail-error"><AlertCircle size={18} />{error}</div>}
    {question && state !== "loading" && <div className="quiz-question"><span>第 {index + 1} / {quiz?.questions.length} 题 · {question.qtype}</span><strong>{question.stem}</strong>{question.options.map((option) => <button type="button" className={`quiz-option ${answer === option ? "active" : ""}`} key={option} onClick={() => setAnswer(option)}>{option}</button>)}<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="输入你的答案" /><button type="button" className="command-button" onClick={() => void submit()} disabled={Boolean(feedback)}>提交答案</button>{feedback && <div className={feedback.is_correct ? "quiz-feedback correct" : "quiz-feedback incorrect"}><strong>{feedback.is_correct ? "回答正确" : "需要巩固"}</strong><p>{feedback.feedback}</p>{feedback.mastery !== null && <span>当前掌握度 {Math.round(feedback.mastery * 100)}%</span>}{index + 1 < (quiz?.questions.length ?? 0) && <button type="button" className="secondary-button" onClick={next}>下一题</button>}</div>}</div>}
  </section>;
}

function DashboardPanel({ projectId }: { projectId: number }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setState("loading"); setError(null); try { setDashboard(await getDashboard(projectId)); setState("ready"); } catch (loadError) { setError(formatError(loadError)); setState("error"); } }, [projectId]);
  useEffect(() => { void load(); }, [load]);
  const download = (kind: string) => { window.location.assign(apiUrl(`/projects/${projectId}/exports/${kind}`)); };
  return <section className="dashboard-panel"><div className="section-heading"><div><p className="eyebrow">LEARNING DASHBOARD</p><h3>学习概览</h3></div><button type="button" className="text-action" onClick={() => void load()}>刷新</button></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在读取看板</div>}{state === "error" && <div className="review-state detail-error"><AlertCircle size={18} />{error}<button type="button" className="text-action" onClick={() => void load()}>重试</button></div>}
    {dashboard && state === "ready" && <><div className="dashboard-metrics"><div><strong>{dashboard.metrics.total_nodes}</strong><span>知识点</span></div><div><strong>{dashboard.metrics.mastered_nodes}</strong><span>已掌握</span></div><div><strong>{Math.round(dashboard.metrics.avg_mastery * 100)}%</strong><span>平均掌握</span></div><div><strong>{dashboard.metrics.week_minutes}</strong><span>近 7 天分钟</span></div><div><strong>{dashboard.metrics.due_cards}/{dashboard.metrics.total_cards}</strong><span>到期卡片</span></div></div><div className="dashboard-detail"><div><strong>状态分布</strong>{Object.entries(dashboard.status_counts).map(([key, value]) => <p key={key}>{statusLabels[key] ?? key} <b>{value}</b></p>)}</div><div><strong>近 14 天学习热力</strong><div className="heatmap">{dashboard.heatmap.map((day) => <span title={`${day.date}: ${day.minutes} 分钟`} style={{ opacity: day.minutes ? Math.min(1, 0.25 + day.minutes / 60) : 0.1 }} key={day.date}>{day.minutes}</span>)}</div></div></div><article className="dashboard-report">{dashboard.latest_report}</article><div className="export-actions"><button type="button" onClick={() => download("roadmap")}>路线 JSON</button><button type="button" onClick={() => download("markdown")}>学习笔记</button><button type="button" onClick={() => download("report")}>进度报告</button><button type="button" onClick={() => download("anki")}>Anki ZIP</button></div></>}
  </section>;
}

function Workspace({
  workspace,
  roadmap,
  state,
  error,
  statusPendingId,
  onRetry,
  onUpdateStatus,
}: {
  workspace: ProjectWorkspace | null;
  roadmap: ProjectRoadmap | null;
  state: LoadState;
  error: string | null;
  statusPendingId: number | null;
  onRetry: () => void;
  onUpdateStatus: (node: StatusNode, status: string) => Promise<boolean>;
}) {
  const roadmapNodes = useMemo(() => new Map(roadmap?.nodes.map((node) => [node.id, node]) ?? []), [roadmap]);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailAction, setDetailAction] = useState<"content" | "practice" | "resources" | "note" | null>(null);
  const [detailActionError, setDetailActionError] = useState<string | null>(null);
  const [noteContent, setNoteContent] = useState("");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("dashboard");
  const [roadmapView, setRoadmapView] = useState<"list" | "detail">("list");
  const detailPanelRef = useRef<HTMLDivElement | null>(null);
  const detailRequestRef = useRef(0);

  useEffect(() => {
    if (detailState !== "idle") {
      detailPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [detailState]);

  const openDetail = async (nodeId: number) => {
    const requestId = ++detailRequestRef.current;
    setRoadmapView("detail");
    setDetailState("loading");
    setDetailError(null);
    setDetailActionError(null);
    setDetailAction(null);
    setDetail(null);
    try {
      const next = await getNodeDetail(nodeId);
      if (requestId !== detailRequestRef.current) return;
      setDetail(next);
      setNoteContent(next.note?.content ?? "");
      setDetailState("ready");
    } catch (loadError) {
      if (requestId !== detailRequestRef.current) return;
      setDetailError(formatError(loadError));
      setDetailState("error");
    }
  };
  const returnToRoadmap = () => {
    ++detailRequestRef.current;
    setRoadmapView("list");
    setDetailState("idle");
    setDetailError(null);
    setDetailActionError(null);
    setDetailAction(null);
  };
  const runDetailAction = async (
    kind: "content" | "practice" | "resources" | "note",
    action: () => Promise<{ detail: NodeDetail; status?: string; error?: string | null }>,
  ) => {
    const requestId = ++detailRequestRef.current;
    setDetailAction(kind);
    setDetailActionError(null);
    try {
      const result = await action();
      if (requestId !== detailRequestRef.current) return;
      setDetail(result.detail);
      if (kind === "note") setNoteContent(result.detail.note?.content ?? noteContent);
      if (result.status === "failed") {
        setDetailActionError(result.error ?? "当前操作失败，请检查模型配置后重试。");
      }
    } catch (actionError) {
      if (requestId !== detailRequestRef.current) return;
      setDetailActionError(formatError(actionError));
    } finally {
      if (requestId === detailRequestRef.current) setDetailAction(null);
    }
  };

  if (state === "loading") {
    return <main className="workspace-state"><LoaderCircle className="spin" size={28} /> 正在加载学习工作台</main>;
  }
  if (state === "error") {
    return (
      <main className="workspace-state">
        <AlertCircle size={30} />
        <strong>项目数据暂时不可用</strong>
        <span>{error}</span>
        <button type="button" className="command-button" onClick={onRetry}><RotateCcw size={16} />重新加载</button>
      </main>
    );
  }
  if (!workspace) {
    return (
      <main className="workspace-state">
        <BookOpenCheck size={34} />
        <strong>选择一个项目</strong>
        <span>这里会显示路线、学习内容和当前进度。</span>
      </main>
    );
  }

  const { project, progress, nodes } = workspace;
  const progressWidth = progress.total === 0 ? 0 : Math.round((progress.done / progress.total) * 100);
  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">{project.topic || "LEARNING PROJECT"}</p>
          <h2>{project.title}</h2>
          <p className="project-goal">{project.goal || project.background || "尚未填写学习目标。"}</p>
        </div>
        <div className="progress-readout" aria-label={`项目进度 ${progress.done}/${progress.total}`}>
          <span>{progress.done}<small> / {progress.total}</small></span>
          <p>完成节点</p>
        </div>
      </header>

      <section className="progress-strip" aria-label="学习进度">
        <div className="progress-line"><span style={{ width: `${progressWidth}%` }} /></div>
        <div className="progress-labels">
          <span>{progressWidth}% 已完成</span>
          <span>{progress.learning} 个学习中</span>
          <span>{progress.weak} 个待巩固</span>
        </div>
      </section>

      <div className="workspace-tabs" role="tablist" aria-label="学习功能">
        {workspaceTabs.map((tab) => (
          <button
            key={tab.id}
            id={`workspace-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`workspace-panel-${tab.id}`}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section
        id={`workspace-panel-${activeTab}`}
        className="workspace-tab-panel"
        role="tabpanel"
        aria-labelledby={`workspace-tab-${activeTab}`}
      >
        {activeTab === "roadmap" && roadmapView === "list" && <>
          <section className="roadmap-pane" aria-label="学习路线">
          <div className="section-heading">
            <div><p className="eyebrow">ROADMAP</p><h3>学习路线</h3></div>
            <span>{roadmap?.stages.length ?? 0} 个阶段</span>
          </div>
          <div className="node-list">
            {nodes.length === 0 && <div className="empty-nodes">该项目暂无学习节点，请新建或重新生成学习路线。</div>}
            {nodes.map((node) => {
              const roadmapNode = roadmapNodes.get(node.id);
              return (
                <article className={`node-row node-${node.status}`} key={node.id}>
                  <button type="button" className="node-open-button" onClick={() => void openDetail(node.id)} aria-label={`查看 ${node.title} 的详细内容`}>
                    <div className="node-marker" aria-hidden="true">{node.status === "mastered" ? <CheckCircle2 size={20} /> : node.code}</div>
                    <div className="node-content">
                      <div className="node-title-row"><h4>{node.title}</h4><span>{roadmapNode?.stage || node.stage}</span></div>
                      <p>{nodePreview(node.description)}</p>
                      <div className="node-meta">
                        <span>{node.est_hours} 小时</span><span>难度 {node.difficulty}/5</span><span>{statusLabels[node.status] ?? node.status}</span>
                      </div>
                      <p className="node-prerequisites">{roadmapNode?.prerequisites?.length ? `前置节点：${roadmapNode.prerequisites.join("、")}` : "可直接开始"}</p>
                      {node.resources.length > 0 && <p className="resource-count">已关联 {node.resources.length} 项学习资料</p>}
                    </div>
                  </button>
                  <StatusButton node={node} pending={statusPendingId === node.id} onUpdate={(status) => onUpdateStatus(node, status)} />
                </article>
              );
            })}
          </div>
          </section>
        </>}
        {activeTab === "roadmap" && roadmapView === "detail" && <>
          <div className="detail-navigation">
            <button type="button" className="secondary-button" onClick={returnToRoadmap}><ArrowLeft size={16} />返回学习路线</button>
          </div>
          {detailState === "loading" && <section ref={detailPanelRef} className="node-detail-panel"><LoaderCircle className="spin" size={18} />正在读取节点详情</section>}
          {detailError && <section ref={detailPanelRef} className="node-detail-panel detail-error"><AlertCircle size={18} />{detailError}</section>}
          {detail && detailState === "ready" && <div ref={detailPanelRef} className="node-detail-windows">
            {detailActionError && <div className="detail-action-error" role="alert"><AlertCircle size={18} />{detailActionError}</div>}
            <section className="node-detail-panel">
              <div className="preview-heading"><div><p className="eyebrow">LESSON DETAIL / 课程详情</p><h3>{detail.title}</h3></div><span>{detail.code}</span></div>
              <StatusButton node={detail} pending={statusPendingId === detail.id} onUpdate={async (status) => { const prior = detail; setDetail({ ...detail, status }); if (!await onUpdateStatus(detail, status)) setDetail(prior); }} />
              <MarkdownContent content={detail.description || "当前没有完整课程内容。"} />
              <div className="detail-actions"><button type="button" className="secondary-button" disabled={detailAction !== null} onClick={() => void runDetailAction("content", () => generateNodeContent(detail.id, detail.has_content))}>{detailAction === "content" && <LoaderCircle className="spin" size={16} />}{detail.has_content ? "重新生成课程" : "生成课程"}</button></div>
              <textarea className="detail-note" value={noteContent} disabled={detailAction !== null} onChange={(event) => setNoteContent(event.target.value)} placeholder="记录你的理解、疑问和总结" />
              <button type="button" className="command-button" disabled={detailAction !== null} onClick={() => void runDetailAction("note", () => saveNodeNote(detail.id, noteContent))}>{detailAction === "note" && <LoaderCircle className="spin" size={16} />}保存笔记</button>
            </section>
            <section className="node-detail-panel">
              <div className="preview-heading"><div><p className="eyebrow">PRACTICE LESSON / 实操课程</p><h3>{detail.practice?.title ?? "尚未生成实操课程"}</h3></div></div>
              {detail.practice ? <div className="detail-practice-content"><MarkdownContent content={detail.practice.description} /></div> : <p className="detail-empty">生成课程后，可在这里完成针对当前知识点的实操练习。</p>}
              <div className="detail-actions"><button type="button" className="secondary-button" disabled={detailAction !== null} onClick={() => void runDetailAction("practice", () => generatePracticeLesson(detail.id))}>{detailAction === "practice" && <LoaderCircle className="spin" size={16} />}{detail.practice ? "重新生成实操" : "生成实操"}</button></div>
            </section>
            <section className="node-detail-panel">
              <div className="preview-heading"><div><p className="eyebrow">REFERENCE MATERIALS / 参考资料</p><h3>{detail.resources.length ? `${detail.resources.length} 项已关联资料` : "尚未拉取参考资料"}</h3></div></div>
              {detail.resources.length ? <div className="detail-resource-list">{detail.resources.map((resource) => <a className="detail-resource" href={resource.url} target="_blank" rel="noreferrer" key={resource.id ?? resource.url}><strong>{resource.title}</strong><span>{resource.rtype} · {resource.source}</span>{resource.description && <small>{resource.description}</small>}</a>)}</div> : <p className="detail-empty">拉取后，资料会保留在当前节点并显示在此处。</p>}
              <div className="detail-actions"><button type="button" className="secondary-button" disabled={detailAction !== null} onClick={() => void runDetailAction("resources", () => generateNodeResources(detail.id))}>{detailAction === "resources" && <LoaderCircle className="spin" size={16} />}拉取资料</button></div>
            </section>
          </div>}
        </>}
        {activeTab === "dashboard" && <DashboardPanel projectId={project.id} />}
        {activeTab === "review" && <ReviewPanel projectId={project.id} />}
        {activeTab === "rag" && <><ResourceLibraryPanel nodes={nodes} /><RagChatPanel nodes={nodes} /></>}
        {activeTab === "quiz" && <QuizPanel projectId={project.id} nodes={nodes} />}
        {activeTab === "models" && <ModelConfigurationPanel />}
      </section>
    </main>
  );
}

export default function HomePage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [projectState, setProjectState] = useState<LoadState>("loading");
  const [workspaceState, setWorkspaceState] = useState<LoadState>("idle");
  const [workspace, setWorkspace] = useState<ProjectWorkspace | null>(null);
  const [roadmap, setRoadmap] = useState<ProjectRoadmap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusPendingId, setStatusPendingId] = useState<number | null>(null);
  const [view, setView] = useState<"workspace" | "create">("workspace");

  const loadWorkspace = useCallback(async (projectId: number) => {
    setWorkspaceState("loading");
    setError(null);
    try {
      const [nextRoadmap, nextWorkspace] = await Promise.all([
        getProjectRoadmap(projectId),
        getProjectWorkspace(projectId),
      ]);
      setRoadmap(nextRoadmap);
      setWorkspace(nextWorkspace);
      setWorkspaceState("ready");
    } catch (loadError) {
      setWorkspaceState("error");
      setError(formatError(loadError));
    }
  }, []);

  const loadProjects = useCallback(async (preferredProjectId?: number) => {
    setProjectState("loading");
    setError(null);
    try {
      const nextProjects = await listProjects();
      setProjects(nextProjects);
      setProjectState("ready");
      const nextId = preferredProjectId && nextProjects.some((project) => project.id === preferredProjectId)
        ? preferredProjectId
        : selectedId && nextProjects.some((project) => project.id === selectedId)
        ? selectedId
        : nextProjects[0]?.id ?? null;
      setSelectedId(nextId);
      if (nextId) {
        await loadWorkspace(nextId);
      } else {
        setWorkspace(null);
        setRoadmap(null);
        setWorkspaceState("ready");
      }
    } catch (loadError) {
      setProjectState("error");
      setError(formatError(loadError));
    }
  }, [loadWorkspace, selectedId]);

  useEffect(() => { void loadProjects(); }, [loadProjects]);

  const chooseProject = (projectId: number) => {
    setView("workspace");
    setSelectedId(projectId);
    void loadWorkspace(projectId);
  };

  const showCreatedProject = (projectId: number) => {
    setView("workspace");
    setSelectedId(projectId);
    void loadProjects(projectId);
  };

  const changeNodeStatus = async (node: StatusNode, status: string) => {
    if (!workspace || status === node.status) return true;
    const priorWorkspace = workspace;
    setStatusPendingId(node.id);
    setError(null);
    setWorkspace({
      ...workspace,
      nodes: workspace.nodes.map((item) => item.id === node.id ? { ...item, status } : item),
    });
    try {
      const result = await updateNodeStatus(node.id, status);
      setWorkspace(result.workspace);
      setRoadmap((current) => current ? {
        ...current,
        nodes: current.nodes.map((item) => item.id === node.id ? { ...item, status } : item),
      } : current);
      void loadProjects();
    } catch (updateError) {
      setWorkspace(priorWorkspace);
      setError(formatError(updateError));
      return false;
    } finally {
      setStatusPendingId(null);
    }
    return true;
  };

  return (
    <div className="app-shell">
      <ProjectList projects={projects} selectedId={view === "workspace" ? selectedId : null} state={projectState} error={error} onSelect={chooseProject} onRetry={() => void loadProjects()} onCreate={() => setView("create")} />
      {view === "create" ? <RoadmapCreation onCreated={showCreatedProject} /> : <Workspace key={selectedId ?? "empty"} workspace={workspace} roadmap={roadmap} state={workspaceState} error={error} statusPendingId={statusPendingId} onRetry={() => selectedId && void loadWorkspace(selectedId)} onUpdateStatus={changeNodeStatus} />}
    </div>
  );
}
