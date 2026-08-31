"use client";

import { AlertCircle, LoaderCircle } from "lucide-react";
import { useEffect, useRef } from "react";

import { MarkdownContent } from "../markdown/MarkdownContent";
import { NodeStatusControl } from "./NodeStatusControl";
import type { DetailAction, DetailLoadState } from "./useNodeDetail";
import type { NodeDetail } from "../../lib/api";

export function NodeDetailPanel({
  detail,
  state,
  error,
  action,
  actionError,
  noteContent,
  onNoteChange,
  onUpdateStatus,
  onGenerateContent,
  onGeneratePractice,
  onGenerateResources,
  onSaveNote,
  statusPending,
}: {
  detail: NodeDetail | null;
  state: DetailLoadState;
  error: string | null;
  action: DetailAction;
  actionError: string | null;
  noteContent: string;
  onNoteChange: (content: string) => void;
  onUpdateStatus: (status: string) => void;
  onGenerateContent: () => void;
  onGeneratePractice: () => void;
  onGenerateResources: () => void;
  onSaveNote: () => void;
  statusPending: boolean;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (state !== "idle") panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [state]);

  if (state === "loading") return <section ref={panelRef} className="node-detail-panel"><LoaderCircle className="spin" size={18} />正在读取节点详情</section>;
  if (error) return <section ref={panelRef} className="node-detail-panel detail-error"><AlertCircle size={18} />{error}</section>;
  if (!detail) return null;

  return <div ref={panelRef} className="node-detail-windows">
    {actionError && <div className="detail-action-error" role="alert"><AlertCircle size={18} />{actionError}</div>}
    <section className="node-detail-panel">
      <div className="preview-heading"><div><p className="eyebrow">LESSON DETAIL / 课程详情</p><h3>{detail.title}</h3></div><span>{detail.code}</span></div>
      <NodeStatusControl node={detail} pending={statusPending} onUpdate={onUpdateStatus} />
      <MarkdownContent content={detail.description || "当前没有完整课程内容。"} />
      <div className="detail-actions"><button type="button" className="secondary-button" disabled={action !== null} onClick={onGenerateContent}>{action === "content" && <LoaderCircle className="spin" size={16} />}{detail.has_content ? "重新生成课程" : "生成课程"}</button></div>
      <textarea className="detail-note" value={noteContent} disabled={action !== null} onChange={(event) => onNoteChange(event.target.value)} placeholder="记录你的理解、疑问和总结" />
      <button type="button" className="command-button" disabled={action !== null} onClick={onSaveNote}>{action === "note" && <LoaderCircle className="spin" size={16} />}保存笔记</button>
    </section>
    <section className="node-detail-panel">
      <div className="preview-heading"><div><p className="eyebrow">PRACTICE LESSON / 实操课程</p><h3>{detail.practice?.title ?? "尚未生成实操课程"}</h3></div></div>
      {detail.practice ? <div className="detail-practice-content"><MarkdownContent content={detail.practice.description} /></div> : <p className="detail-empty">生成课程后，可在这里完成针对当前知识点的实操练习。</p>}
      <div className="detail-actions"><button type="button" className="secondary-button" disabled={action !== null} onClick={onGeneratePractice}>{action === "practice" && <LoaderCircle className="spin" size={16} />}{detail.practice ? "重新生成实操" : "生成实操"}</button></div>
    </section>
    <section className="node-detail-panel">
      <div className="preview-heading"><div><p className="eyebrow">REFERENCE MATERIALS / 参考资料</p><h3>{detail.resources.length ? `${detail.resources.length} 项已关联资料` : "尚未拉取参考资料"}</h3></div></div>
      {detail.resources.length ? <div className="detail-resource-list">{detail.resources.map((resource) => <a className="detail-resource" href={resource.url} target="_blank" rel="noreferrer" key={resource.id ?? resource.url}><strong>{resource.title}</strong><span>{resource.rtype} · {resource.source}</span>{resource.description && <small>{resource.description}</small>}</a>)}</div> : <p className="detail-empty">拉取后，资料会保留在当前节点并显示在此处。</p>}
      <div className="detail-actions"><button type="button" className="secondary-button" disabled={action !== null} onClick={onGenerateResources}>{action === "resources" && <LoaderCircle className="spin" size={16} />}拉取资料</button></div>
    </section>
  </div>;
}
