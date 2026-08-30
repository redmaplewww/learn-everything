"use client";

import { LoaderCircle, X } from "lucide-react";
import { useState } from "react";

import type { Project, ProjectUpdate } from "../../lib/api";

export function ProjectEditDialog({
  project,
  saving,
  error,
  onClose,
  onSave,
}: {
  project: Project;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (payload: ProjectUpdate) => void;
}) {
  const [title, setTitle] = useState(project.title);
  const [topic, setTopic] = useState(project.topic);
  const [background, setBackground] = useState(project.background);
  const [goal, setGoal] = useState(project.goal);
  const [weeklyHours, setWeeklyHours] = useState(project.weekly_hours);
  return <div className="project-dialog-backdrop" role="presentation">
    <form className="project-dialog" role="dialog" aria-modal="true" aria-labelledby="project-edit-title" onSubmit={(event) => { event.preventDefault(); onSave({ title, topic, background, goal, weekly_hours: weeklyHours }); }}>
      <div className="project-dialog-heading"><div><p className="eyebrow">PROJECT SETTINGS</p><h2 id="project-edit-title">编辑学习项目</h2></div><button type="button" className="icon-button" title="关闭" onClick={onClose} disabled={saving}><X size={18} /></button></div>
      <p className="project-dialog-hint">修改主题不会重新生成当前学习路线；需要变更路线时，请新建学习路线。</p>
      <label>项目名称<input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={300} disabled={saving} /></label>
      <label>学习主题<input value={topic} onChange={(event) => setTopic(event.target.value)} required maxLength={300} disabled={saving} /></label>
      <label>学习背景<textarea value={background} onChange={(event) => setBackground(event.target.value)} maxLength={4000} rows={3} disabled={saving} /></label>
      <label>学习目标<textarea value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={4000} rows={3} disabled={saving} /></label>
      <label>每周投入时间<span className="hour-input"><input type="number" min="1" max="168" value={weeklyHours} onChange={(event) => setWeeklyHours(Number(event.target.value))} required disabled={saving} />小时</span></label>
      {error && <p className="project-dialog-error" role="alert">{error}</p>}
      <div className="project-dialog-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={saving}>取消</button><button type="submit" className="command-button" disabled={saving}>{saving && <LoaderCircle className="spin" size={16} />}保存修改</button></div>
    </form>
  </div>;
}
