import type { BrandSlug } from "@/components/brand-icons";
import type { PublicAuthor } from "@/lib/api/public";

/**
 * Domain types for the Relaydesk console.
 *
 * Some of these (e.g. `Workspace`, `CurrentUser`) are now the real shape of
 * API responses, fetched by getters in `lib/api/*`. The rest still back the
 * in-memory stores under `lib/mock/*` until each area gets its own endpoint.
 */

export type ConversationStatus =
  | "open"
  | "pending"
  | "resolved"
  | "on_hold"
  | "ignored"
  | "trash";
export type Priority = "urgent" | "high" | "medium" | "low";
export type Channel = "email" | "discord" | "portal" | "api";

export interface Label {
  id: string;
  name: string;
  color: "citron" | "slate" | "amber" | "rose" | "sky";
}

export interface Conversation {
  id: string;
  subject: string;
  preview: string;
  customerName: string;
  customerEmail: string;
  channel: Channel;
  status: ConversationStatus;
  priority: Priority;
  /** Human-readable age, e.g. "12m", "3h", "2d". */
  age: string;
  assignee: string | null;
  /** Stable id for mutations; `assignee` stays the display name. */
  assigneeId: string | null;
  labelIds: string[];
  hasDraft: boolean;
  unread: boolean;
  /** Sequential ticket number shown in the details panel. */
  number: number;
  /** Short calendar label for the list, e.g. "Sep 3". */
  date: string;
  /** AI-written summary of the thread, once one has been generated. */
  summary: string | null;
  summaryState: "none" | "ready" | "failed";
}

export interface Attachment {
  id: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
}

export interface Message {
  id: string;
  author: string;
  /** Address the message was sent to, shown in the bubble header. */
  to: string;
  role: "customer" | "agent" | "ai" | "system";
  body: string;
  sentAt: string;
  attachments: Attachment[];
  deliveryState: "none" | "queued" | "sent" | "failed";
}

export type ActivityKind = "created" | "status" | "priority" | "assignee" | "label" | "reply";

export interface ActivityEvent {
  id: string;
  conversationId: string;
  actor: string;
  kind: ActivityKind;
  /** Human-readable fragment after the actor, e.g. "marked this as". */
  verb: string;
  /** The value that changed, e.g. "Resolved" or a label name. */
  value: string;
  /** Status value when the event is a status change, for the pill. */
  status?: ConversationStatus;
  at: string;
}

export interface StatusCount {
  status: ConversationStatus;
  count: number;
}

export interface MetricPoint {
  /** ISO date, e.g. "2026-08-14". */
  date: string;
  value: number;
}

export interface MetricSeries {
  id: string;
  label: string;
  hint?: string;
  headline: string;
  /** Percentage change against the previous period; negative is a decrease. */
  delta: number | null;
  /** "count" renders bare integers, "duration" renders 4m 20s style ticks. */
  format: "count" | "duration";
  points: MetricPoint[];
}

export interface AgentRow {
  userId: string;
  name: string;
  handled: number;
  /** Null when this member never opened a thread; the table shows an em dash. */
  firstResponseSeconds: number | null;
  resolved: number;
}

export interface AnalyticsResponse {
  series: MetricSeries[];
  agents: AgentRow[];
}

export type ArticleStatus = "draft" | "ready" | "published";

/** Internal articles are procedures for the AI agent; external ones are the customer-facing help site. */
export type KbScope = "internal" | "external";

/**
 * An entry in `GET /kb/articles` -- no `doc`, no `publishedAt`. The list
 * page only ever renders title, excerpt, status and updatedAt, so the API
 * doesn't ship every article's full ProseMirror document just to fill a
 * list row.
 */
export interface KbArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  status: ArticleStatus;
  categoryId: string;
  updatedAt: string;
}

