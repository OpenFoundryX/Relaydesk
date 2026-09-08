import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "./metric-card";
import { formatDuration } from "@/lib/analytics";
import type { MetricSeries } from "@/lib/types";

const series: MetricSeries = {
  id: "resolution-time",
  label: "Avg time to resolve",
  headline: "4h 12m",
  delta: -8,
  format: "duration",
  points: [{ date: "2026-08-30", value: 15120 }],
};

describe("MetricCard", () => {
  it("renders the headline the API formatted", () => {
    render(<MetricCard series={series} />);

    expect(screen.getByText("4h 12m")).toBeTruthy();
  });

  it("renders no delta at all when there is none", () => {
    // A workspace's first period has nothing to compare against. An arrow
    // pointing somewhere would be an invention.
    render(<MetricCard series={{ ...series, delta: null }} />);

    expect(screen.queryByText("%", { exact: false })).toBeNull();
  });

  it("gives a falling duration the improving tone", () => {
    const { container } = render(<MetricCard series={series} />);

    expect(container.querySelector(".text-positive-600")).not.toBeNull();
  });

  it("gives a rising count the improving tone", () => {
    const created: MetricSeries = {
      ...series,
      id: "tickets-created",
      format: "count",
      headline: "412",
      delta: 40,
    };

    const { container } = render(<MetricCard series={created} />);

    expect(container.querySelector(".text-positive-600")).not.toBeNull();
  });

  it("does not congratulate a growing backlog", () => {
    // "Open backlog" is a count, but the only one where up is bad: 40% more
    // unanswered tickets was rendering in the same green as 40% more
    // tickets resolved.
    const backlog: MetricSeries = {
      ...series,
      id: "backlog",
      label: "Open backlog",
      format: "count",
      headline: "42",
      delta: 40,
    };

    const { container } = render(<MetricCard series={backlog} />);

    expect(container.querySelector(".text-positive-600")).toBeNull();
  });

  it("congratulates a shrinking backlog", () => {
    const backlog: MetricSeries = {
      ...series,
      id: "backlog",
      label: "Open backlog",
      format: "count",
      headline: "42",
      delta: -40,
    };

    const { container } = render(<MetricCard series={backlog} />);

    expect(container.querySelector(".text-positive-600")).not.toBeNull();
  });
});

describe("formatDuration", () => {
  it("renders hours and minutes at or above one hour", () => {
    expect(formatDuration(15120)).toBe("4h 12m");
  });

  it("renders minutes and seconds below one hour", () => {
    expect(formatDuration(504)).toBe("8m 24s");
  });

  it("drops the seconds when they are zero", () => {
    expect(formatDuration(480)).toBe("8m");
  });

  it("rounds the total duration before splitting to avoid impossible times", () => {
    expect(formatDuration(479.5)).toBe("8m");
  });
});
