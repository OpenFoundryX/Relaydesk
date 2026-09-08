import { formatDuration } from "@/lib/analytics";
import type { AgentRow } from "@/lib/types";

/** The §4.7 table. Every column counts an action, so the headings say so --
 *  these are not the tickets somebody is holding, they are the ones they
 *  worked. There is deliberately no "Unassigned" row: an action has an
 *  actor. */
export function AgentTable({ rows }: { rows: AgentRow[] }) {
  return (
    <section className="rounded-lg border border-ink-200 bg-white p-5">
      <h2 className="text-[13px] font-medium text-ink-600">By agent</h2>
      {rows.length > 0 ? (
        <table className="mt-3 w-full">
          <thead>
            <tr className="border-b border-ink-200 text-left">
              <th className="pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Agent
              </th>
              {["Replied to", "First reply", "Resolved"].map((heading) => (
                <th
                  key={heading}
                  className="w-32 pb-2 text-right text-[11px] font-semibold uppercase tracking-wider text-ink-400"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.userId} className="border-b border-ink-200 last:border-b-0">
                <td className="py-2.5 text-[13px] font-medium text-ink-900">
                  {row.name}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.handled}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.firstResponseSeconds === null
                    ? "—"
                    : formatDuration(row.firstResponseSeconds)}
                </td>
                <td className="tabular py-2.5 text-right text-[13px] text-ink-600">
                  {row.resolved}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-3 text-[13px] text-ink-500">
          No replies or resolutions in this period.
        </p>
      )}
    </section>
  );
}
