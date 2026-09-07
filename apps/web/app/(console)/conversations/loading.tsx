import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

/**
 * Mirrors the real list: an `h-12` toolbar over `h-11` rows with the same
 * borders and padding, so the rows do not move when the data lands.
 */
export default function ConversationsLoading() {
  return (
    <SkeletonScreen label="Loading conversations" className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-ink-200 bg-white px-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-8 rounded-full" />
      </div>

      <ul>
        {Array.from({ length: 12 }, (_, index) => (
          <li
            key={index}
            className="flex h-11 items-center gap-3 border-b border-ink-100 pl-3 pr-4 last:border-b-0"
          >
            <Skeleton className="size-4 shrink-0 rounded-sm" />
            <Skeleton className="h-3.5 w-32 shrink-0" />
            <Skeleton className="h-3.5 min-w-0 flex-1" />
            <Skeleton className="h-3.5 w-12 shrink-0" />
          </li>
        ))}
      </ul>
    </SkeletonScreen>
  );
}
