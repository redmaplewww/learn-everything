"use client";

import { LoaderCircle, X } from "lucide-react";
import { useState } from "react";

import type { ProjectSummary } from "../../lib/api";

export function ProjectDeletionDialog({
  project,
  deleting,
  error,
  onClose,
  onConfirm,
}: {
  project: ProjectSummary;
  deleting: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  return <div className="project-dialog-backdrop" role="presentation">
    <section className="project-dialog project-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="project-delete-title">
      <div className="project-dialog-heading"><div><p className="eyebrow">DELETE PROJECT</p><h2 id="project-delete-title">删除“{project.title}”</h2></div><button type="button" className="icon-button" title="关闭" onClick={onClose} disabled={deleting}><X size={18} /></button></div>
      <p>这会永久删除该项目的路线、知识点、学习笔记、参考资料、卡片、复习记录、测验和进度记录。</p>
      <label>输入 <strong>DELETE</strong> 确认<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" disabled={deleting} /></label>
      {error && <p className="project-dialog-error" role="alert">{error}</p>}
      <div className="project-dialog-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={deleting}>取消</button><button type="button" className="danger-button" onClick={onConfirm} disabled={confirmation !== "DELETE" || deleting}>{deleting && <LoaderCircle className="spin" size={16} />}永久删除</button></div>
    </section>
  </div>;
}
