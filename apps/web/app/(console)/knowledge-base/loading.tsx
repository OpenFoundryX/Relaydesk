import { Skeleton, SkeletonScreen } from "@/components/ui/skeleton";

/**
 * The right-hand pane only. The tree, tabs and header live in this segment's
 * layout, which renders above this boundary and stays on screen -- so this
 * stands in for the article being opened, not for the whole page.
 */
export default function KnowledgeBaseLoading() {
  return (
    <SkeletonScreen label="Loading article" className="space-y-4">
      <Skeleton className="h-7 w-2/3" />
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <div className="space-y-2 pt-2">
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-5/6" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-3/4" />
      </div>
    </SkeletonScreen>
  );
}
