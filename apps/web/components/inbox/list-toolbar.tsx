"use client";

import { ArrowUpDown, ListFilter } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ListToolbar({
  title,
  count,
  icon,
}: {
  title: string;
  count: number;
  icon?: ReactNode;
}) {
  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-ink-200 bg-white px-4">
      {icon && <span className="flex items-center [&_svg]:size-4">{icon}</span>}
      <h1 className="text-sm font-semibold tracking-tight text-ink-900">{title}</h1>
      <span className="tabular rounded-full bg-ink-100 px-2 py-0.5 text-[11px] text-ink-500">
        {count}
      </span>

      <div className="flex-1" />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Sort" title="Sort">
            <ArrowUpDown />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>Newest first</DropdownMenuItem>
          <DropdownMenuItem>Oldest first</DropdownMenuItem>
          <DropdownMenuItem>Priority</DropdownMenuItem>
          <DropdownMenuItem>Longest waiting</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Filter" title="Filter">
            <ListFilter />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>Assigned to me</DropdownMenuItem>
          <DropdownMenuItem>Unassigned</DropdownMenuItem>
          <DropdownMenuItem>Has an AI draft</DropdownMenuItem>
          <DropdownMenuItem>Urgent only</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
