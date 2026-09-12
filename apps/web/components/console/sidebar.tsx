"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  BookOpen,
  ChartLine,
  CircleCheck,
  CircleDashed,
  CircleDot,
  FileText,
  Globe,
  Inbox,
  Pause,
  Plus,
  Settings,
  ShieldBan,
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { CreateLabelButton } from "@/components/inbox/create-label-button";
import type { Label, SetupTask, StatusCount } from "@/lib/mock/types";
import { cn } from "@/lib/utils";

import { SetupProgress } from "./setup-progress";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  count?: number;
  /** Matches the `status` query param on /conversations. */
  status?: string;
  /**
   * Hidden from an agent. Set on the pages that exist only to configure the
   * workspace, which `requireAdmin` 404s for a non-admin — without this an
   * agent sees nav entries that lead nowhere.
   */
  adminOnly?: boolean;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

interface SidebarProps {
  statusCounts: StatusCount[];
  draftCount: number;
  setupTasks: SetupTask[];
  labels: Label[];
  isAdmin: boolean;
}

const settingsItems: NavItem[] = [
  { label: "Channels", href: "/settings/channels", icon: Inbox, adminOnly: true },
  {
    label: "Automations",
    href: "/settings/automations",
    icon: CircleDashed,
    adminOnly: true,
  },
  {
    label: "Integrations",
    href: "/settings/integrations",
    icon: Globe,
    adminOnly: true,
  },
  {
    label: "Custom webhooks",
    href: "/settings/custom-webhooks",
    icon: CircleDot,
    adminOnly: true,
  },
  {
    label: "Widget",
    href: "/settings/widget",
    icon: CircleDot,
    adminOnly: true,
  },
  {
    label: "AI answers",
    href: "/settings/ai",
    icon: CircleDot,
    adminOnly: true,
  },
  {
    label: "MCP servers",
    href: "/settings/mcp-servers",
    icon: CircleDot,
    adminOnly: true,
  },
  { label: "AI triage", href: "/settings/ai-triage", icon: CircleDot, adminOnly: true },
  {
    label: "Templates",
    href: "/settings/templates",
    icon: FileText,
    adminOnly: true,
  },
  { label: "API keys", href: "/settings/api-keys", icon: CircleDot, adminOnly: true },
  { label: "Team", href: "/settings/team", icon: CircleDot, adminOnly: true },
  { label: "Account", href: "/settings/account", icon: CircleDot },
];

const portalItems: NavItem[] = [
  { label: "General", href: "/user-portal/general", icon: CircleDot, adminOnly: true },
  {
    label: "Appearance",
    href: "/user-portal/appearance",
    icon: CircleDot,
    adminOnly: true,
  },
  {
    label: "Ticket form",
    href: "/user-portal/ticket-form",
    icon: CircleDot,
    adminOnly: true,
  },
  {
    label: "Knowledge base",
    href: "/user-portal/knowledge-base",
    icon: CircleDot,
    adminOnly: true,
  },
];

