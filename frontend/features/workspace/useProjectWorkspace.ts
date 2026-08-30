"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getProjectRoadmap, getProjectWorkspace, updateNodeStatus, type ProjectRoadmap, type ProjectWorkspace, type WorkspaceNode } from "../../lib/api";
import { formatError } from "../../lib/errors";

export type WorkspaceLoadState = "idle" | "loading" | "ready" | "error";
export type StatusNode = Pick<WorkspaceNode, "id" | "title" | "status">;

export function useProjectWorkspace(projectId: number | null, onStatusUpdated: () => void) {
  const [workspace, setWorkspace] = useState<ProjectWorkspace | null>(null);
  const [roadmap, setRoadmap] = useState<ProjectRoadmap | null>(null);
  const [state, setState] = useState<WorkspaceLoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [statusPendingId, setStatusPendingId] = useState<number | null>(null);
  const requestRef = useRef(0);

  const reload = useCallback(async () => {
    if (!projectId) {
      setWorkspace(null);
      setRoadmap(null);
      setState("ready");
      return;
    }
    const requestId = ++requestRef.current;
    setState("loading");
    setError(null);
    try {
      const [nextRoadmap, nextWorkspace] = await Promise.all([
        getProjectRoadmap(projectId),
        getProjectWorkspace(projectId),
      ]);
      if (requestId !== requestRef.current) return;
      setRoadmap(nextRoadmap);
      setWorkspace(nextWorkspace);
      setState("ready");
    } catch (loadError) {
      if (requestId !== requestRef.current) return;
      setState("error");
      setError(formatError(loadError));
    }
  }, [projectId]);

  useEffect(() => { void reload(); }, [reload]);

  const changeNodeStatus = useCallback(async (node: StatusNode, status: string) => {
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
      onStatusUpdated();
    } catch (updateError) {
      setWorkspace(priorWorkspace);
      setError(formatError(updateError));
      return false;
    } finally {
      setStatusPendingId(null);
    }
    return true;
  }, [onStatusUpdated, workspace]);

  return { workspace, roadmap, state, error, statusPendingId, reload, changeNodeStatus };
}
