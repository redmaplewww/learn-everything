"use client";

import { AlertCircle, ArrowRight, CheckCircle2, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  cancelContentPreparation,
  createProject,
  getContentPreparation,
  prepareProjectContent,
  previewRoadmap,
  refineRoadmap,
  retryContentPreparation,
  type ContentPreparation,
  type RoadmapPreview,
} from "../../lib/api";
import { formatError } from "../../lib/errors";

type CreationState = "idle" | "previewing" | "ready" | "saving" | "preparing" | "error";

export function RoadmapCreation({ onCreated }: { onCreated: (projectId: number) => void }) {
  const [topic, setTopic] = useState("");
  const [background, setBackground] = useState("");
  const [goal, setGoal] = useState("");
  const [weeklyHours, setWeeklyHours] = useState(10);
  const [instruction, setInstruction] = useState("");
  const [preview, setPreview] = useState<RoadmapPreview | null>(null);
  const [creation, setCreation] = useState<ContentPreparation | null>(null);
  const [createdProjectId, setCreatedProjectId] = useState<number | null>(null);
  const [state, setState] = useState<CreationState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!creation || (creation.status !== "doing" && creation.status !== "cancelling")) return;
    const timer = window.setInterval(() => {
      void getContentPreparation(creation.project_id, creation.job_id)
        .then((current) => setCreation(current))
        .catch((pollError) => {
          window.clearInterval(timer);
          setError(formatError(pollError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
          setState("error");
        });
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [creation]);

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    setState("previewing");
    setError(null);
    try {
      setPreview(await previewRoadmap({ topic, background, goal, weekly_hours: weeklyHours }));
      setState("ready");
    } catch (generateError) {
      setError(formatError(generateError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
      setState("error");
    }
  };

  const refine = async () => {
    if (!preview || !instruction.trim()) return;
    setState("previewing");
    setError(null);
    try {
      const result = await refineRoadmap(preview.roadmap, instruction.trim());
      setPreview({ ...preview, roadmap: result.roadmap });
      setInstruction("");
      setState("ready");
    } catch (refineError) {
      setError(formatError(refineError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
      setState("error");
    }
  };

  const save = async () => {
    if (!preview) return;
    setState("saving");
    setError(null);
    try {
      const project = await createProject({ topic, background, goal, weekly_hours: weeklyHours, roadmap: preview.roadmap });
      setState("preparing");
      const preparation = await prepareProjectContent(project.project_id);
      setCreation(preparation);
      setCreatedProjectId(project.project_id);
    } catch (saveError) {
      setError(formatError(saveError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
      setState("error");
    }
  };

  const cancelPreparation = async () => {
    if (!creation) return;
    setError(null);
    try {
      setCreation(await cancelContentPreparation(creation.project_id, creation.job_id));
    } catch (cancelError) {
      setError(formatError(cancelError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
    }
  };

  const retryPreparation = async () => {
    if (!creation) return;
    setError(null);
    try {
      setCreation(await retryContentPreparation(creation.project_id, creation.job_id));
    } catch (retryError) {
      setError(formatError(retryError, "本地学习服务不可用，请确认 FastAPI 已启动。"));
    }
  };

  const isBusy = state === "previewing" || state === "saving" || state === "preparing";
  return (
    <main className="roadmap-creation">
      <header className="creation-header">
        <p className="eyebrow">NEW LEARNING PATH</p>
        <h2>规划一条可执行的学习路线</h2>
        <p>先生成并审阅路线，再保存项目。内容准备作为独立作业持续显示状态。</p>
      </header>

      <form className="roadmap-form" onSubmit={(event) => void generate(event)}>
        <label>选题<input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="例如：从零学习 Transformer" required maxLength={300} /></label>
        <label>学习背景<textarea value={background} onChange={(event) => setBackground(event.target.value)} placeholder="已有 Python 基础，了解神经网络" maxLength={4000} rows={3} /></label>
        <label>学习目标<textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="能理解论文并实现小型模型" maxLength={4000} rows={3} /></label>
        <label>每周投入时间<span className="hour-input"><input type="number" min="1" max="168" value={weeklyHours} onChange={(event) => setWeeklyHours(Number(event.target.value))} required />小时</span></label>
        <button className="command-button" type="submit" disabled={isBusy}><Sparkles size={17} />{state === "previewing" ? "正在生成" : "生成路线预览"}</button>
      </form>

      {error && <div className="creation-error"><AlertCircle size={19} /><span>{error}</span><button type="button" className="text-action" onClick={() => setError(null)}>关闭</button></div>}

      {preview && (
        <section className="roadmap-preview" aria-live="polite">
          <div className="preview-heading"><div><p className="eyebrow">PREVIEW</p><h3>{preview.roadmap.summary}</h3></div><span>{preview.roadmap.nodes.length} 个节点</span></div>
          {(preview.audit.verdict || preview.audit.score !== undefined) && <div className="audit-note"><strong>路线审计</strong><span>{preview.audit.score ?? "-"} 分 · {preview.audit.verdict ?? "已完成"}</span></div>}
          <ol className="preview-nodes">{preview.roadmap.nodes.map((node) => <li key={node.code}><span>{node.code}</span><div><strong>{node.title}</strong><p>{node.description}</p></div><em>{node.est_hours} 小时</em></li>)}</ol>
          <div className="refine-row"><input value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="例如：增加一个实操项目" maxLength={4000} /><button type="button" className="secondary-button" onClick={() => void refine()} disabled={isBusy || !instruction.trim()}><RotateCcw size={16} />调整</button></div>
          <button type="button" className="command-button save-route" onClick={() => void save()} disabled={isBusy}><CheckCircle2 size={17} />{state === "saving" ? "正在保存项目" : state === "preparing" ? "正在启动内容准备" : "确认保存并开始准备"}<ArrowRight size={17} /></button>
        </section>
      )}

      {creation && <section className={`content-job job-${creation.status}`}><LoaderCircle className={creation.status === "doing" || creation.status === "cancelling" ? "spin" : ""} size={20} /><div><strong>{creation.status === "doing" ? "课程内容正在准备" : creation.status === "cancelling" ? "正在停止课程准备" : creation.status === "done" ? "课程内容已准备完成" : creation.status === "cancelled" ? "课程内容准备已取消" : "课程内容准备受阻"}</strong><span>已生成 {creation.generated_node_ids.length} 节，待处理 {creation.pending_node_ids.length} 节，失败 {creation.failed_node_ids.length} 节，第 {creation.attempts} 次尝试。</span>{creation.error && <span>{creation.error}</span>}<div className="detail-actions">{creation.status === "doing" && <button type="button" className="secondary-button" onClick={() => void cancelPreparation()}>停止准备</button>}{(creation.status === "blocked" || creation.status === "cancelled") && creation.pending_node_ids.length + creation.failed_node_ids.length > 0 && <button type="button" className="secondary-button" onClick={() => void retryPreparation()}>重试未完成内容</button>}{createdProjectId && <button type="button" className="text-action" onClick={() => onCreated(createdProjectId)}>查看新项目</button>}</div></div></section>}
    </main>
  );
}
