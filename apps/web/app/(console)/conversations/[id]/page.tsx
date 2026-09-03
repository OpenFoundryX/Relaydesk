import { notFound } from "next/navigation";

import { ConversationHeader } from "@/components/inbox/conversation-header";
import { DetailsSidebar } from "@/components/inbox/details-sidebar";
import { ReplyComposer } from "@/components/inbox/reply-composer";
import { Thread } from "@/components/inbox/thread";
import { getTeam } from "@/lib/api/team";
import { getWorkspace } from "@/lib/api/workspace";
import {
  getActivity,
  getConversation,
  getConversations,
  getDraft,
  getLabels,
  getMessages,
} from "@/lib/mock/conversations";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const conversation = await getConversation(id);
  if (!conversation) notFound();

  const [messages, draft, activity, labels, team, siblings, workspace] = await Promise.all([
    getMessages(id),
    getDraft(id),
    getActivity(id),
    getLabels(),
    getTeam(),
    getConversations(conversation.status),
    getWorkspace(),
  ]);

  const index = siblings.findIndex((entry) => entry.id === id);
  const prevId = index > 0 ? siblings[index - 1].id : null;
  const nextId = index >= 0 && index < siblings.length - 1 ? siblings[index + 1].id : null;

  return (
    <div className="flex h-full flex-col">
      <ConversationHeader conversation={conversation} team={team} prevId={prevId} nextId={nextId} />

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <Thread conversation={conversation} messages={messages} />
          </div>
          <ReplyComposer
            conversationId={conversation.id}
            customerEmail={conversation.customerEmail}
            from="support@chronon.co"
            draft={draft}
          />
        </div>

        <DetailsSidebar
          conversation={conversation}
          activity={activity}
          labels={labels}
          team={team}
          workspaceName={workspace.name}
        />
      </div>
    </div>
  );
}
