"use client";

import { useEffect, useRef, useState } from "react";

import { Article } from "@/components/widget/article";
import { Ask } from "@/components/widget/ask";
import { Compose } from "@/components/widget/compose";
import { Footer } from "@/components/widget/footer";
import { Header } from "@/components/widget/header";
import { Home } from "@/components/widget/home";
import { Results } from "@/components/widget/results";
import { Sent } from "@/components/widget/sent";
import type { SubmitWidgetTicketResult } from "@/app/(widget)/widget/frame/actions";
import type { WidgetSessionEventKind } from "@/lib/api/widget";

/**
 * The per-key branding blob (spec D10, un-deferred). Every field is
 * optional and validated server-side (`services/widget_keys.py`); an
 * absent field means today's unbranded behaviour, unchanged. No `iconUrl`
 * yet -- the API refuses it as an unknown setting until there is
 * somewhere to serve an icon from; see this slice's report.
 */
type WidgetBrandingSettings = {
  name?: string;
  greeting?: string;
  accentColour?: string;
  position?: "left" | "right";
};

export type PanelProps = {
  workspaceName: string;
  monogram: string;
  settings: Record<string, unknown>;
  articleCount: number;
  /**
   * The host page is on a laptop-sized screen, so the panel is drawn
   * larger and its contents scale to match. Absent on a phone, where the
   * panel is already a full-screen takeover at the reader's own text size.
   */
  wide?: boolean;
  /**
   * Whether this workspace can actually answer a question -- AI switched on
   * AND a key installed. Absent or false means the panel opens exactly as
   * it did before AI existed: a visitor is never shown a question box that
   * could only bounce them back to search.
   */
  aiEnabled?: boolean;
  /**
   * The credential this panel opened with -- absent only in a test that
   * renders `Panel` on its own, where nothing reaches the network. The
   * frame page (`app/(widget)/widget/frame/page.tsx`) always supplies it.
   */
  widgetKey?: string;
  /**
   * Prefill only (spec §6), forwarded from the loader's `data-email` /
   * `data-name` attributes via the frame page's query string. Absent
   * whenever the customer didn't set the attribute -- an absent value must
   * leave Compose's field empty exactly as it was before this existed, so
   * both stay optional all the way down.
   */
  email?: string;
  name?: string;
  /**
   * The ticket-submission server action, already bound to `widgetKey` by
   * the frame page. A prop rather than an import here: a Client Component
   * may take a Server Action as a prop, but importing the module that
   * defines one would pull `lib/api/widget.ts` -- `server-only` -- into
   * this file's module graph. See compose.tsx for the rest of that
   * reasoning. Forwarded to both Compose and Ask -- the inline escalation
   * offer in Ask files a ticket the same way Compose's form does.
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
  | { name: "ask" }
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
  settings,
  articleCount,
  aiEnabled,
  wide,
  widgetKey,
  email,
  name,
  onSubmit,
}: PanelProps) {
  // Cast rather than re-validated here: the value only ever reaches this
  // component already cleaned by `services/widget_keys.py`'s
  // `_clean_settings`, which is the one place these fields are constrained.
  const branding = settings as WidgetBrandingSettings;
  // The configured display name replaces the workspace name in the header
  // (spec D10, un-deferred) -- absent falls back to exactly what rendered
  // before this existed.
  const displayName =
    branding.name && branding.name.trim() !== "" ? branding.name : workspaceName;

  // The day-one state for every new customer (spec D7). Deciding it from
  // articleCount rather than from a failed search is what stops a new
  // workspace ever rendering a search box over nothing.
  const empty = articleCount === 0;
  // Three day-one states, in priority order. An empty knowledge base still
  // opens on `compose` and never mounts a search field (spec D7, slice 8)
  // -- that rule is untouched, and it outranks AI because a model with
  // nothing to ground an answer in cannot answer either. Otherwise a
  // workspace that has configured AI opens on the conversation, and one
  // that has not opens on search exactly as before.
  const [view, setView] = useState<View>(() => {
    if (empty) return { name: "compose" };
    return aiEnabled ? { name: "ask" } : { name: "home" };
  });

  // Set only by Ask's escalate button, from the turns already on screen
  // (task 11, spec D8): the agent reading the resulting ticket must see
  // what the visitor was already told, not just what they typed into
  // Compose. Reset by every other route into Compose, so a transcript
  // from an earlier, abandoned conversation can never ride along on a
  // ticket that has nothing to do with it.
  const [transcript, setTranscript] = useState("");
  const compose = (nextTranscript = "") => {
    setTranscript(nextTranscript);
    setView({ name: "compose" });
  };

  const containerRef = useRef<HTMLDivElement>(null);

  // Minted once, for the life of the panel -- not persisted, not sent
  // anywhere but the counter below. A lazy `useState` initialiser rather
  // than a ref: it runs exactly once, on first render, without ever
  // reading a ref's value during render (which `react-hooks/refs` forbids
  // here). `undefined` when there is no `widgetKey` at all -- the test that
  // renders a bare `Panel` reaches the network for nothing either way.
  const [sessionId] = useState<string | undefined>(() =>
    widgetKey ? crypto.randomUUID() : undefined,
  );

  // Each kind fires at most once per session (spec §1, §4): the deflection
  // baseline counts sessions, not events, so a search box firing on every
  // keystroke or an article re-opened twice must not inflate it.
  const firedRef = useRef<Set<WidgetSessionEventKind>>(new Set());

  // The counter side of the deflection baseline (task 11). Posted to the
  // frame's own `/widget/session` route -- see that file for why a Client
  // Component cannot call the API directly -- and never awaited: a support
  // request must never be able to fail, slow down, or even notice that this
  // call happened. Failures are swallowed here a second time even though
  // the route already swallows its own, because `fetch` itself can reject
  // (offline, blocked by an extension) before the route ever sees it.
  function recordEvent(kind: WidgetSessionEventKind) {
    if (!widgetKey || !sessionId) return;
    if (firedRef.current.has(kind)) return;
    firedRef.current.add(kind);
    fetch("/widget/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: widgetKey, sessionId, kind }),
    }).catch(() => {});
  }

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
      aria-label={`${displayName} support`}
      tabIndex={-1}
      // `zoom` rather than a second set of sizes on every element: the
      // panel is a self-contained document at a width we choose, so
      // scaling it whole keeps type, spacing and hit targets in the
      // proportions they were designed in. `transform: scale` would blur
      // text and leave the layout at the old size; `zoom` re-lays out.
      style={wide ? { zoom: 1.12 } : undefined}
      className="motion-reduce:transition-none flex h-screen flex-col bg-white text-ink-900 dark:bg-ink-900 dark:text-ink-50"
    >
      <Header name={displayName} monogram={monogram} onBack={onBack} onClose={close} />
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {view.name === "home" && (
          <Home
            greeting={branding.greeting}
            onSearch={(query) => {
              recordEvent("searched");
              setView({ name: "results", query });
            }}
            onCompose={() => compose()}
          />
        )}
        {view.name === "results" && (
          <Results
            key={view.query}
            widgetKey={widgetKey}
            query={view.query}
            onOpen={(path) => {
              recordEvent("read");
              setView({ name: "article", path });
            }}
            onCompose={() => compose()}
          />
        )}
        {view.name === "article" && (
          <Article
            key={view.path}
            widgetKey={widgetKey}
            path={view.path}
            onCompose={() => compose()}
          />
        )}
        {view.name === "compose" && (
          <Compose
            showBack={!empty}
            onBack={goHome}
            onSent={() => {
              recordEvent("submitted");
              setView({ name: "sent" });
            }}
            onSubmit={onSubmit}
            initialEmail={email}
            initialName={name}
            transcript={transcript}
          />
        )}
        {view.name === "ask" && (
          <Ask
            widgetKey={widgetKey}
            greeting={branding.greeting}
            onDegrade={() => setView({ name: "home" })}
            onCompose={compose}
            onSubmit={onSubmit}
          />
        )}
        {view.name === "sent" && <Sent onHome={goHome} />}
      </div>
      <Footer />
    </div>
  );
}
