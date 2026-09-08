import { notFound } from "next/navigation";

import { ConversationHeader } from "@/components/inbox/conversation-header";
import { DetailsSidebar } from "@/components/inbox/details-sidebar";
import { ReplyComposer } from "@/components/inbox/reply-composer";
import { Thread } from "@/components/inbox/thread";
import {
  getActivity,
  getConversation,
  getConversations,
  getDraft,
  getMessages,
} from "@/lib/api/conversations";
import { getLabels } from "@/lib/api/labels";
import { getSnippets } from "@/lib/api/snippets";
import { getTeam } from "@/lib/api/team";
import { getCurrentUser, getWorkspace } from "@/lib/api/workspace";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const conversation = await getConversation(id);
  if (!conversation) notFound();

  const [messages, draft, activity, labels, team, siblings, workspace, user, snippets] =
    await Promise.all([
      getMessages(id),
      getDraft(id),
      getActivity(id),
      getLabels(),
      getTeam(),
      getConversations({ status: conversation.status }),
      getWorkspace(),
      getCurrentUser(),
      getSnippets(),
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
            snippets={snippets}
            // What `{{...}}` placeholders in a snippet resolve to. `agentName`
            // is the signed-in user rather than the conversation's assignee:
            // a snippet signs the reply being written, and whoever is writing
            // it is not always who it is assigned to.
            snippetContext={{
              customerName: conversation.customerName,
              customerEmail: conversation.customerEmail,
              ticketNumber: conversation.number,
              ticketSubject: conversation.subject,
              agentName: user.name,
              workspaceName: workspace.name,
            }}
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
