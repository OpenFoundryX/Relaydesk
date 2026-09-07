import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

/**
 * The heaviest route in the console: it awaits the conversation, then eight
 * more calls for messages, draft, activity, labels, team, siblings and the
 * workspace. Two round trips before anything can render, which is exactly
 * the wait this stands in for.
 */
export default function ConversationLoading() {
  return (
    <SkeletonScreen label="Loading conversation" className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-3 border-b border-ink-200 bg-white px-4">
        <Skeleton className="h-4 w-56" />
        <div className="flex-1" />
        <Skeleton className="h-6 w-20 rounded-md" />
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-5 overflow-hidden p-5">
            {["h-16", "h-24", "h-12"].map((height, index) => (
              <div
                key={height}
                className={index % 2 ? "flex justify-end" : "flex justify-start"}
              >
                <div className="w-[min(32rem,80%)] space-y-2">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className={`w-full rounded-lg ${height}`} />
                </div>
              </div>
            ))}
          </div>
          <div className="shrink-0 border-t border-ink-200 p-4">
            <Skeleton className="h-20 w-full rounded-lg" />
          </div>
        </div>

        <div className="hidden w-72 shrink-0 space-y-4 border-l border-ink-200 p-4 lg:block">
          <Skeleton className="h-3.5 w-24" />
          <Skeleton className="h-8 w-full rounded-md" />
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="h-8 w-full rounded-md" />
          <Skeleton className="h-3.5 w-16" />
          <Skeleton className="h-24 w-full rounded-md" />
        </div>
      </div>
    </SkeletonScreen>
  );
}
