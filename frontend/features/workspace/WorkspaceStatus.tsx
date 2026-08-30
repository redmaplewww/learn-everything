"use client";

import { AlertCircle, BookOpenCheck, LoaderCircle, RotateCcw } from "lucide-react";

import type { WorkspaceLoadState } from "./useProjectWorkspace";

export function WorkspaceStatus({ state, error, onRetry }: { state: WorkspaceLoadState; error: string | null; onRetry: () => void }) {
  if (state === "loading") {
    return <main className="workspace-state"><LoaderCircle className="spin" size={28} /> 正在加载学习工作台</main>;
  }
  if (state === "error") {
    return (
      <main className="workspace-state">
        <AlertCircle size={30} />
        <strong>项目数据暂时不可用</strong>
        <span>{error}</span>
        <button type="button" className="command-button" onClick={onRetry}><RotateCcw size={16} />重新加载</button>
      </main>
    );
  }
  return (
    <main className="workspace-state">
      <BookOpenCheck size={34} />
      <strong>选择一个项目</strong>
      <span>这里会显示路线、学习内容和当前进度。</span>
    </main>
  );
}
