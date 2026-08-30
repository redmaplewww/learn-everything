import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "../app/page";
import { deleteProject, getDashboard, getProjectRoadmap, getProjectWorkspace, listProjects } from "../lib/api";
import { projectSummary, roadmap, workspace } from "./fixtures";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, listProjects: vi.fn(), getProjectRoadmap: vi.fn(), getProjectWorkspace: vi.fn(), getDashboard: vi.fn(), deleteProject: vi.fn() };
});

const jsProject = { ...projectSummary, id: 2, title: "JS 学习", topic: "学习 JS" };
const emptyDashboard = { project_id: 1, projects: [], metrics: { total_nodes: 1, mastered_nodes: 0, avg_mastery: 0, week_minutes: 0, due_cards: 0, total_cards: 0 }, status_counts: { pending: 1 }, heatmap: [], latest_report: "" };

describe("学习工作台组合根", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getProjectRoadmap).mockImplementation(async (projectId) => ({ ...roadmap, project_id: projectId }));
    vi.mocked(getProjectWorkspace).mockImplementation(async (projectId) => ({ ...workspace, project: { ...workspace.project, id: projectId, title: projectId === 2 ? "JS 学习" : "学习 Rust" } }));
    vi.mocked(getDashboard).mockResolvedValue(emptyDashboard);
  });

  it("首次选择首个项目，并在侧栏选择后加载对应工作台", async () => {
    vi.mocked(listProjects).mockResolvedValue([projectSummary, jsProject]);
    const user = userEvent.setup();
    render(<HomePage />);
    await screen.findByRole("heading", { name: "学习 Rust", level: 2 });
    await user.click(screen.getByRole("button", { name: /^JS 学习学习 JS0\/1 已完成$/ }));
    await screen.findByRole("heading", { name: "JS 学习", level: 2 });
    expect(getProjectWorkspace).toHaveBeenCalledWith(2);
  });

  it("删除当前项目后回退到剩余项目", async () => {
    vi.mocked(listProjects).mockResolvedValueOnce([projectSummary, jsProject]).mockResolvedValueOnce([projectSummary]);
    vi.mocked(deleteProject).mockResolvedValue({ project_id: 2, deleted: {} });
    const user = userEvent.setup();
    render(<HomePage />);
    await screen.findByRole("heading", { name: "学习 Rust", level: 2 });
    await user.click(screen.getByRole("button", { name: /^JS 学习学习 JS0\/1 已完成$/ }));
    await screen.findByRole("heading", { name: "JS 学习", level: 2 });
    await user.click(screen.getByRole("button", { name: "删除 JS 学习" }));
    await user.type(screen.getByRole("textbox"), "DELETE");
    await user.click(screen.getByRole("button", { name: "永久删除" }));
    await screen.findByRole("heading", { name: "学习 Rust", level: 2 });
    await waitFor(() => expect(deleteProject).toHaveBeenCalledWith(2, "DELETE"));
  });
});
