"use client";

import { useCallback, useRef, useState } from "react";

import { generateNodeContent, generateNodeResources, generatePracticeLesson, getNodeDetail, saveNodeNote, type NodeDetail } from "../../lib/api";
import { formatError } from "../../lib/errors";

export type DetailLoadState = "idle" | "loading" | "ready" | "error";
export type DetailAction = "content" | "practice" | "resources" | "note" | null;

export function useNodeDetail() {
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [state, setState] = useState<DetailLoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<DetailAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [noteContent, setNoteContent] = useState("");
  const requestRef = useRef(0);

  const open = useCallback(async (nodeId: number) => {
    const requestId = ++requestRef.current;
    setState("loading");
    setError(null);
    setActionError(null);
    setAction(null);
    setDetail(null);
    try {
      const next = await getNodeDetail(nodeId);
      if (requestId !== requestRef.current) return;
      setDetail(next);
      setNoteContent(next.note?.content ?? "");
      setState("ready");
    } catch (loadError) {
      if (requestId !== requestRef.current) return;
      setError(formatError(loadError));
      setState("error");
    }
  }, []);

  const close = useCallback(() => {
    ++requestRef.current;
    setState("idle");
    setError(null);
    setActionError(null);
    setAction(null);
  }, []);

  const run = useCallback(async (kind: Exclude<DetailAction, null>, operation: () => Promise<{ detail: NodeDetail; status?: string; error?: string | null }>) => {
    const requestId = ++requestRef.current;
    setAction(kind);
    setActionError(null);
    try {
      const result = await operation();
      if (requestId !== requestRef.current) return;
      setDetail(result.detail);
      if (kind === "note") setNoteContent(result.detail.note?.content ?? noteContent);
      if (result.status === "failed") setActionError(result.error ?? "当前操作失败，请检查模型配置后重试。");
    } catch (actionFailure) {
      if (requestId !== requestRef.current) return;
      setActionError(formatError(actionFailure));
    } finally {
      if (requestId === requestRef.current) setAction(null);
    }
  }, [noteContent]);

  const updateStatus = useCallback((status: string) => {
    setDetail((current) => current ? { ...current, status } : current);
  }, []);

  return {
    detail,
    state,
    error,
    action,
    actionError,
    noteContent,
    setNoteContent,
    open,
    close,
    run,
    updateStatus,
    generateContent: (nodeId: number, force: boolean) => run("content", () => generateNodeContent(nodeId, force)),
    generatePractice: (nodeId: number) => run("practice", () => generatePracticeLesson(nodeId)),
    generateResources: (nodeId: number) => run("resources", () => generateNodeResources(nodeId)),
    saveNote: (nodeId: number, content: string) => run("note", () => saveNodeNote(nodeId, content)),
  };
}
