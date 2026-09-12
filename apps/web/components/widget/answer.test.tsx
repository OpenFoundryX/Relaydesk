import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Answer } from "@/components/widget/answer";

const CITATIONS = [
  { number: 1, title: "Refunds", path: "billing/refunds" },
  { number: 2, title: "Invoices", path: "billing/invoices" },
];

describe("Answer", () => {
  it("renders bold and italic rather than printing the asterisks", () => {
    render(<Answer text="A **hard** and *soft* rule." citations={[]} />);
    expect(screen.getByText("hard").tagName).toBe("STRONG");
    expect(screen.getByText("soft").tagName).toBe("EM");
    expect(screen.queryByText(/\*\*/)).toBeNull();
  });

  it("renders a bullet list as a list", () => {
    render(<Answer text={"Reasons:\n- One\n- Two"} citations={[]} />);
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "One",
      "Two",
    ]);
  });

  it("turns a citation marker into a link to that article", () => {
    render(<Answer text="Within 14 days [1]." citations={CITATIONS} />);
    const link = screen.getByRole("link", { name: "1" });
    expect(link.getAttribute("href")).toBe("/help/billing/refunds");
    expect(link.getAttribute("target")).toBe("_blank");
  });

  it("drops a marker the server never issued", () => {
    // Spec D3: an invented citation produces no link. Printing "[9]" beside
    // real links would read as a broken one.
    render(<Answer text="See [9] for more." citations={CITATIONS} />);
    expect(screen.queryByRole("link", { name: "9" })).toBeNull();
    expect(screen.queryByText(/\[9\]/)).toBeNull();
  });

  it("never builds HTML from the model's text", () => {
    // The answer is untrusted (spec D7). React escapes text nodes, so the
    // tag arrives as literal characters rather than an element.
    const { container } = render(
      <Answer text={"<img src=x onerror=alert(1)> **ok**"} citations={[]} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });
});
