"use client";

import { useEffect, useRef, useState } from "react";

import { Article } from "@/components/widget/article";
import { Compose } from "@/components/widget/compose";
import { Footer } from "@/components/widget/footer";
import { Header } from "@/components/widget/header";
import { Home } from "@/components/widget/home";
import { Results } from "@/components/widget/results";
import { Sent } from "@/components/widget/sent";
import type { SubmitWidgetTicketResult } from "@/app/(widget)/widget/frame/actions";

export type PanelProps = {
  workspaceName: string;
  monogram: string;
  settings: Record<string, unknown>;
  articleCount: number;
  /**
   * The credential this panel opened with -- absent only in a test that
   * renders `Panel` on its own, where nothing reaches the network. The
   * frame page (`app/(widget)/widget/frame/page.tsx`) always supplies it.
   */
  widgetKey?: string;
  /**
   * The ticket-submission server action, already bound to `widgetKey` by
   * the frame page. A prop rather than an import here: a Client Component
   * may take a Server Action as a prop, but importing the module that
   * defines one would pull `lib/api/widget.ts` -- `server-only` -- into
   * this file's module graph. See compose.tsx for the rest of that
   * reasoning.
   */
  onSubmit?: (formData: FormData) => Promise<SubmitWidgetTicketResult>;
};

// Home and Results both offer search; Compose is reachable from either
// (and, when the knowledge base is empty, is where the panel opens
// directly), Article is reachable from Results, and Sent is terminal.
type View =
  | { name: "home" }
  | { name: "results"; query: string }
  | { name: "article"; path: string }
  | { name: "compose" }
  | { name: "sent" };

/**
 * The widget panel: everything a visitor sees inside the loader's iframe
 * (spec D5). Composes the seven states the design draws in
 * `docs/superpowers/specs/2026-09-10-support-widget-design.md` §7 behind
 * one piece of view state.
 *
 * Two rules carry meaning, not taste, and are enforced by which button
 * variant each screen is given, not by anything here: "Send a message" is
 * secondary on Home and primary on Results and Article -- the visitor has
 * tried to self-serve, so escalation becomes the right action -- and dark
 * mode follows `prefers-color-scheme` only, via Tailwind's `dark:`
 * variant, because the frame is cross-origin from the host page and has no
 * other signal for it.
 */
export function Panel({
  workspaceName,
  monogram,
  articleCount,
  widgetKey,
  onSubmit,
}: PanelProps) {
  // The day-one state for every new customer (spec D7). Deciding it from
  // articleCount rather than from a failed search is what stops a new
  // workspace ever rendering a search box over nothing.
  const empty = articleCount === 0;
  const [view, setView] = useState<View>(() =>
    empty ? { name: "compose" } : { name: "home" },
  );

  const containerRef = useRef<HTMLDivElement>(null);

  // Tell the loader to hide the frame. The loader (public/widget.js) only
  // ever hides on receipt of this exact string from this exact origin --
  // `event.origin` on the receiving end is the sender's origin regardless
  // of the target origin passed here, so "*" carries nothing sensitive.
  function close() {
    window.parent?.postMessage("relaydesk:close", "*");
  }

  // Focus trap + Esc-to-close, while the panel is mounted at all -- it is
  // the whole content of its own document, so "while the panel is open" is
  // simply "for the life of this component". Returning focus to the
  // launcher itself is the loader's job: it owns the launcher element, and
  // a cross-document iframe cannot move focus in its parent on its own.
  useEffect(() => {
    const node = containerRef.current;
    node?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        close();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const focusable = node.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  // The one place "go home" is decided, for every transition that can ask
  // for it -- Header's back chevron, Compose's own back button, and Sent's
  // "Back to home". `empty` gates the panel's *initial* view (above), but a
  // transition is a second, independent way to reach `home`, and each of
  // these three was reachable even when the knowledge base is empty:
  // Compose is the initial screen there, so both its back button and, after
  // a real submission, Sent are always live. Routing every one of them
  // through this rather than `{ name: "home" }` directly is what stops a
  // visitor on a zero-article workspace from ever reaching the search field
  // Home renders -- the exact failure mode spec D7 exists to prevent.
  const goHome = () => setView(empty ? { name: "compose" } : { name: "home" });

  // Results and Article are the two screens reached by going further in;
  // Home is where "further in" starts, so only those two get a way back to
  // it. Compose carries its own `showBack` (it is reachable from Home
  // directly, from either of those two, or is the whole panel on an empty
  // knowledge base), and Sent is terminal with its own way home.
  const onBack = view.name === "results" || view.name === "article" ? goHome : undefined;

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-label={`${workspaceName} support`}
      tabIndex={-1}
      className="motion-reduce:transition-none flex h-screen flex-col bg-white text-ink-900 dark:bg-ink-900 dark:text-ink-50"
    >
      <Header name={workspaceName} monogram={monogram} onBack={onBack} onClose={close} />
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {view.name === "home" && (
          <Home
            onSearch={(query) => setView({ name: "results", query })}
            onCompose={() => setView({ name: "compose" })}
          />
        )}
        {view.name === "results" && (
          <Results
            key={view.query}
            widgetKey={widgetKey}
            query={view.query}
            onOpen={(path) => setView({ name: "article", path })}
            onCompose={() => setView({ name: "compose" })}
          />
        )}
        {view.name === "article" && (
          <Article
            key={view.path}
            widgetKey={widgetKey}
            path={view.path}
            onCompose={() => setView({ name: "compose" })}
          />
        )}
        {view.name === "compose" && (
          <Compose
            showBack={!empty}
            onBack={goHome}
            onSent={() => setView({ name: "sent" })}
            onSubmit={onSubmit}
          />
        )}
        {view.name === "sent" && <Sent onHome={goHome} />}
      </div>
      <Footer />
    </div>
  );
}
