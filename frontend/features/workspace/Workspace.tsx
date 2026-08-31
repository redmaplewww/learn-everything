"use client";

import { useState } from "react";

import { ModelConfigurationPanel } from "../configuration/ModelConfigurationPanel";
import { DashboardPanel } from "../dashboard/DashboardPanel";
import { QuizPanel } from "../quiz/QuizPanel";
import { RagChatPanel } from "../chat/RagChatPanel";
import { ResourceLibraryPanel } from "../resources/ResourceLibraryPanel";
import { ReviewPanel } from "../review/ReviewPanel";
import { RoadmapPanel } from "../roadmap/RoadmapPanel";
import type { ProjectRoadmap, ProjectWorkspace } from "../../lib/api";
import type { StatusNode, WorkspaceLoadState } from "./useProjectWorkspace";
import { WorkspaceStatus } from "./WorkspaceStatus";

type WorkspaceTab = "dashboard" | "roadmap" | "review" | "rag" | "quiz" | "models";

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "dashboard", label: "学习概览" },
  { id: "roadmap", label: "学习路线" },
  { id: "review", label: "到期复习" },
  { id: "rag", label: "RAG 问答" },
  { id: "quiz", label: "查漏测验" },
  { id: "models", label: "模型配置" },
];

export function Workspace({
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
  state: WorkspaceLoadState;
  error: string | null;
  statusPendingId: number | null;
  onRetry: () => void;
  onUpdateStatus: (node: StatusNode, status: string) => Promise<boolean>;
}) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("dashboard");
  if (state !== "ready" || !workspace) return <WorkspaceStatus state={state} error={error} onRetry={onRetry} />;

  const { project, progress, nodes } = workspace;
  const progressWidth = progress.total === 0 ? 0 : Math.round((progress.done / progress.total) * 100);
  return <main className="workspace">
    <header className="workspace-header"><div><p className="eyebrow">{project.topic || "LEARNING PROJECT"}</p><h2>{project.title}</h2><p className="project-goal">{project.goal || project.background || "尚未填写学习目标。"}</p></div><div className="progress-readout" aria-label={`项目进度 ${progress.done}/${progress.total}`}><span>{progress.done}<small> / {progress.total}</small></span><p>完成节点</p></div></header>
    <section className="progress-strip" aria-label="学习进度"><div className="progress-line"><span style={{ width: `${progressWidth}%` }} /></div><div className="progress-labels"><span>{progressWidth}% 已完成</span><span>{progress.learning} 个学习中</span><span>{progress.weak} 个待巩固</span></div></section>
    <div className="workspace-tabs" role="tablist" aria-label="学习功能">{workspaceTabs.map((tab) => <button key={tab.id} id={`workspace-tab-${tab.id}`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`workspace-panel-${tab.id}`} className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}</div>
    <section id={`workspace-panel-${activeTab}`} className="workspace-tab-panel" role="tabpanel" aria-labelledby={`workspace-tab-${activeTab}`}>
      <div hidden={activeTab !== "roadmap"}><RoadmapPanel roadmap={roadmap} nodes={nodes} statusPendingId={statusPendingId} onUpdateStatus={onUpdateStatus} /></div>
      {activeTab === "dashboard" && <DashboardPanel projectId={project.id} />}
      {activeTab === "review" && <ReviewPanel projectId={project.id} />}
      {activeTab === "rag" && <><ResourceLibraryPanel nodes={nodes} /><RagChatPanel nodes={nodes} /></>}
      {activeTab === "quiz" && <QuizPanel projectId={project.id} nodes={nodes} />}
      {activeTab === "models" && <ModelConfigurationPanel />}
    </section>
  </main>;
}
