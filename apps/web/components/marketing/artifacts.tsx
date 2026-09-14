import { cn } from "@/lib/utils";

/**
 * The floating product artifact surface.
 *
 * These are the ONLY elements in the Steep system that carry elevation --
 * content cards (mist and peach) stay flat. Everything that floats is a
 * fragment of the real product, cropped: a channel table, a stat with a
 * gestural line, the widget, the inbox.
 */
export function Artifact({
  className,
  style,
  children,
}: {
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <div
      style={style}
      className={cn(
        // `min-w-0` because artifacts are usually grid or flex children, and
        // those default to a min-content floor -- one unbreakable URL inside
        // would otherwise widen the whole column past the viewport.
        "min-w-0 rounded-elevated bg-paper-white shadow-artifact",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** A label above an artifact's contents. Typographic, never a badge. */
function ArtifactLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[14px] font-normal text-ash-gray">{children}</p>
  );
}

/**
 * Where tickets arrive, as a cropped table. Steep's "region table" slot: five
 * rows, no chrome, no header row styling beyond a recessive label.
 */
export function ChannelTable({ className }: { className?: string }) {
  const rows = [
    { channel: "Email", count: "412", share: "58%" },
    { channel: "Widget", count: "186", share: "26%" },
    { channel: "Discord", count: "74", share: "10%" },
    { channel: "Portal", count: "29", share: "4%" },
    { channel: "API", count: "14", share: "2%" },
  ];

  return (
    <Artifact className={cn("px-5 pb-3 pt-4", className)}>
      <ArtifactLabel>Tickets by channel</ArtifactLabel>
      <table className="mt-3 w-full">
        <tbody>
          {rows.map((row) => (
            <tr key={row.channel} className="border-t border-hairline">
              <td className="py-2 text-[15px] font-normal text-ink-black">
                {row.channel}
              </td>
              <td className="tabular py-2 text-right text-[15px] font-w450 text-ink-black">
                {row.count}
              </td>
              <td className="tabular w-12 py-2 text-right text-[14px] text-slate-gray">
                {row.share}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Artifact>
  );
}

/**
 * A metric with a gestural line. No axes and no gridlines by design -- the
 * stroke is the only place outside a peach surface where sienna is allowed.
 *
 * `trend` is not decoration: a card reading "down from 11m" under a rising
 * line is a chart that contradicts its own caption, so the direction is
 * required rather than defaulted.
 */
const trendPaths = {
  up: "M2 38 C 22 36, 34 30, 52 31 S 84 20, 104 17 S 140 10, 178 4",
  down: "M2 6 C 22 8, 34 14, 52 13 S 84 24, 104 27 S 140 34, 178 40",
} as const;

export function StatCard({
  label,
  value,
  delta,
  trend,
  className,
}: {
  label: string;
  value: string;
  delta: string;
  trend: "up" | "down";
  className?: string;
}) {
  return (
    <Artifact className={cn("px-5 pb-4 pt-4", className)}>
      <ArtifactLabel>{label}</ArtifactLabel>
      <p className="mt-2 text-body-lg font-medium text-ink-black">{value}</p>
      <p className="mt-0.5 text-[14px] text-slate-gray">{delta}</p>
      <svg
        viewBox="0 0 180 44"
        fill="none"
        className="mt-3 h-11 w-full"
        aria-hidden
      >
        {/* pathLength normalises the path to 1, so a single keyframe can
            draw any of these lines without knowing its real length. */}
        <path
          d={trendPaths[trend]}
          pathLength={1}
          strokeDasharray={1}
          className="animate-draw-line"
          stroke="#5d2a1a"
          strokeWidth="1.75"
          strokeLinecap="round"
          fill="none"
        />
      </svg>
    </Artifact>
  );
}

/**
 * A radial ring, the other chart shape Steep uses. Same sienna stroke, same
 * absence of chrome.
 */
export function RingCard({
  label,
  value,
  percent,
  className,
}: {
  label: string;
  value: string;
  percent: number;
  className?: string;
}) {
  return (
    <Artifact className={cn("flex items-center gap-4 px-5 py-4", className)}>
      <svg viewBox="0 0 60 60" className="size-[60px] shrink-0" aria-hidden>
        <circle cx="30" cy="30" r="26" stroke="#f2f2f3" strokeWidth="5" fill="none" />
        {/* Normalised to pathLength 1, so `--ring-to` is just the remaining
            fraction and the sweep stops exactly on the stated percentage. */}
        <circle
          cx="30"
          cy="30"
          r="26"
          pathLength={1}
          strokeDasharray={1}
          className="animate-draw-ring"
          style={
            { "--ring-to": 1 - percent / 100 } as React.CSSProperties
          }
          stroke="#5d2a1a"
          strokeWidth="5"
          strokeLinecap="round"
          fill="none"
          transform="rotate(-90 30 30)"
        />
      </svg>
      <div className="min-w-0">
        <ArtifactLabel>{label}</ArtifactLabel>
        <p className="mt-1 text-body-lg font-medium text-ink-black">{value}</p>
      </div>
    </Artifact>
  );
}

/** The self-hosting commands, as an artifact rather than a dark terminal. */
export function CodeArtifact({ className }: { className?: string }) {
  return (
    <Artifact className={cn("px-5 pb-5 pt-4", className)}>
      <ArtifactLabel>Terminal</ArtifactLabel>
      <pre className="mt-3 overflow-x-auto font-mono text-[13.5px] leading-relaxed text-ink-black">
        <code>{`git clone https://github.com/openfoundry/relaydesk
cd relaydesk
cp .env.example .env
docker compose up --build`}</code>
      </pre>
      <p className="mt-3 border-t border-hairline pt-3 font-mono text-[13px] text-slate-gray">
        Console localhost:3000 · API localhost:8000
      </p>
    </Artifact>
  );
}