export interface KbArticle extends KbArticleSummary {
  /**
   * The article body as ProseMirror JSON. `unknown` on purpose: nothing in
   * the console reads into it by hand -- the editor round-trips it through
   * TipTap, and `DocRenderer` walks it defensively through a fixed node
   * table. Typing it as a shape would invite code that trusts that shape.
   */
  doc: unknown;
  /** When it first went live. Stays set after an unpublish; `status` says whether it is live now. */
  publishedAt: string | null;
  /**
   * Who wrote it. The preview renders the help site's own `ArticleView`,
   * byline and all, so it needs the same author the public API sends --
   * a preview missing the byline is previewing a different page. Null
   * where their account has been deleted.
   */
  author: PublicAuthor | null;
}

export interface KbCategory {
  id: string;
  name: string;
  slug: string;
  scope: KbScope;
  position: number;
  articleCount: number;
  /** Null for a root collection. */
  parentId: string | null;
  /** 0 for a root, 2 at the deepest the help site renders. */
  depth: number;
  /** The blurb under the name on the help site's card. */
  description: string;
  /** A name from the fixed set in `components/portal/category-icon.tsx`. */
  icon: string;
}

export interface Snippet {
  id: string;
  title: string;
  content: string;
}

export type ApiKeyScope =
  | "conversations:read"
  | "conversations:write"
  | "messages:write"
  | "contacts:read"
  | "labels:read"
  | "labels:write";

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: ApiKeyScope[];
  createdAt: string;
  lastUsedAt: string | null;
}

export interface ApiKeyCreated {
  token: string;
  key: ApiKey;
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface WebhookParam {
  name: string;
  type: "string" | "number" | "boolean";
  description: string;
  required: boolean;
}

export interface Webhook {
  id: string;
  name: string;
  description: string;
  method: HttpMethod;
  url: string;
  params: WebhookParam[];
}

export interface McpServer {
  id: string;
  name: string;
  description: string;
  url: string;
  active: boolean;
  toolCount: number;
}

export type IntegrationCategory =
  | "Notifications"
  | "Payments"
  | "Data"
  | "Development";

export interface Integration {
  id: string;
  name: string;
  category: IntegrationCategory;
  /** Vendor mark. Absent when Simple Icons has none, e.g. DynamoDB. */
  brand?: BrandSlug;
  /** Fallback shown when `brand` is absent. */
  monogram: string;
  connected: boolean;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "Admin" | "Agent";
  status: "active" | "invited";
  /** The underlying user id, for assignment. Null for a pending invite — you cannot assign a ticket to someone who has not accepted yet. */
  userId: string | null;
}

export interface Plan {
  id: string;
  name: string;
  price: string;
  cadence: string;
  blurb: string;
  cta: string;
  features: string[];
  featured: boolean;
  meteredOptions?: string[];
}

export interface SetupTask {
  id: string;
  label: string;
  href: string;
  done: boolean;
}

export interface PortalSettings {
  name: string;
  subdomain: string;
  domain: string;
  status: "deployed" | "draft";
  headline: string;
  intro: string;
  accent: string;
}

export interface ChannelAccount {
  id: string;
  address: string;
  displayName: string;
  active: boolean;
}

/** Mock-only until Discord ships in a later slice. */
export interface DiscordAccount {
  id: string;
  label: string;
}

export interface ImportSource {
  id: string;
  name: string;
  host: string;
  /** Vendor mark. Absent when Simple Icons has none, e.g. Freshdesk. */
  brand?: BrandSlug;
  /** Fallback shown when `brand` is absent. */
  monogram: string;
  comingSoon: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  /**
   * The subdomain label the workspace is reached at. Its public help site is
   * served at `<slug>.<portal domain>`, and a rename never changes it --
   * it is the address of everything already published there.
   */
  slug: string;
  monogram: string;
  seats: number;
}

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  monogram: string;
  timeZone: string;
  notifyOnAssignment: boolean;
}

/** Display order for statuses. A fixed enumeration, not data. */
export const statuses: ConversationStatus[] = [
  "open",
  "pending",
  "resolved",
  "on_hold",
  "ignored",
  "trash",
];
