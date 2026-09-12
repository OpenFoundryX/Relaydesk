import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Home } from "@/components/widget/home";

/**
 * Direct tests of Home, in isolation from Panel.
 *
 * Why these can't all live in panel.test.tsx: `articleCount === 0` gates
 * Home out of Panel entirely (it opens straight on Compose, spec D7 /
 * slice 8) -- so a Panel-level test can never actually exercise Home's own
 * `articleCount > 0` guard on the "Search for help" card, only the outer
 * one that stops Home from mounting at all. Rendering Home directly is
 * what pins that inner guard rather than a guarantee the code provides by
 * a different route than the one under test.
 */
describe("Home", () => {
  const base = {
    workspaceName: "Beacon",
    articleCount: 12,
    onAsk: vi.fn(),
    onCompose: vi.fn(),
    onSearchHelp: vi.fn(),
  };

  it("hides Search for help when there are no articles to browse", () => {
    render(<Home {...base} articleCount={0} />);
    expect(screen.queryByText("Search for help")).toBeNull();
  });

  it("shows Search for help, with the article count, when there are articles", () => {
    render(<Home {...base} articleCount={21} />);
    expect(screen.getByText("Search for help")).toBeTruthy();
    expect(screen.getByText("Browse 21 articles")).toBeTruthy();
  });

  it("uses the singular for exactly one article", () => {
    render(<Home {...base} articleCount={1} />);
    expect(screen.getByText("Browse 1 article")).toBeTruthy();
  });

  it("switches to the Help tab when Search for help is clicked", () => {
    const onSearchHelp = vi.fn();
    render(<Home {...base} onSearchHelp={onSearchHelp} />);
    fireEvent.click(screen.getByText("Search for help"));
    expect(onSearchHelp).toHaveBeenCalledTimes(1);
  });

  it("offers Ask a question, and calls onAsk, when AI is configured", () => {
    const onAsk = vi.fn();
    render(<Home {...base} aiEnabled onAsk={onAsk} />);
    expect(screen.getByText("Ask a question")).toBeTruthy();
    expect(screen.getByText("Our AI answers from your help articles")).toBeTruthy();
    expect(screen.queryByText("Send us a message")).toBeNull();
    fireEvent.click(screen.getByText("Ask a question"));
    expect(onAsk).toHaveBeenCalledTimes(1);
  });

  it("offers Send us a message, and calls onCompose, without AI", () => {
    const onCompose = vi.fn();
    render(<Home {...base} onCompose={onCompose} />);
    expect(screen.getByText("Send us a message")).toBeTruthy();
    expect(screen.queryByText("Ask a question")).toBeNull();
    fireEvent.click(screen.getByText("Send us a message"));
    expect(onCompose).toHaveBeenCalledTimes(1);
  });

  it("greets the visitor by name, with the brighter line still reading How can we help?", () => {
    render(<Home {...base} name="Ada" />);
    expect(screen.getByText("Hello Ada.")).toBeTruthy();
    expect(screen.getByText("How can we help?")).toBeTruthy();
  });

  it("drops the Hello line entirely when no name is known", () => {
    render(<Home {...base} />);
    expect(screen.getByText("How can we help?")).toBeTruthy();
    expect(screen.queryByText(/^Hello/)).toBeNull();
  });

  it("names the workspace in the dark band", () => {
    render(<Home {...base} workspaceName="Acme Support" />);
    expect(screen.getByText("Acme Support")).toBeTruthy();
  });
});
