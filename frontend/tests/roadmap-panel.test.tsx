import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RoadmapPanel } from "../features/roadmap/RoadmapPanel";
import { generateNodeContent, getNodeDetail } from "../lib/api";
import { nodeDetail, roadmap, workspaceNode } from "./fixtures";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, getNodeDetail: vi.fn(), generateNodeContent: vi.fn(), generateNodeResources: vi.fn(), generatePracticeLesson: vi.fn(), saveNodeNote: vi.fn() };
});

describe("RoadmapPanel", () => {
  it("从路线列表进入详情并返回", async () => {
    vi.mocked(getNodeDetail).mockResolvedValue(nodeDetail);
    const user = userEvent.setup();
    render(<RoadmapPanel roadmap={roadmap} nodes={[workspaceNode]} statusPendingId={null} onUpdateStatus={vi.fn().mockResolvedValue(true)} />);
    await user.click(screen.getByRole("button", { name: "查看 所有权 的详细内容" }));
    await screen.findByText("LESSON DETAIL / 课程详情");
    await user.click(screen.getByRole("button", { name: "返回学习路线" }));
    expect(screen.getByRole("button", { name: "查看 所有权 的详细内容" })).toBeTruthy();
  });

  it("详情生成失败时展示操作错误", async () => {
    vi.mocked(getNodeDetail).mockResolvedValue(nodeDetail);
    vi.mocked(generateNodeContent).mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<RoadmapPanel roadmap={roadmap} nodes={[workspaceNode]} statusPendingId={null} onUpdateStatus={vi.fn().mockResolvedValue(true)} />);
    await user.click(screen.getByRole("button", { name: "查看 所有权 的详细内容" }));
    await screen.findByText("生成课程");
    await user.click(screen.getByRole("button", { name: "生成课程" }));
    await screen.findByText("无法连接本地学习服务，请确认 FastAPI 已启动。");
  });
});
