import { CircleCheck } from "lucide-react";

import { WidgetButton } from "@/components/widget/button";

/**
 * The terminal screen. No reference number -- `TicketSubmittedOut` says
 * nothing but `received`, deliberately, because the submitter is
 * anonymous and must not be handed a handle to the inbox.
 */
export function Sent({ onHome }: { onHome: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <CircleCheck className="size-8 text-accent-600 dark:text-accent-400" aria-hidden />
      <h1 className="text-[15px] font-semibold tracking-tight text-ink-900 dark:text-white">
        Message sent
      </h1>
      <p className="text-[13px] leading-relaxed text-ink-500 dark:text-ink-400">
        We&apos;ll reply by email as soon as we can.
      </p>
      <WidgetButton type="button" variant="secondary" onClick={onHome} className="w-auto px-4">
        Back to home
      </WidgetButton>
    </div>
  );
}
