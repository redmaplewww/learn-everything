"use client";

import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useMemo, useState } from "react";

import type { ProjectRoadmap, WorkspaceNode } from "../../lib/api";
import { NodeDetailPanel } from "./NodeDetailPanel";
import { NodeStatusControl, statusLabels } from "./NodeStatusControl";
import { useNodeDetail } from "./useNodeDetail";

function nodePreview(description: string) {
  const plainText = description.replace(/^#{1,6}\s+/gm, "").replace(/\s+/g, " ").trim();
  return plainText.length > 260 ? `${plainText.slice(0, 260)}...` : plainText || "尚未准备学习内容。";
}

export function RoadmapPanel({ roadmap, nodes, statusPendingId, onUpdateStatus }: { roadmap: ProjectRoadmap | null; nodes: WorkspaceNode[]; statusPendingId: number | null; onUpdateStatus: (node: Pick<WorkspaceNode, "id" | "title" | "status">, status: string) => Promise<boolean> }) {
  const [view, setView] = useState<"list" | "detail">("list");
  const detail = useNodeDetail();
  const roadmapNodes = useMemo(() => new Map(roadmap?.nodes.map((node) => [node.id, node]) ?? []), [roadmap]);

  const openDetail = async (nodeId: number) => { setView("detail"); await detail.open(nodeId); };
  const returnToRoadmap = () => { detail.close(); setView("list"); };
  const updateDetailStatus = async (status: string) => {
    if (!detail.detail) return;
    const prior = detail.detail.status;
    detail.updateStatus(status);
    if (!await onUpdateStatus(detail.detail, status)) detail.updateStatus(prior);
  };

  if (view === "detail") return <>
    <div className="detail-navigation"><button type="button" className="secondary-button" onClick={returnToRoadmap}><ArrowLeft size={16} />返回学习路线</button></div>
    <NodeDetailPanel detail={detail.detail} state={detail.state} error={detail.error} action={detail.action} actionError={detail.actionError} noteContent={detail.noteContent} onNoteChange={detail.setNoteContent} onUpdateStatus={(status) => void updateDetailStatus(status)} onGenerateContent={() => detail.detail && void detail.generateContent(detail.detail.id, detail.detail.has_content)} onGeneratePractice={() => detail.detail && void detail.generatePractice(detail.detail.id)} onGenerateResources={() => detail.detail && void detail.generateResources(detail.detail.id)} onSaveNote={() => detail.detail && void detail.saveNote(detail.detail.id, detail.noteContent)} statusPending={detail.detail ? statusPendingId === detail.detail.id : false} />
  </>;

  return <section className="roadmap-pane" aria-label="学习路线">
    <div className="section-heading"><div><p className="eyebrow">ROADMAP</p><h3>学习路线</h3></div><span>{roadmap?.stages.length ?? 0} 个阶段</span></div>
    <div className="node-list">
      {nodes.length === 0 && <div className="empty-nodes">该项目暂无学习节点，请新建或重新生成学习路线。</div>}
      {nodes.map((node) => {
        const roadmapNode = roadmapNodes.get(node.id);
        return <article className={`node-row node-${node.status}`} key={node.id}>
          <button type="button" className="node-open-button" onClick={() => void openDetail(node.id)} aria-label={`查看 ${node.title} 的详细内容`}>
            <div className="node-marker" aria-hidden="true">{node.status === "mastered" ? <CheckCircle2 size={20} /> : node.code}</div>
            <div className="node-content"><div className="node-title-row"><h4>{node.title}</h4><span>{roadmapNode?.stage || node.stage}</span></div><p>{nodePreview(node.description)}</p><div className="node-meta"><span>{node.est_hours} 小时</span><span>难度 {node.difficulty}/5</span><span>{statusLabels[node.status] ?? node.status}</span></div><p className="node-prerequisites">{roadmapNode?.prerequisites?.length ? `前置节点：${roadmapNode.prerequisites.join("、")}` : "可直接开始"}</p>{node.resources.length > 0 && <p className="resource-count">已关联 {node.resources.length} 项学习资料</p>}</div>
          </button>
          <NodeStatusControl node={node} pending={statusPendingId === node.id} onUpdate={(status) => void onUpdateStatus(node, status)} />
        </article>;
      })}
    </div>
  </section>;
}
