"use client";

import { useCallback, useState } from "react";

import { ProjectDeletionDialog } from "../features/projects/ProjectDeletionDialog";
import { ProjectEditDialog } from "../features/projects/ProjectEditDialog";
import { ProjectRail } from "../features/projects/ProjectRail";
import { useProjectCatalog } from "../features/projects/useProjectCatalog";
import { RoadmapCreation } from "../features/roadmap/RoadmapCreation";
import { Workspace } from "../features/workspace/Workspace";
import { useProjectWorkspace } from "../features/workspace/useProjectWorkspace";

export default function HomePage() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [view, setView] = useState<"workspace" | "create">("workspace");
  const catalog = useProjectCatalog(selectedProjectId, setSelectedProjectId);
  const refreshCatalog = useCallback(() => { void catalog.refresh(); }, [catalog.refresh]);
  const projectWorkspace = useProjectWorkspace(selectedProjectId, refreshCatalog);

  const chooseProject = (projectId: number) => {
    setView("workspace");
    setSelectedProjectId(projectId);
  };

  const showCreatedProject = (projectId: number) => {
    setView("workspace");
    setSelectedProjectId(projectId);
    void catalog.refresh(projectId);
  };

  return <div className="app-shell">
    <ProjectRail projects={catalog.projects} selectedId={view === "workspace" ? selectedProjectId : null} state={catalog.state} error={catalog.error} onSelect={chooseProject} onRetry={() => void catalog.refresh()} onCreate={() => setView("create")} onEdit={(projectId) => void catalog.openEditor(projectId)} onDelete={catalog.beginDelete} />
    {view === "create" ? <RoadmapCreation onCreated={showCreatedProject} /> : <Workspace key={selectedProjectId ?? "empty"} workspace={projectWorkspace.workspace} roadmap={projectWorkspace.roadmap} state={projectWorkspace.state} error={projectWorkspace.error} statusPendingId={projectWorkspace.statusPendingId} onRetry={() => void projectWorkspace.reload()} onUpdateStatus={projectWorkspace.changeNodeStatus} />}
    {catalog.editingProject && <ProjectEditDialog key={`edit-${catalog.editingProject.id}`} project={catalog.editingProject} saving={catalog.action === "saving"} error={catalog.actionError} onClose={catalog.closeEditor} onSave={(payload) => void catalog.save(payload)} />}
    {catalog.deletingProject && <ProjectDeletionDialog key={`delete-${catalog.deletingProject.id}`} project={catalog.deletingProject} deleting={catalog.action === "deleting"} error={catalog.actionError} onClose={catalog.closeDelete} onConfirm={() => void catalog.confirmDelete()} />}
  </div>;
}
