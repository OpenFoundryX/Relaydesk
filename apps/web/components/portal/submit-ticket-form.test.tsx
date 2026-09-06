import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SubmitTicketForm } from "./submit-ticket-form";

// The server action is not something jsdom can execute (it is a "use
// server" boundary, not an ordinary function), so every assertion here
// goes through this stand-in instead of the real thing.
const { submitTicketAction } = vi.hoisted(() => ({ submitTicketAction: vi.fn() }));
vi.mock("@/app/(portal)/submit-ticket/actions", () => ({ submitTicketAction }));

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/^Email/), {
    target: { value: "ada@example.dev" },
  });
  fireEvent.change(screen.getByLabelText(/^Message/), {
    target: { value: "Where is my order?" },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /submit ticket/i }));
}

beforeEach(() => {
  submitTicketAction.mockReset();
});

describe("SubmitTicketForm", () => {
  it("submits the typed values once and shows the success panel", async () => {
    submitTicketAction.mockResolvedValue({ ok: true });
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText("Subject"), {
      target: { value: "Refund" },
    });
    submit();

    await screen.findByText("Ticket received");

    expect(submitTicketAction).toHaveBeenCalledTimes(1);
    const form = submitTicketAction.mock.calls[0][0] as FormData;
    expect(form.get("email")).toBe("ada@example.dev");
    expect(form.get("message")).toBe("Where is my order?");
    expect(form.get("name")).toBe("Ada Lovelace");
    expect(form.get("subject")).toBe("Refund");
    // Untouched by a human filling the form normally.
    expect(form.get("company")).toBe("");
  });

  // The bug this whole slice exists to fix: a failure must never render
  // the same panel a success does. If this behaviour regressed back to
  // `setSubmitted(true)` unconditionally, this is the test that would
  // catch it.
  it("shows the failure reason and never the success panel", async () => {
    submitTicketAction.mockResolvedValue({
      ok: false,
      message: "That message is too long.",
    });
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    submit();

    await screen.findByText("That message is too long.");

    expect(screen.queryByText("Ticket received")).toBeNull();
    // The form is still here to retry with -- a failure does not clear it.
    expect(screen.getByRole("button", { name: /submit ticket/i })).toBeDefined();
  });

  it("shows a distinct reason for a 429 than for a 422", async () => {
    submitTicketAction.mockResolvedValue({
      ok: false,
      message: "We could not accept that just now.",
    });
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    submit();

    await screen.findByText("We could not accept that just now.");
    expect(screen.queryByText("That message is too long.")).toBeNull();
  });

  // The action rethrows anything that isn't a recognized API error (a
  // genuine network failure, a malformed response). Without a catch around
  // the awaited call, that rejection would leave `status` pinned at
  // "submitting" forever -- not the original looks-like-success bug, but
  // still not one of the form's three real states, and this is the test
  // that would catch a regression back to that.
  it("reaches the failed state, not a stuck submitting state, if the action rejects", async () => {
    submitTicketAction.mockRejectedValue(new Error("network down"));
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    submit();

    await screen.findByText(/couldn't reach the server/i);

    expect(screen.queryByText("Ticket received")).toBeNull();
    expect(screen.queryByText("Submitting…")).toBeNull();
    const button = screen.getByRole("button", { name: /submit ticket/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("keeps the honeypot empty, hidden from a keyboard, and out of the tab order", () => {
    render(<SubmitTicketForm workspaceName="Chronon" />);

    const company = screen.getByLabelText("Company") as HTMLInputElement;
    expect(company.value).toBe("");
    expect(company.tabIndex).toBe(-1);
    expect(company.getAttribute("autocomplete")).toBe("off");
    // CSS-hidden, not `type="hidden"` -- see the comment in
    // submit-ticket-form.tsx for why a merely-hidden-by-type field is not
    // enough of a honeypot.
    expect(company.getAttribute("type")).toBe("text");
    expect(company.closest("[aria-hidden='true']")).not.toBeNull();
  });

  it("does not call the action while a field required for submission is empty", () => {
    render(<SubmitTicketForm workspaceName="Chronon" />);

    submit();

    expect(submitTicketAction).not.toHaveBeenCalled();
  });
});

describe("SubmitTicketForm honesty", () => {
  it("does not promise a confirmation email, because none is sent", async () => {
    submitTicketAction.mockResolvedValue({ ok: true });
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    submit();

    await screen.findByText("Ticket received");

    // Nothing queues a confirmation and the design says there is none. The
    // panel used to say "We have sent a confirmation to ...", which left
    // every customer waiting for mail that was never coming.
    expect(screen.queryByText(/we have sent a confirmation/i)).toBeNull();
    expect(screen.queryByText(/confirmation/i)).toBeNull();
    // What it does say is true: the team has it and will reply by email.
    expect(screen.getByText(/will reply to ada@example\.dev/i)).toBeDefined();
  });

  it("offers no working attachment control, and claims none", () => {
    render(<SubmitTicketForm workspaceName="Chronon" />);

    // The control used to push fabricated filenames into React state with
    // no file input behind it and no `files` part ever sent -- a customer
    // watched "screenshot-1.png" appear in a list and then submitted a
    // ticket without it. Disabled and labelled instead.
    const button = screen.getByRole("button", {
      name: /add attachment/i,
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText("Coming soon")).toBeDefined();

    fireEvent.click(button);
    expect(screen.queryByText(/screenshot-1\.png/)).toBeNull();
  });

  it("does not advertise attachment limits the API does not have", () => {
    render(<SubmitTicketForm workspaceName="Chronon" />);

    // The old copy said "Images, video, and PDF. Up to 10MB each." The API
    // accepts four image types sharing a single 25MB budget, so every part
    // of that sentence was wrong.
    expect(screen.queryByText(/10MB/i)).toBeNull();
    expect(screen.queryByText(/video/i)).toBeNull();
    expect(screen.queryByText(/PDF/i)).toBeNull();
  });

  it("sends no files part, matching what the form can actually collect", async () => {
    submitTicketAction.mockResolvedValue({ ok: true });
    render(<SubmitTicketForm workspaceName="Chronon" />);

    fillRequiredFields();
    submit();

    await screen.findByText("Ticket received");

    const form = submitTicketAction.mock.calls[0][0] as FormData;
    expect(form.getAll("files")).toEqual([]);
  });
});
