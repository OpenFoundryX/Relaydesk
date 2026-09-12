import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiSettings } from "@/components/settings/ai-settings";

const base = {
  provider: "anthropic",
  model: "claude-opus-5",
  baseUrl: null,
  dailyTokenBudget: 200000,
  enabled: false,
  keySuffix: null,
};

describe("AiSettings", () => {
  it("says the widget keeps working when AI is off", () => {
    render(<AiSettings config={base} />);
    expect(screen.getByText(/search and the message form/i)).toBeTruthy();
  });

  it("shows which key is installed without showing the key", () => {
    render(<AiSettings config={{ ...base, enabled: true, keySuffix: "1234" }} />);
    expect(screen.getByText(/…1234/)).toBeTruthy();
  });
});
