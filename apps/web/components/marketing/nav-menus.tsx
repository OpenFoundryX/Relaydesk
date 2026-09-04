"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeftRight,
  BarChart3,
  BookOpen,
  Calendar,
  ChevronDown,
  Database,
  FileText,
  Globe,
  Inbox,
  Lightbulb,
  LifeBuoy,
  Receipt,
  Server,
  ShieldCheck,
  Tag,
  Webhook,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { BrandIcon } from "@/components/brand-icons";
import { competitors } from "@/lib/marketing/compare";
import { cn } from "@/lib/utils";

const REPO = "https://github.com/openfoundry/relaydesk";

interface MenuItem {
  icon: LucideIcon;
  title: string;
  description?: string;
  href: string;
}

const ticketing: MenuItem[] = [
  { icon: Inbox, title: "Unified inbox", description: "Email, Discord, portal, API", href: "/#product" },
  { icon: BarChart3, title: "Analytics", description: "See what the AI handles", href: "/#analytics" },
];

const aiAgent: MenuItem[] = [
  { icon: Database, title: "Connect your data", description: "Full account context", href: "/#agent" },
  { icon: Receipt, title: "Solve billing issues", description: "Refunds and cancellations", href: "/#agent" },
  { icon: Lightbulb, title: "Triage tickets", description: "Auto-assign and label", href: "/#triage" },
  { icon: Webhook, title: "Custom actions", description: "Webhooks and MCP servers", href: "/#agent" },
];

const knowledge: MenuItem[] = [
  { icon: Globe, title: "Hosted user portal", description: "Customer self-service", href: "/#portal" },
  { icon: BookOpen, title: "Internal knowledge base", description: "Your company docs", href: "/#portal" },
];

const resources: MenuItem[] = [
  { icon: FileText, title: "Documentation", description: "Setup, configuration, API", href: `${REPO}#readme` },
  { icon: Server, title: "Self-hosting guide", description: "Docker Compose in minutes", href: `${REPO}#start` },
  { icon: Tag, title: "Changelog", description: "What shipped recently", href: `${REPO}/releases` },
  { icon: LifeBuoy, title: "Support", description: "Get help from the team", href: `${REPO}/blob/main/SUPPORT.md` },
  { icon: ShieldCheck, title: "Security", description: "Report a vulnerability", href: `${REPO}/blob/main/SECURITY.md` },
];

export function PlatformMenu() {
  return (
    <NavDropdown label="Platform">
      <div className="grid w-[52rem] grid-cols-[1fr_15rem]">
        <div className="space-y-6 p-6">
          <MenuGroup title="Ticketing" items={ticketing} />
          <MenuGroup title="AI agent" items={aiAgent} />
          <MenuGroup title="Knowledge" items={knowledge} />
        </div>
        <div className="space-y-6 border-l border-ink-200 bg-ink-50 p-6">
          <div>
            <GroupTitle>Getting started</GroupTitle>
            <ul className="mt-2 space-y-0.5">
              <li>
                <SimpleLink href="/contact" icon={Calendar}>
                  Book a demo
                </SimpleLink>
              </li>
              <li>
                <SimpleLink href={REPO} icon={Server}>
                  Self-host it
                </SimpleLink>
              </li>
            </ul>
          </div>
          <div>
            <GroupTitle>Compare</GroupTitle>
            <ul className="mt-2 space-y-0.5">
              {competitors.map((competitor) => (
                <li key={competitor.slug}>
                  <SimpleLink href={`/compare/${competitor.slug}`} icon={ArrowLeftRight}>
                    vs {competitor.name}
                  </SimpleLink>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </NavDropdown>
  );
}

export function ResourcesMenu() {
  return (
    <NavDropdown label="Resources">
      <div className="w-72 p-3">
        <ul className="space-y-0.5">
          {resources.map((item) => (
            <li key={item.title}>
              <MenuLink item={item} />
            </li>
          ))}
        </ul>
        <Link
          href={REPO}
          className="mt-2 flex items-center gap-2 rounded-md border-t border-ink-200 px-3 pb-1 pt-3 text-[13px] text-ink-600 hover:text-ink-900"
        >
          <BrandIcon brand="github" mono className="size-3.5" />
          Star on GitHub
        </Link>
      </div>
    </NavDropdown>
  );
}

/**
 * Hover-and-click disclosure for the header. Opens on hover or click, closes
 * on Escape, on a click outside, when focus leaves, or when a link is chosen.
 */
function NavDropdown({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);

  const cancelClose = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = null;
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div
      ref={root}
      className="relative"
      onMouseEnter={() => {
        cancelClose();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
      onBlur={(event) => {
        if (!root.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={(event) => {
          // A mouse click follows a hover that already opened the menu, so it
          // should keep it open. Keyboard activation (detail === 0) toggles.
          if (event.detail === 0) setOpen((value) => !value);
          else setOpen(true);
        }}
        className={cn(
          "inline-flex h-8 items-center gap-1 rounded-md border px-2 text-[13px] font-medium transition-colors",
          open
            ? "border-accent-500 bg-accent-50 text-ink-900"
            : "border-transparent text-ink-600 hover:text-ink-900",
        )}
      >
        {label}
        <ChevronDown
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open && (
        <div className="absolute left-1/2 top-full z-30 -translate-x-1/2 pt-3">
          <div
            className="animate-content-in overflow-hidden rounded-xl border border-ink-200 bg-white shadow-overlay"
            onClick={(event) => {
              if ((event.target as HTMLElement).closest("a")) setOpen(false);
            }}
          >
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

function MenuGroup({ title, items }: { title: string; items: MenuItem[] }) {
  return (
    <div>
      <GroupTitle>{title}</GroupTitle>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5">
        {items.map((item) => (
          <li key={item.title}>
            <MenuLink item={item} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function GroupTitle({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{children}</p>
  );
}

function MenuLink({ item }: { item: MenuItem }) {
  return (
    <Link
      href={item.href}
      className="group flex items-start gap-3 rounded-md px-3 py-2 transition-colors hover:bg-ink-50"
    >
      <item.icon className="mt-0.5 size-4 shrink-0 text-ink-400 group-hover:text-ink-700" aria-hidden />
      <span>
        <span className="block text-[13px] font-medium text-ink-900">{item.title}</span>
        {item.description && (
          <span className="block text-[12px] text-ink-500">{item.description}</span>
        )}
      </span>
    </Link>
  );
}

function SimpleLink({ href, icon: Icon, children }: { href: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium text-ink-800 transition-colors hover:bg-white hover:text-ink-900"
    >
      <Icon className="size-3.5 text-ink-400 group-hover:text-ink-700" aria-hidden />
      {children}
    </Link>
  );
}
