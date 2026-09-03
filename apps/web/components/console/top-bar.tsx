"use client";

import Link from "next/link";
import { ChevronDown, CircleUser, LogOut, Search, Settings } from "lucide-react";

import { Logo } from "@/components/console/logo";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface TopBarProps {
  workspaceName: string;
  userName: string;
  userMonogram: string;
}

export function TopBar({ workspaceName, userName, userMonogram }: TopBarProps) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-ink-200 bg-white px-4">
      <Link href="/conversations" className="rounded-md">
        <Logo />
      </Link>

      <span className="text-ink-300">/</span>

      <DropdownMenu>
        <DropdownMenuTrigger className="flex h-7 items-center gap-1.5 rounded-md px-2 text-[13px] font-medium text-ink-700 transition-colors hover:bg-ink-100">
          {workspaceName}
          <ChevronDown className="size-3.5 text-ink-400" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem>{workspaceName}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem>Create workspace</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="flex-1" />

      <button
        type="button"
        className="flex h-8 w-64 items-center gap-2 rounded-md border border-ink-200 bg-ink-50 px-2.5 text-[13px] text-ink-400 transition-colors hover:border-ink-300 hover:text-ink-600"
      >
        <Search className="size-3.5" />
        Search tickets
        <kbd className="ml-auto rounded border border-ink-200 bg-white px-1.5 font-mono text-[10px] text-ink-400">
          ⌘K
        </kbd>
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger className="rounded-full">
          <Avatar>
            <AvatarFallback>{userMonogram}</AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <div className="px-2.5 py-1.5 text-[13px] font-medium text-ink-900">
            {userName}
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link href="/settings/account">
              <CircleUser />
              Account
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/settings/channels">
              <Settings />
              Workspace settings
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem destructive>
            <LogOut />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
