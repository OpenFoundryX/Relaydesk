import { Inbox } from "lucide-react";

import { EmptyState } from "@/components/console/empty-state";
import { InboxList } from "@/components/inbox/inbox-list";
import { ListToolbar } from "@/components/inbox/list-toolbar";
import { StatusIcon, statusMeta } from "@/components/inbox/status-meta";
import { getConversations, getLabels, savedViews, statuses } from "@/lib/mock/conversations";
import { getTeam } from "@/lib/mock/settings";
import type { Conversation, ConversationStatus } from "@/lib/mock/types";
import { getCurrentUser } from "@/lib/api/workspace";

export const metadata = { title: "Inbox" };

const virtualTitles: Record<string, string> = {
  all: "All tickets",
  drafts: "Drafts",
};

function isStatus(value: string): value is ConversationStatus {
  return (statuses as string[]).includes(value);
}

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; view?: string; label?: string }>;
}) {
  const { status = "open", view, label } = await searchParams;
  const [all, labels, team, currentUser] = await Promise.all([
    getConversations(),
    getLabels(),
    getTeam(),
    getCurrentUser(),
  ]);

  /** Saved views are fixed filters for now; they become user-defined later. */
  const viewFilters: Record<string, (conversation: Conversation) => boolean> = {
    urgent: (c) => c.priority === "urgent" && c.assignee === null && c.status === "open",
    mine: (c) => c.assignee === currentUser.name && c.status !== "trash",
    waiting: (c) => c.status === "pending",
  };

  let conversations: Conversation[];
  let title: string;
  let icon: React.ReactNode = null;

  if (view && viewFilters[view]) {
    conversations = all.filter(viewFilters[view]);
    title = savedViews.find((entry) => entry.id === view)?.name ?? "View";
  } else if (label) {
    conversations = all.filter((c) => c.labelIds.includes(label) && c.status !== "trash");
    title = labels.find((entry) => entry.id === label)?.name ?? "Label";
  } else if (isStatus(status)) {
    conversations = all.filter((c) => c.status === status);
    title = statusMeta[status].label;
    icon = <StatusIcon status={status} className="size-4" />;
  } else if (status === "drafts") {
    conversations = all.filter((c) => c.hasDraft && c.status !== "trash");
    title = virtualTitles.drafts;
  } else {
    conversations = all.filter((c) => c.status !== "trash");
    title = virtualTitles.all;
  }

  return (
    <div className="flex h-full flex-col">
      <ListToolbar title={title} count={conversations.length} icon={icon} />

      {conversations.length > 0 ? (
        <InboxList conversations={conversations} labels={labels} team={team} />
      ) : (
        <div className="p-6">
          <EmptyState
            icon={Inbox}
            title={`Nothing in ${title.toLowerCase()}`}
            description="When a ticket lands here it will show up in this list, newest first."
          />
        </div>
      )}
    </div>
  );
}
