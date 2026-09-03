/**
 * Domain types for the Relaydesk console.
 *
 * These are deliberately shaped like the API responses we expect to fetch
 * later, so wiring the real backend means changing the body of each getter in
 * `lib/mock/*` rather than touching any page.
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

export interface Message {
  id: string;
  author: string;
  /** Address the message was sent to, shown in the bubble header. */
  to: string;
  role: "customer" | "agent" | "ai";
  body: string;
  sentAt: string;
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

export type ArticleStatus = "draft" | "ready" | "published";

export interface KbArticle {
  id: string;
  title: string;
  excerpt: string;
  status: ArticleStatus;
  updatedAt: string;
}

export interface KbCategory {
  id: string;
  name: string;
  articles: KbArticle[];
}

export interface Snippet {
  id: string;
  title: string;
  content: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  createdAt: string;
  lastUsedAt: string | null;
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
  /** Two-letter monogram shown in the tile, since we ship no vendor logos. */
  monogram: string;
  connected: boolean;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "Admin" | "Agent";
  status: "active" | "invited";
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
  kind: "email" | "discord";
  label: string;
  detail: string;
}

export interface ImportSource {
  id: string;
  name: string;
  host: string;
  monogram: string;
  comingSoon: boolean;
}

export interface SavedView {
  id: string;
  name: string;
  count: number;
}

export interface Workspace {
  id: string;
  name: string;
  monogram: string;
  plan: string;
  trialDaysLeft: number;
  seats: number;
  ticketsThisPeriod: number;
  projectedTickets: number;
}

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  monogram: string;
  timeZone: string;
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
