"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  Tooltip as InfoTooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";
import { formatDuration } from "@/lib/analytics";
import type { MetricSeries } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatTickDate(iso: string) {
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

export function MetricCard({ series }: { series: MetricSeries }) {
  const isDuration = series.format === "duration";
  const formatValue = (value: number) =>
    isDuration ? formatDuration(value) : String(value);

  // For durations a fall is an improvement, so the tone flips.
  const improving =
    series.delta === null ? null : isDuration ? series.delta < 0 : series.delta > 0;

  return (
    <section className="rounded-lg border border-ink-200 bg-white p-5">
      <header className="flex items-center gap-1.5">
        <h2 className="text-[13px] font-medium text-ink-600">{series.label}</h2>
        {series.hint && (
          <InfoTooltip>
            <TooltipTrigger className="rounded text-ink-400 transition-colors hover:text-ink-700">
              <Info className="size-3.5" />
            </TooltipTrigger>
            <TooltipContent>{series.hint}</TooltipContent>
          </InfoTooltip>
        )}
      </header>

      <div className="mt-1 flex items-baseline gap-2.5">
        <span className="tabular text-2xl font-semibold tracking-tight text-ink-900">
          {series.headline}
        </span>
        {series.delta !== null && (
          <span
            className={cn(
              "flex items-center gap-1 text-[12px] font-medium",
              improving ? "text-positive-600" : "text-ink-500",
            )}
          >
            {series.delta > 0 ? (
              <TrendingUp className="size-3.5" />
            ) : (
              <TrendingDown className="size-3.5" />
            )}
            {Math.abs(series.delta)}%
          </span>
        )}
      </div>

      <div className="mt-4 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={series.points}
            margin={{ top: 4, right: 4, bottom: 0, left: -8 }}
          >
            <defs>
              <linearGradient id={`fill-${series.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#C4E538" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#C4E538" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="#E4E4E7"
              strokeDasharray="2 4"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatTickDate}
              tickLine={false}
              axisLine={{ stroke: "#E4E4E7" }}
              minTickGap={28}
              tick={{ fill: "#A1A1AA", fontSize: 11 }}
            />
            <YAxis
              tickFormatter={formatValue}
              tickLine={false}
              axisLine={false}
              width={46}
              tick={{ fill: "#A1A1AA", fontSize: 11 }}
            />
            <Tooltip
              cursor={{ stroke: "#D4D4D8", strokeDasharray: "3 3" }}
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #E4E4E7",
                fontSize: 12,
                boxShadow: "0 10px 20px -15px rgb(9 9 11 / 0.3)",
              }}
              labelFormatter={(value) => formatTickDate(String(value))}
              formatter={(value) => [formatValue(Number(value ?? 0)), series.label]}
            />
            <Area
              type="monotone"
              dataKey="value"
              // Recharts animates the reveal with rAF, which Chrome throttles in
              // a background tab -- the chart then stays blank until focus.
              isAnimationActive={false}
              stroke="#6E8225"
              strokeWidth={2}
              fill={`url(#fill-${series.id})`}
              dot={false}
              activeDot={{ r: 3, fill: "#18181B", stroke: "#fff", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
