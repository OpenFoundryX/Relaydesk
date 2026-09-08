"use client";

import { CalendarDays, Users } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RANGES } from "@/lib/analytics";

/** The URL a filter change navigates to. Pure, so the routing decision is
 *  testable without a Select. Omits defaults so the common case is a clean
 *  `/analytics`. */
export function filterHref(
  pathname: string,
  range: string,
  assignee: string | null,
): string {
  const query = new URLSearchParams();
  if (range !== "30d") query.set("range", range);
  if (assignee) query.set("assignee", assignee);
  const suffix = query.toString();
  return suffix ? `${pathname}?${suffix}` : pathname;
}

export function AnalyticsFilters({
  team,
  range,
  assignee,
}: {
  team: { id: string; name: string }[];
  range: string;
  assignee: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-2">
      <Select
        value={assignee ?? "all"}
        onValueChange={(next) =>
          router.replace(filterHref(pathname, range, next === "all" ? null : next))
        }
      >
        <SelectTrigger className="w-44" aria-label="Filter by assignee">
          <span className="flex items-center gap-2 truncate">
            <Users className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All assignees</SelectItem>
          {team.map((member) => (
            <SelectItem key={member.id} value={member.id}>
              {member.name}
            </SelectItem>
          ))}
          <SelectItem value="unassigned">Unassigned</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={range}
        onValueChange={(next) => router.replace(filterHref(pathname, next, assignee))}
      >
        <SelectTrigger className="w-40" aria-label="Date range">
          <span className="flex items-center gap-2 truncate">
            <CalendarDays className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          {RANGES.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
