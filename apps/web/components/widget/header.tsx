import { ArrowLeft, X } from "lucide-react";

/**
 * The bar every screen shares: who this is, a way back to Home from
 * anywhere further in, and a way to close the panel.
 */
export function Header({
  name,
  monogram,
  onBack,
  onClose,
}: {
  name: string;
  monogram: string;
  /** Present only on Results and Article -- see panel.tsx. */
  onBack?: () => void;
  onClose: () => void;
}) {
  return (
    <header className="flex shrink-0 items-center gap-2 border-b border-ink-200 bg-ink-950 px-4 py-3 dark:border-ink-800">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to home"
          className="flex size-7 shrink-0 items-center justify-center rounded-md text-ink-300 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          <ArrowLeft className="size-4" aria-hidden />
        </button>
      ) : (
        <span
          aria-hidden
          className="flex size-7 shrink-0 items-center justify-center rounded-md bg-white text-[11px] font-semibold text-ink-900"
        >
          {monogram}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate text-[14px] font-semibold tracking-tight text-white">
        {name}
      </span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="flex size-7 shrink-0 items-center justify-center rounded-md text-ink-300 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
      >
        <X className="size-4" aria-hidden />
      </button>
    </header>
  );
}
