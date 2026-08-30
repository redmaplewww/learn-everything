"use client";

import { AlertCircle, LoaderCircle, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";

import type { ProjectSummary } from "../../lib/api";

type LoadState = "idle" | "loading" | "ready" | "error";

export function ProjectRail({
  projects,
  selectedId,
  state,
  error,
  onSelect,
  onRetry,
  onCreate,
  onEdit,
  onDelete,
}: {
  projects: ProjectSummary[];
  selectedId: number | null;
  state: LoadState;
  error: string | null;
  onSelect: (projectId: number) => void;
  onRetry: () => void;
  onCreate: () => void;
  onEdit: (projectId: number) => void;
  onDelete: (project: ProjectSummary) => void;
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
          return <article key={project.id} className={`project-item ${isSelected ? "selected" : ""}`}>
            <button type="button" className="project-select" onClick={() => onSelect(project.id)} aria-current={isSelected ? "page" : undefined}>
              <span className="project-title">{project.title}</span>
              <span className="project-topic">{project.topic}</span>
              <span className="project-metric">{project.progress.done}/{project.progress.total} 已完成</span>
            </button>
            <div className="project-actions">
              <button type="button" className="project-action" title={`编辑 ${project.title}`} onClick={() => onEdit(project.id)}><Pencil size={14} /><span className="sr-only">编辑 {project.title}</span></button>
              <button type="button" className="project-action danger" title={`删除 ${project.title}`} onClick={() => onDelete(project)}><Trash2 size={14} /><span className="sr-only">删除 {project.title}</span></button>
            </div>
          </article>;
        })}
      </nav>
      <button className="new-project-button" type="button" onClick={onCreate}><Plus size={17} />新建学习路线</button>
    </aside>
  );
}
