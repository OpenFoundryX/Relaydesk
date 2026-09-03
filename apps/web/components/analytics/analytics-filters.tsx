"use client";

import { useState } from "react";
import { CalendarDays, Users } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { assignees, dateRanges } from "@/lib/mock/analytics";

export function AnalyticsFilters() {
  const [assignee, setAssignee] = useState("all");
  const [range, setRange] = useState("30d");

  return (
    <div className="flex items-center gap-2">
      <Select value={assignee} onValueChange={setAssignee}>
        <SelectTrigger className="w-44" aria-label="Filter by assignee">
          <span className="flex items-center gap-2 truncate">
            <Users className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          {assignees.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={range} onValueChange={setRange}>
        <SelectTrigger className="w-40" aria-label="Date range">
          <span className="flex items-center gap-2 truncate">
            <CalendarDays className="size-3.5 shrink-0 text-ink-400" />
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          {dateRanges.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
