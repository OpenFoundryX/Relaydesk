import { Paperclip, TriangleAlert } from "lucide-react";

import { MessageBody } from "@/components/inbox/message-body";
import type { Conversation, Message } from "@/lib/types";
import { cn, formatFileSize } from "@/lib/utils";

function Monogram({ name, className }: { name: string; className?: string }) {
  return (
    <span
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold uppercase text-white",
        className,
      )}
    >
      {name
        .split(" ")
        .map((part) => part[0])
        .join("")
        .slice(0, 2)}
    </span>
  );
}

/**
 * The message thread. Customer messages sit on the left, replies from the
 * team on the right, in the shape of a chat so the back-and-forth reads at a
 * glance. Plain markup: replies land here via the composer's server action.
 */
export function Thread({
  conversation,
  messages,
}: {
  conversation: Conversation;
  messages: Message[];
}) {
  return (
    <div className="flex-1 space-y-6 px-6 py-5">
      <p className="text-center text-[12px] text-ink-500">{conversation.date} at 9:14 AM</p>

      {messages.map((message) => {
        if (message.role === "system") {
          return (
            <p key={message.id} className="text-center text-[12px] text-ink-500">
              {message.body}
            </p>
          );
        }

        const mine = message.role !== "customer";
        return (
          <div key={message.id} className={cn("flex items-end gap-3", mine && "flex-row-reverse")}>
            <Monogram name={message.author} className={mine ? "bg-ink-900" : "bg-ink-700"} />
            <div className={cn("max-w-[70%] min-w-0", mine ? "items-end" : "items-start")}>
              <p className={cn("mb-1 text-[11px] text-ink-500", mine && "text-right")}>
                {message.author}
              </p>
              <div
                className={cn(
                  "rounded-lg px-4 py-3 text-[13px] leading-relaxed text-ink-900",
                  mine ? "bg-accent-50 ring-1 ring-accent-200" : "bg-ink-50 ring-1 ring-ink-200",
                )}
              >
                <p className="mb-1.5 text-[11px] text-ink-500">
                  <span className="font-medium text-ink-700">To</span> {message.to}
                </p>
                <MessageBody body={message.body} />

                {message.attachments.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {message.attachments.map((attachment) => (
                      <a
                        key={attachment.id}
                        href={`/api/attachments/${attachment.id}`}
                        className="flex items-center gap-1.5 rounded-md border border-ink-200 bg-white px-2 py-1 text-[12px] text-ink-700 transition-colors hover:border-ink-300 hover:text-ink-900"
                      >
                        <Paperclip className="size-3.5 shrink-0 text-ink-400" />
                        <span className="truncate">{attachment.filename}</span>
                        <span className="shrink-0 text-ink-400">
                          {formatFileSize(attachment.sizeBytes)}
                        </span>
                      </a>
                    ))}
                  </div>
                )}

                {message.deliveryState === "failed" && (
                  <p className="mt-2 flex items-center gap-1 text-[11px] font-medium text-danger-600">
                    <TriangleAlert className="size-3.5" />
                    Not delivered
                  </p>
                )}

                <p className="mt-2 text-[11px] text-ink-400">{message.sentAt}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
