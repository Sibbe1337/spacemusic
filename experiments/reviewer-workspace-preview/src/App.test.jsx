import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, within, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App.jsx";

const click = async (user, name) =>
  user.click(
    screen.getByRole("button", {
      name: name === "02 Review" ? /^02 Review/ : name,
      exact: true,
    }),
  );
async function openReview(user) {
  await click(user, "02 Review");
}
async function draft(user) {
  await openReview(user);
  await click(user, "Confirm these two fields");
  await click(user, "Prepare follow-up");
}
async function markReviewed(user) {
  await click(user, "Review message");
  await click(user, "Mark draft reviewed");
}

describe("interactive fictional workflow", () => {
  it("returns to the editor after Back to editing", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await click(user, "Review message");
    await click(user, "Back to editing");
    expect(document.activeElement).toBe(
      screen.getByLabelText("Follow-up draft"),
    );
  });
  it("traps keyboard focus and restores the dialog invoker", async () => {
    const user = userEvent.setup();
    render(<App />);
    await click(user, "Cases");
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close dialog" }),
    );
    await user.tab({ shift: true });
    expect(document.activeElement.textContent).toContain("CR-025");
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close dialog" }),
    );
    await click(user, "Close dialog");
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Cases", exact: true }),
    );
  });
  it.each(["edit", "switch", "reset"])(
    "ignores late clipboard feedback after %s",
    async (change) => {
      const user = userEvent.setup();
      render(<App />);
      await draft(user);
      await markReviewed(user);
      let finish;
      const pending = new Promise((resolve) => {
        finish = resolve;
      });
      const spy = vi
        .spyOn(navigator.clipboard, "writeText")
        .mockReturnValue(pending);
      await click(user, "Copy reviewed draft");
      if (change === "edit")
        fireEvent.change(screen.getByLabelText("Follow-up draft"), {
          target: { value: "New wording" },
        });
      if (change === "switch") {
        await click(user, "Cases");
        await user.click(screen.getByRole("button", { name: /CR-025/ }));
      }
      if (change === "reset") {
        await click(user, "Reset demo");
        await user.click(
          within(screen.getByRole("dialog")).getByRole("button", {
            name: "Reset demo",
          }),
        );
      }
      await act(async () => {
        finish();
        await pending;
      });
      expect(
        screen.queryByText("Draft copied. Nothing has been sent."),
      ).toBeNull();
      spy.mockRestore();
    },
  );
  it("discloses the scope and starts in overview", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Example Recordings",
    );
    expect(
      screen.getByText("Fictional cases only. No AI calls, uploads or emails."),
    ).toBeTruthy();
  });
  it("does not let the step navigation bypass classification", async () => {
    const user = userEvent.setup();
    render(<App />);
    await click(user, "03 Follow-up");
    expect(
      screen.getByRole("heading", { name: "Review the classification first." }),
    ).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("exposes all original sources without mutation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await openReview(user);
    await click(user, "royalty-statements.csv");
    expect(screen.getByText("Reporting period")).toBeTruthy();
    await click(user, "catalog-list.xlsx");
    expect(screen.getByText("Example Track A")).toBeTruthy();
    await click(user, "Application");
    expect(screen.getByText("50% of our master rights")).toBeTruthy();
  });
  it("keeps follow-up disabled until confirmation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await openReview(user);
    expect(
      screen.getByRole("button", { name: "Prepare follow-up" }).disabled,
    ).toBe(true);
    await click(user, "Confirm these two fields");
    expect(
      screen.getByRole("button", { name: "Prepare follow-up" }).disabled,
    ).toBe(false);
    expect(
      screen.getByText("Classification reviewed. Ownership is not verified."),
    ).toBeTruthy();
  });
  it("completes review and draft review without sending", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await markReviewed(user);
    expect(
      screen.getByRole("button", { name: "Copy reviewed draft" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^send/i })).toBeNull();
  });
  it("allows uncertainty rather than forcing a confident result", async () => {
    const user = userEvent.setup();
    render(<App />);
    await openReview(user);
    await click(user, "Mark both fields unclear");
    expect(screen.getByLabelText("Rights offered").value).toBe("Unclear");
    await click(user, "Prepare follow-up");
    expect(screen.getByLabelText("Follow-up draft").value).toContain(
      "Are you offering master rights",
    );
  });
  it("preserves custom text and asks before replacement", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    fireEvent.change(screen.getByLabelText("Follow-up draft"), {
      target: { value: "My custom questions" },
    });
    await click(user, "02 Review");
    await user.selectOptions(
      screen.getByLabelText("Rights offered"),
      "Publishing",
    );
    await click(user, "Confirm these two fields");
    await click(user, "Open follow-up draft");
    expect(screen.getByLabelText("Follow-up draft").value).toBe(
      "My custom questions",
    );
    expect(
      screen.getByRole("button", { name: "Review message" }).disabled,
    ).toBe(true);
    await click(user, "Replace with updated draft");
    expect(screen.getByRole("dialog")).toBeTruthy();
    await click(user, "Keep my draft");
    expect(screen.getByLabelText("Follow-up draft").value).toBe(
      "My custom questions",
    );
    await click(user, "Replace with updated draft");
    await click(user, "Replace draft");
    expect(document.activeElement).toBe(
      screen.getByLabelText("Follow-up draft"),
    );
    expect(screen.getByLabelText("Follow-up draft").value).toContain(
      "publishing interests",
    );
    expect(
      screen.getByRole("button", { name: "Review message" }).disabled,
    ).toBe(false);
  });
  it("removes the reviewed status when draft wording changes", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await markReviewed(user);
    fireEvent.change(screen.getByLabelText("Follow-up draft"), {
      target: { value: "Changed" },
    });
    expect(
      screen.queryByRole("button", { name: "Copy reviewed draft" }),
    ).toBeNull();
  });
  it("blocks a blank draft", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await user.clear(screen.getByLabelText("Follow-up draft"));
    expect(
      screen.getByRole("button", { name: "Review message" }).disabled,
    ).toBe(true);
    expect(screen.getByRole("alert").textContent).toContain("Add a message");
  });
  it("keeps case decisions separate across navigation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await click(user, "Cases");
    await user.click(screen.getByRole("button", { name: /CR-025/ }));
    await openReview(user);
    expect(screen.getByLabelText("Rights offered").value).toBe("Publishing");
    expect(screen.getByLabelText("Sale structure").value).toBe("Unclear");
    expect(
      screen.getByRole("button", { name: "Prepare follow-up" }).disabled,
    ).toBe(true);
    await click(user, "Cases");
    await user.click(screen.getByRole("button", { name: /CR-024/ }));
    await click(user, "03 Follow-up");
    expect(screen.getByLabelText("Follow-up draft").value).toContain(
      "master rights",
    );
  });
  it("reset requires confirmation and clears both cases", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await click(user, "Reset demo");
    await click(user, "Keep working");
    expect(screen.getByLabelText("Follow-up draft")).toBeTruthy();
    await click(user, "Reset demo");
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Reset demo",
      }),
    );
    await click(user, "03 Follow-up");
    expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("offers a manual fallback when clipboard access is blocked", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await markReviewed(user);
    const spy = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockRejectedValue(new Error("blocked"));
    await click(user, "Copy reviewed draft");
    expect(
      screen.getByText(
        "Clipboard is unavailable. Select and copy the draft text instead.",
      ),
    ).toBeTruthy();
    spy.mockRestore();
  });
  it("copies exactly the reviewed text", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    await markReviewed(user);
    const spy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    await click(user, "Copy reviewed draft");
    expect(spy).toHaveBeenCalledWith(
      screen.getByLabelText("Follow-up draft").value,
    );
    spy.mockRestore();
  });
  it("renders inserted markup as text rather than executable HTML", async () => {
    const user = userEvent.setup();
    render(<App />);
    await draft(user);
    fireEvent.change(screen.getByLabelText("Follow-up draft"), {
      target: { value: "<img src=x onerror=alert(1)>" },
    });
    await click(user, "Review message");
    expect(screen.getByRole("dialog").querySelector("img")).toBeNull();
    expect(
      within(screen.getByRole("dialog")).getByText(
        "<img src=x onerror=alert(1)>",
      ),
    ).toBeTruthy();
  });
});
