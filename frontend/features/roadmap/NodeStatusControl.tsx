"use client";

import type { WorkspaceNode } from "../../lib/api";

export const statusLabels: Record<string, string> = {
  pending: "待开始",
  learning: "学习中",
  mastered: "已掌握",
  weak: "需复习",
  skipped: "已跳过",
};

type StatusNode = Pick<WorkspaceNode, "id" | "title" | "status">;

export function NodeStatusControl({ node, pending, onUpdate }: { node: StatusNode; pending: boolean; onUpdate: (status: string) => void }) {
  const options = ["pending", "learning", "mastered", "weak"];
  return (
    <div className="status-control" aria-label={`${node.title} 的学习状态`}>
      {options.map((status) => (
        <button
          key={status}
          type="button"
          className={`status-button ${node.status === status ? "active" : ""}`}
          disabled={pending}
          onClick={() => onUpdate(status)}
        >
          {statusLabels[status]}
        </button>
      ))}
    </div>
  );
}
