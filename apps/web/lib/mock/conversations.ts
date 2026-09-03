import type {
  ActivityEvent,
  Conversation,
  ConversationStatus,
  Label,
  Message,
  Priority,
  StatusCount,
} from "./types";

/**
 * In-memory inbox store. Mutations below are what the server actions call;
 * swapping the bodies for API requests is the intended path to a backend.
 * State lives for the lifetime of the server process.
 */

export const labels: Label[] = [
  { id: "billing", name: "Billing", color: "amber" },
  { id: "bug", name: "Bug", color: "rose" },
  { id: "onboarding", name: "Onboarding", color: "citron" },
  { id: "feature-request", name: "Feature request", color: "sky" },
];

export const savedViews = [
  { id: "urgent", name: "Urgent & unassigned", count: 2 },
  { id: "mine", name: "Assigned to me", count: 4 },
  { id: "waiting", name: "Waiting on customer", count: 3 },
];

const conversations: Conversation[] = [
  {
    id: "c_9d6d5cd1",
    number: 299,
    subject: "Checkout fails with a 402 on annual plans",
    preview:
      "Hey — every time I try to switch our workspace to annual billing the payment step returns a 402. Card works fine elsewhere.",
    customerName: "Priya Raman",
    customerEmail: "priya@northwind.io",
    channel: "email",
    status: "open",
    priority: "urgent",
    age: "12m",
    date: "Sep 4",
    assignee: null,
    labelIds: ["billing", "bug"],
    hasDraft: true,
    unread: true,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_41ba7f02",
    number: 298,
    subject: "How do I invite a read-only teammate?",
    preview:
      "We want our finance lead to see invoices but not touch tickets. Is there a viewer role?",
    customerName: "Marcus Webb",
    customerEmail: "marcus@lattice-labs.com",
    channel: "portal",
    status: "open",
    priority: "medium",
    age: "48m",
    date: "Sep 4",
    assignee: "Nilesh Pant",
    labelIds: ["onboarding"],
    hasDraft: true,
    unread: true,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_7c02e155",
    number: 297,
    subject: "Discord bot stopped creating tickets last night",
    preview:
      "Our forum channel was quiet in Relaydesk since about 23:00 UTC but there are definitely new threads.",
    customerName: "Ida Okonkwo",
    customerEmail: "ida@parsecgg.com",
    channel: "discord",
    status: "open",
    priority: "high",
    age: "3h",
    date: "Sep 3",
    assignee: "Sara Duval",
    labelIds: ["bug"],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_2f8b91de",
    number: 296,
    subject: "Request: bulk export of resolved tickets",
    preview:
      "Would love a CSV export so we can run our own reporting on resolution times.",
    customerName: "Tomas Lind",
    customerEmail: "tomas@heliossoft.se",
    channel: "email",
    status: "open",
    priority: "low",
    age: "5h",
    date: "Sep 3",
    assignee: null,
    labelIds: ["feature-request"],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_b3417a90",
    number: 295,
    subject: "Refund for duplicate October charge",
    preview: "We were billed twice on 3 Oct. Invoice numbers are INV-2291 and INV-2292.",
    customerName: "Grace Whitfield",
    customerEmail: "grace@bellcurve.app",
    channel: "email",
    status: "pending",
    priority: "high",
    age: "1d",
    date: "Sep 3",
    assignee: "Nilesh Pant",
    labelIds: ["billing"],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_5ee1c874",
    number: 294,
    subject: "SAML metadata URL is rejected",
    preview: "Okta gives us a metadata URL, but the field seems to want raw XML.",
    customerName: "Devon Ruiz",
    customerEmail: "devon@quorumhq.com",
    channel: "api",
    status: "pending",
    priority: "medium",
    age: "1d",
    date: "Sep 2",
    assignee: "Sara Duval",
    labelIds: [],
    hasDraft: true,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_18ca6b33",
    number: 293,
    subject: "Thanks — webhook signing sorted",
    preview: "Verified the signature header against our secret and it lines up. Appreciate it.",
    customerName: "Aiko Tanaka",
    customerEmail: "aiko@driftline.jp",
    channel: "email",
    status: "resolved",
    priority: "low",
    age: "2d",
    date: "Sep 2",
    assignee: "Nilesh Pant",
    labelIds: [],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_a70f2d61",
    number: 292,
    subject: "Password reset email never arrives",
    preview: "Checked spam. Nothing. Our domain is on Google Workspace.",
    customerName: "Owen Pryce",
    customerEmail: "owen@caldera.dev",
    channel: "portal",
    status: "resolved",
    priority: "medium",
    age: "3d",
    date: "Sep 1",
    assignee: "Sara Duval",
    labelIds: ["bug"],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
  {
    id: "c_cc39e40b",
    number: 291,
    subject: "Waiting on legal review of the DPA",
    preview: "Our counsel has the agreement. Parking this until they come back to us.",
    customerName: "Helena Marsh",
    customerEmail: "helena@ridgeway.co",
    channel: "email",
    status: "on_hold",
    priority: "low",
    age: "6d",
    date: "Aug 29",
    assignee: "Nilesh Pant",
    labelIds: [],
    hasDraft: false,
    unread: false,
    summary: null,
    summaryState: "none",
  },
];

const messages = new Map<string, Message[]>();
const activity: ActivityEvent[] = conversations.map((conversation) => ({
  id: `${conversation.id}_created`,
  conversationId: conversation.id,
  actor: conversation.customerName,
  kind: "created",
  verb: "opened this ticket via",
  value: conversation.channel,
  at: `${conversation.date}, 9:14 AM`,
}));

export const statuses: ConversationStatus[] = [
  "open",
  "pending",
  "on_hold",
  "resolved",
  "ignored",
  "trash",
];

export const statusLabel: Record<ConversationStatus, string> = {
  open: "Open",
  pending: "Pending",
  on_hold: "On hold",
  resolved: "Resolved",
  ignored: "Ignored",
  trash: "Trash",
};

export const priorities: Priority[] = ["low", "medium", "high", "urgent"];

export const priorityLabel: Record<Priority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

/* ------------------------------------------------------------------ reads */

export async function getConversations(
  status?: ConversationStatus,
): Promise<Conversation[]> {
  if (!status) return conversations;
  return conversations.filter((conversation) => conversation.status === status);
}

export async function getStatusCounts(): Promise<StatusCount[]> {
  return statuses.map((status) => ({
    status,
    count: conversations.filter((conversation) => conversation.status === status).length,
  }));
}

export async function getDraftCount(): Promise<number> {
  return conversations.filter((conversation) => conversation.hasDraft).length;
}

export async function getConversation(id: string): Promise<Conversation | null> {
  return conversations.find((conversation) => conversation.id === id) ?? null;
}

export async function getLabels(): Promise<Label[]> {
  return labels;
}

/**
 * Threads are seeded from the conversation itself the first time they are
 * read, then kept so replies persist across navigations.
 */
export async function getMessages(id: string): Promise<Message[]> {
  const existing = messages.get(id);
  if (existing) return existing;

  const conversation = conversations.find((entry) => entry.id === id);
  if (!conversation) return [];

  const thread: Message[] = [
    {
      id: `${id}_m1`,
      author: conversation.customerName,
      to: "support@chronon.co",
      role: "customer",
      body: conversation.preview,
      sentAt: conversation.age,
    },
  ];

  if (conversation.status !== "open") {
    thread.push({
      id: `${id}_m2`,
      author: conversation.assignee ?? "Relaydesk",
      to: conversation.customerEmail,
      role: "agent",
      body:
        "Thanks for flagging this — I have reproduced it on our side and passed the details to engineering. I will update you as soon as I hear back.",
      sentAt: conversation.age,
    });
  }

  messages.set(id, thread);
  return thread;
}

/** The AI-drafted reply for a ticket, if it has one. Lives outside the thread. */
export async function getDraft(id: string): Promise<string | null> {
  const conversation = conversations.find((entry) => entry.id === id);
  if (!conversation?.hasDraft) return null;
  const first = conversation.customerName.split(" ")[0];
  return `Hi ${first},\n\nSorry to hear you're running into trouble. Could you share a bit more detail so I can look into this?\n\n- Which plan and workspace this affects\n- Roughly when it started\n- Any error message or screenshot of what you're seeing\n\nOnce I have those, I'll be able to help sort this out.\n\nThanks,\nRelaydesk Support`;
}

export async function getActivity(id: string): Promise<ActivityEvent[]> {
  return activity.filter((event) => event.conversationId === id).slice().reverse();
}

/* -------------------------------------------------------------- mutations */

const actor = "Nilesh Pant";

function now() {
  return `Today, ${new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
}

function record(event: Omit<ActivityEvent, "id" | "at" | "actor">) {
  activity.push({
    ...event,
    id: `evt_${activity.length + 1}`,
    actor,
    at: now(),
  });
}

function find(id: string) {
  const conversation = conversations.find((entry) => entry.id === id);
  if (!conversation) throw new Error(`Unknown conversation ${id}`);
  return conversation;
}

export async function setStatus(id: string, status: ConversationStatus) {
  const conversation = find(id);
  if (conversation.status === status) return;
  conversation.status = status;
  conversation.unread = false;
  record({ conversationId: id, kind: "status", verb: "marked this as", value: statusLabel[status], status });
}

export async function setPriority(id: string, priority: Priority) {
  const conversation = find(id);
  if (conversation.priority === priority) return;
  conversation.priority = priority;
  record({ conversationId: id, kind: "priority", verb: "set priority to", value: priorityLabel[priority] });
}

export async function setAssignee(id: string, assignee: string | null) {
  const conversation = find(id);
  if (conversation.assignee === assignee) return;
  conversation.assignee = assignee;
  record({
    conversationId: id,
    kind: "assignee",
    verb: assignee ? "assigned this to" : "unassigned this from",
    value: assignee ?? conversation.assignee ?? "everyone",
  });
}

export async function toggleLabel(id: string, labelId: string) {
  const conversation = find(id);
  const label = labels.find((entry) => entry.id === labelId);
  if (!label) return;
  const has = conversation.labelIds.includes(labelId);
  conversation.labelIds = has
    ? conversation.labelIds.filter((entry) => entry !== labelId)
    : [...conversation.labelIds, labelId];
  record({ conversationId: id, kind: "label", verb: has ? "removed label" : "added label", value: label.name });
}

export async function createLabel(name: string): Promise<Label> {
  const trimmed = name.trim();
  const existing = labels.find((label) => label.name.toLowerCase() === trimmed.toLowerCase());
  if (existing) return existing;
  const colors: Label["color"][] = ["citron", "slate", "amber", "rose", "sky"];
  const label: Label = {
    id: trimmed.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `label-${labels.length + 1}`,
    name: trimmed,
    color: colors[labels.length % colors.length],
  };
  labels.push(label);
  return label;
}

export async function addReply(id: string, body: string) {
  const conversation = find(id);
  const thread = await getMessages(id);
  thread.push({
    id: `${id}_m${thread.length + 1}`,
    author: actor,
    to: conversation.customerEmail,
    role: "agent",
    body,
    sentAt: "now",
  });
  conversation.hasDraft = false;
  conversation.unread = false;
  record({ conversationId: id, kind: "reply", verb: "replied to", value: conversation.customerName });
}

export async function discardDraft(id: string) {
  find(id).hasDraft = false;
}

export async function generateSummary(id: string) {
  const conversation = find(id);
  const thread = await getMessages(id);
  const replies = thread.filter((message) => message.role !== "customer").length;
  conversation.summary =
    `${conversation.customerName} reports: ${conversation.preview} ` +
    (replies > 0
      ? `The team has replied ${replies === 1 ? "once" : `${replies} times`} and the ticket is ${statusLabel[conversation.status].toLowerCase()}.`
      : "No reply has been sent yet.");
  conversation.summaryState = "ready";
}
