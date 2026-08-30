import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { useProjectWorkspace } from "../features/workspace/useProjectWorkspace";
import { getProjectRoadmap, getProjectWorkspace, updateNodeStatus } from "../lib/api";
import { roadmap, workspace, workspaceNode } from "./fixtures";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, getProjectRoadmap: vi.fn(), getProjectWorkspace: vi.fn(), updateNodeStatus: vi.fn() };
});

function Harness({ onUpdated }: { onUpdated: () => void }) {
  const model = useProjectWorkspace(1, onUpdated);
  return <>
    <output>{model.workspace?.nodes[0]?.status ?? model.state}</output>
    <button type="button" onClick={() => void model.changeNodeStatus(workspaceNode, "mastered")}>更新状态</button>
  </>;
}

describe("useProjectWorkspace", () => {
  it("状态更新成功后采用服务端工作台并刷新项目摘要", async () => {
    vi.mocked(getProjectRoadmap).mockResolvedValue(roadmap);
    vi.mocked(getProjectWorkspace).mockResolvedValue(workspace);
    vi.mocked(updateNodeStatus).mockResolvedValue({ node: { id: 101, status: "mastered" }, workspace: { ...workspace, nodes: [{ ...workspaceNode, status: "mastered" }] } });
    const onUpdated = vi.fn();
    const user = userEvent.setup();
    render(<Harness onUpdated={onUpdated} />);
    await screen.findByText("pending");
    await user.click(screen.getByRole("button", { name: "更新状态" }));
    await screen.findByText("mastered");
    expect(onUpdated).toHaveBeenCalledOnce();
  });

  it("状态更新失败后回滚乐观状态", async () => {
    vi.mocked(getProjectRoadmap).mockResolvedValue(roadmap);
    vi.mocked(getProjectWorkspace).mockResolvedValue(workspace);
    vi.mocked(updateNodeStatus).mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<Harness onUpdated={vi.fn()} />);
    await screen.findByText("pending");
    await user.click(screen.getByRole("button", { name: "更新状态" }));
    await waitFor(() => expect(screen.getByText("pending")).toBeTruthy());
  });
});
