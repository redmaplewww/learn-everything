"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { deleteProject, getProject, listProjects, updateProject, type Project, type ProjectSummary, type ProjectUpdate } from "../../lib/api";
import { formatError } from "../../lib/errors";

type LoadState = "idle" | "loading" | "ready" | "error";

export function useProjectCatalog(selectedId: number | null, onSelectionChange: (projectId: number | null) => void) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<ProjectSummary | null>(null);
  const [action, setAction] = useState<"saving" | "deleting" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const refresh = useCallback(async (preferredProjectId?: number) => {
    setState("loading");
    setError(null);
    try {
      const nextProjects = await listProjects();
      setProjects(nextProjects);
      setState("ready");
      const currentId = selectedIdRef.current;
      const nextId = preferredProjectId && nextProjects.some((project) => project.id === preferredProjectId)
        ? preferredProjectId
        : currentId && nextProjects.some((project) => project.id === currentId)
        ? currentId
        : nextProjects[0]?.id ?? null;
      onSelectionChange(nextId);
      return nextProjects;
    } catch (loadError) {
      setState("error");
      setError(formatError(loadError));
      return null;
    }
  }, [onSelectionChange]);

  useEffect(() => { void refresh(); }, [refresh]);

  const openEditor = useCallback(async (projectId: number) => {
    setActionError(null);
    try {
      setEditingProject(await getProject(projectId));
    } catch (loadError) {
      setActionError(formatError(loadError));
    }
  }, []);

  const save = useCallback(async (payload: ProjectUpdate) => {
    if (!editingProject) return;
    setAction("saving");
    setActionError(null);
    try {
      await updateProject(editingProject.id, payload);
      const projectId = editingProject.id;
      setEditingProject(null);
      await refresh(projectId);
    } catch (saveError) {
      setActionError(formatError(saveError));
    } finally {
      setAction(null);
    }
  }, [editingProject, refresh]);

  const confirmDelete = useCallback(async () => {
    if (!deletingProject) return;
    setAction("deleting");
    setActionError(null);
    try {
      await deleteProject(deletingProject.id, "DELETE");
      setDeletingProject(null);
      await refresh();
    } catch (deleteError) {
      setActionError(formatError(deleteError));
    } finally {
      setAction(null);
    }
  }, [deletingProject, refresh]);

  const beginDelete = useCallback((project: ProjectSummary) => {
    setActionError(null);
    setDeletingProject(project);
  }, []);

  const closeEditor = useCallback(() => { setEditingProject(null); setActionError(null); }, []);
  const closeDelete = useCallback(() => { setDeletingProject(null); setActionError(null); }, []);

  return {
    projects,
    state,
    error,
    editingProject,
    deletingProject,
    action,
    actionError,
    refresh,
    openEditor,
    save,
    beginDelete,
    confirmDelete,
    closeEditor,
    closeDelete,
  };
}
