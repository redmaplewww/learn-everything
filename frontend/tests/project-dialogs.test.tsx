import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProjectDeletionDialog } from "../features/projects/ProjectDeletionDialog";
import { ProjectEditDialog } from "../features/projects/ProjectEditDialog";
import { workspace, projectSummary } from "./fixtures";

describe("项目弹窗", () => {
  it("编辑弹窗提交完整项目字段", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ProjectEditDialog project={workspace.project} saving={false} error={null} onClose={vi.fn()} onSave={onSave} />);
    await user.clear(screen.getByDisplayValue("学习 Rust"));
    await user.type(screen.getByLabelText("项目名称"), "Rust 进阶");
    await user.click(screen.getByRole("button", { name: "保存修改" }));
    expect(onSave).toHaveBeenCalledWith({ title: "Rust 进阶", topic: "Rust", background: "", goal: "", weekly_hours: 8 });
  });

  it("删除弹窗仅在输入 DELETE 后允许确认", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<ProjectDeletionDialog project={projectSummary} deleting={false} error={null} onClose={vi.fn()} onConfirm={onConfirm} />);
    const button = screen.getByRole("button", { name: "永久删除" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByRole("textbox"), "DELETE");
    expect((button as HTMLButtonElement).disabled).toBe(false);
    await user.click(button);
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