export function Sidebar({
  statusCounts,
  draftCount,
  setupTasks,
  labels,
  isAdmin,
}: SidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeStatus = searchParams.get("status") ?? "open";

  const visible = (items: NavItem[]) =>
    items.filter((item) => isAdmin || !item.adminOnly);

  const countFor = (status: string) =>
    statusCounts.find((entry) => entry.status === status)?.count ?? 0;

  if (pathname.startsWith("/settings")) {
    return (
      <SectionSidebar
        title="Settings"
        items={visible(settingsItems)}
        pathname={pathname}
      />
    );
  }

  if (pathname.startsWith("/user-portal")) {
    return (
      <SectionSidebar
        title="User portal"
        items={visible(portalItems)}
        pathname={pathname}
      />
    );
  }

  const groups: NavGroup[] = [
    {
      label: "Inbox",
      items: [
        {
          label: "Open",
          href: "/conversations?status=open",
          icon: CircleDot,
          count: countFor("open"),
          status: "open",
        },
        {
          label: "Pending",
          href: "/conversations?status=pending",
          icon: CircleDashed,
          count: countFor("pending"),
          status: "pending",
        },
        {
          label: "Resolved",
          href: "/conversations?status=resolved",
          icon: CircleCheck,
          count: countFor("resolved"),
          status: "resolved",
        },
        {
          label: "On hold",
          href: "/conversations?status=on_hold",
          icon: Pause,
          count: countFor("on_hold"),
          status: "on_hold",
        },
        {
          label: "All tickets",
          href: "/conversations?status=all",
          icon: Inbox,
          status: "all",
        },
        {
          label: "Drafts",
          href: "/conversations?status=drafts",
          icon: FileText,
          count: draftCount,
          status: "drafts",
        },
        {
          label: "Ignored",
          href: "/conversations?status=ignored",
          icon: ShieldBan,
          count: countFor("ignored"),
          status: "ignored",
        },
        {
          label: "Trash",
          href: "/conversations?status=trash",
          icon: Trash2,
          count: countFor("trash"),
          status: "trash",
        },
      ],
    },
    {
      label: "Workspace",
      items: [
        {
          label: "Analytics",
          href: "/analytics",
          icon: ChartLine,
          adminOnly: true,
        },
        { label: "Knowledge base", href: "/knowledge-base", icon: BookOpen },
        {
          label: "User portal",
          href: "/user-portal/general",
          icon: Globe,
          adminOnly: true,
        },
        { label: "Notifications", href: "/notifications", icon: Bell },
        { label: "Settings", href: "/settings", icon: Settings },
      ],
    },
  ];

  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-ink-200 bg-white">
      <div className="flex-1 overflow-y-auto px-2 py-3">
        {groups.map((group) => (
          <div key={group.label} className="mb-1">
            <GroupLabel>{group.label}</GroupLabel>
            {visible(group.items).map((item) => {
              const active = item.status
                ? pathname === "/conversations" && activeStatus === item.status
                : pathname.startsWith(item.href.split("?")[0]);
              return (
                <NavLink key={item.label} item={item} active={active} />
              );
            })}
          </div>
        ))}

        <div>
          <GroupLabel action={<CreateLabelButton />}>Labels</GroupLabel>
          {labels.map((label) => (
            <Link
              key={label.id}
              href={`/conversations?label=${label.id}`}
              className="group flex h-8 items-center rounded-md pl-2.5 pr-2 text-[13px] text-ink-600 transition-colors hover:bg-ink-100 hover:text-ink-900"
            >
              <span
                className={cn(
                  "mr-2 size-2 shrink-0 rounded-[3px]",
                  label.color === "citron" && "bg-accent-500",
                  label.color === "amber" && "bg-amber-400",
                  label.color === "rose" && "bg-rose-400",
                  label.color === "sky" && "bg-sky-400",
                  label.color === "slate" && "bg-ink-400",
                )}
              />
              <span className="truncate">{label.name}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Five of the six tasks lead to admin-only pages, so an agent
          would get a checklist whose next step 404s. */}
      {isAdmin && <SetupProgress tasks={setupTasks} />}
    </nav>
  );
}

function SectionSidebar({
  title,
  items,
  pathname,
}: {
  title: string;
  items: NavItem[];
  pathname: string;
}) {
  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-ink-200 bg-white">
      <div className="border-b border-ink-200 px-2 py-3">
        <Link
          href="/conversations?status=open"
          className="flex h-8 items-center gap-2 rounded-md px-2.5 text-[13px] text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
        >
          <ArrowLeft className="size-3.5" />
          Back to inbox
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <GroupLabel>{title}</GroupLabel>
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "relative flex h-8 items-center rounded-md px-2.5 text-[13px] transition-colors",
              pathname === item.href
                ? "bg-accent-100 font-medium text-ink-950"
                : "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
            )}
          >
            {pathname === item.href && <ActiveMarker />}
            {item.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "relative flex h-8 items-center rounded-md pl-2.5 pr-2 text-[13px] transition-colors",
        active
          ? "bg-accent-100 font-medium text-ink-950"
          : "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
      )}
    >
      {active && <ActiveMarker />}
      <Icon className={cn("mr-2 size-4", active ? "text-ink-700" : "text-ink-400")} />
      <span className="truncate">{item.label}</span>
      {item.count !== undefined && item.count > 0 && (
        <span
          className={cn(
            "ml-auto tabular text-[11px]",
            active ? "text-ink-600" : "text-ink-400",
          )}
        >
          {item.count}
        </span>
      )}
    </Link>
  );
}

function ActiveMarker() {
  return (
    <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-accent-600" />
  );
}

function GroupLabel({
  children,
  action,
}: {
  children: React.ReactNode;
  action?: string | React.ReactNode;
}) {
  return (
    <div className="flex h-7 items-center px-2.5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        {children}
      </span>
      {typeof action === "string" ? (
        <button
          type="button"
          aria-label={action}
          title={action}
          className="ml-auto rounded text-ink-400 transition-colors hover:text-ink-900"
        >
          <Plus className="size-3.5" />
        </button>
      ) : (
        action && <span className="ml-auto flex">{action}</span>
      )}
    </div>
  );
}
