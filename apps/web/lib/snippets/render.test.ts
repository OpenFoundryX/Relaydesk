import { describe, expect, it } from "vitest";

import { SNIPPET_VARIABLES, renderSnippet, type SnippetContext } from "./render";

const context: SnippetContext = {
  customerName: "Priya Raman",
  customerEmail: "priya@northwind.io",
  ticketNumber: 412,
  ticketSubject: "Checkout fails with a 402",
  agentName: "Nilesh Pant",
  workspaceName: "Chronon",
};

describe("renderSnippet", () => {
  it("fills in every variable the dialog offers", () => {
    // The Variables menu in the snippet dialog is built from
    // SNIPPET_VARIABLES. Offering a placeholder the renderer does not know
    // would ship a snippet that reaches the customer with `{{...}}` still
    // in it, so the two are checked against each other here rather than
    // kept in step by hand.
    for (const variable of SNIPPET_VARIABLES) {
      expect(renderSnippet(variable, context), variable).not.toContain("{{");
    }
  });

  it("substitutes each variable with its value", () => {
    expect(renderSnippet("{{customer.first_name}}", context)).toBe("Priya");
    expect(renderSnippet("{{customer.email}}", context)).toBe("priya@northwind.io");
    expect(renderSnippet("{{ticket.id}}", context)).toBe("412");
    expect(renderSnippet("{{ticket.subject}}", context)).toBe(
      "Checkout fails with a 402",
    );
    expect(renderSnippet("{{agent.name}}", context)).toBe("Nilesh Pant");
    expect(renderSnippet("{{workspace.name}}", context)).toBe("Chronon");
  });

  it("keeps the surrounding text and replaces every occurrence", () => {
    expect(
      renderSnippet(
        "Hi {{customer.first_name}}, thanks — {{customer.first_name}}, one more thing.",
        context,
      ),
    ).toBe("Hi Priya, thanks — Priya, one more thing.");
  });

  it("leaves a placeholder it does not know alone", () => {
    // Nothing validates the vocabulary on the way into the database, so an
    // old or mistyped placeholder must survive as literal text rather than
    // becoming "undefined" in a reply to a customer.
    expect(renderSnippet("Order {{order.id}} refunded.", context)).toBe(
      "Order {{order.id}} refunded.",
    );
  });

  it("does not substitute a placeholder that came from a substituted value", () => {
    // `customerName` is the display name off an inbound email header, so it
    // is written by whoever sent the mail. A chain of `.replace()` calls
    // would let that value introduce a second placeholder and have the next
    // call expand it -- here, leaking the agent's name into a reply the
    // sender composed. One pass over the source string, so what a value
    // contains is only ever output.
    const hostile: SnippetContext = { ...context, customerName: "{{agent.name}}" };

    expect(renderSnippet("Hi {{customer.first_name}}", hostile)).toBe(
      "Hi {{agent.name}}",
    );
  });

  it("uses the first word of a customer's name", () => {
    expect(
      renderSnippet("{{customer.first_name}}", {
        ...context,
        customerName: "Priya Raman-Iyer",
      }),
    ).toBe("Priya");
  });

  it("uses the mailbox when the contact has no name but an address", () => {
    // A contact created from an address with no display name is stored with
    // the address as its name (see `services/contacts.py`), so this is the
    // ordinary case for a first-time emailer, not an edge case.
    expect(
      renderSnippet("Hi {{customer.first_name}},", {
        ...context,
        customerName: "priya@northwind.io",
      }),
    ).toBe("Hi priya,");
  });

  it("renders an empty customer name as nothing rather than undefined", () => {
    expect(
      renderSnippet("Hi {{customer.first_name}}", { ...context, customerName: "" }),
    ).toBe("Hi ");
  });
});
