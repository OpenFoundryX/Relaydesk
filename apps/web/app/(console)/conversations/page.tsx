import { Inbox } from "lucide-react";
import { redirect } from "next/navigation";

import { EmptyState } from "@/components/console/empty-state";
import { InboxList } from "@/components/inbox/inbox-list";
import { ListToolbar } from "@/components/inbox/list-toolbar";
import { StatusIcon, statusMeta } from "@/components/inbox/status-meta";
import { ApiError } from "@/lib/api/client";
import { getConversations } from "@/lib/api/conversations";
import { getLabels } from "@/lib/api/labels";
import { getTeam } from "@/lib/api/team";
import { getViews } from "@/lib/api/views";
import { statuses } from "@/lib/types";
import type { Conversation, ConversationStatus } from "@/lib/types";

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

  const [labels, team, views] = await Promise.all([getLabels(), getTeam(), getViews()]);

  let conversations: Conversation[];
  let title: string;
  let icon: React.ReactNode = null;

  if (view) {
    // A bookmarked or stale view id (its row was deleted) 404s from the
    // API. Bounce to the inbox rather than letting the console error
    // boundary catch it: that boundary's "Try again" would just re-issue
    // the same failing request. Any other failure (422, 500, a revoked
    // session) still propagates — only a missing view redirects.
    let viewNotFound = false;
    try {
      conversations = await getConversations({ viewId: view });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        conversations = [];
        viewNotFound = true;
      } else {
        throw error;
      }
    }
    if (viewNotFound) {
      redirect("/conversations?status=open");
    }
    title = views.find((entry) => entry.id === view)?.name ?? "View";
  } else if (label) {
    conversations = await getConversations({ labelId: label });
    title = labels.find((entry) => entry.id === label)?.name ?? "Label";
  } else if (isStatus(status)) {
    conversations = await getConversations({ status });
    title = statusMeta[status].label;
    icon = <StatusIcon status={status} className="size-4" />;
  } else if (status === "drafts") {
    conversations = await getConversations({ status: "drafts" });
    title = virtualTitles.drafts;
  } else {
    conversations = await getConversations({ status: "all" });
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
