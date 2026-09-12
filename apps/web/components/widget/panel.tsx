"use client";

import { useEffect, useRef, useState } from "react";

import { Ask } from "@/components/widget/ask";
import { Compose } from "@/components/widget/compose";
import { Footer } from "@/components/widget/footer";
import { Header } from "@/components/widget/header";
import { Help } from "@/components/widget/help";
import { Home } from "@/components/widget/home";
import { Sent } from "@/components/widget/sent";
import { TabBar, type PanelTab } from "@/components/widget/tab-bar";
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

// The Home tab's own sub-navigation. Compose is reachable from Home
// (secondary, or the whole of the primary card without AI) and from Ask's
// escalate button; Ask is reachable only from Home's primary card, only
// when `aiEnabled`; Sent is terminal. Search, results and reading an
// article used to be here too -- they now live behind the Help tab
// in `help.tsx`.
type HomeView =
  | { name: "home" }
  | { name: "compose" }
  | { name: "ask" }
  | { name: "sent" };

/**
 * The widget panel: everything a visitor sees inside the loader's iframe
 * (spec D5). A persistent bottom tab bar -- Home, Messages, Help -- sits
 * over three screens; only Home has any sub-navigation of its own today,
 * modelled on Intercom's Messenger.
 *
 * Two rules carry meaning, not taste, and are enforced by which button
 * variant each screen is given, not by anything here: "Send a message" is
 * secondary on Home and primary once the visitor has tried to self-serve
 * -- the deflection hierarchy the design draws in
 * `docs/superpowers/specs/2026-09-10-support-widget-design.md` §7 -- and
 * dark mode follows `prefers-color-scheme` only, via Tailwind's `dark:`
 * variant, because the frame is cross-origin from the host page and has no
 * other signal for it.
 */
/** How much larger the panel is drawn on a laptop-sized host page. */
const PANEL_ZOOM = 1.12;

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

  // Which tab is active. Starts on Home always -- an empty knowledge base
  // or a configured AI both decide what Home itself opens on (below), not
  // which tab that is; there is nothing to search yet either way, so
  // starting anywhere else has nothing to offer.
  const [tab, setTab] = useState<PanelTab>("home");

  // Three day-one states, in priority order, exactly as before. An empty
  // knowledge base still opens on `compose` and never mounts a search
  // affordance (spec D7, slice 8) -- that rule is untouched, and it
  // outranks everything else because a model with nothing to ground an
  // answer in cannot answer either.
  //
  // Otherwise: Home. An earlier rule opened a configured workspace
  // straight into the conversation, which made sense when the conversation
  // WAS the panel -- but the tab bar hides inside a conversation (it is a
  // full-height screen with its own way back), so opening there meant a
  // visitor never saw Home, Help, or the tabs at all. Home now carries
  // "Ask a question" as its first card, which is one tap and shows the
  // visitor what else is here.
  const [homeView, setHomeView] = useState<HomeView>(() =>
    empty ? { name: "compose" } : { name: "home" },
  );

  // Whether the Help tab is showing a full-height screen
  // of its own -- reading an article, the same way Article used to. Set by
  // nothing today (the placeholder never calls it), but wired through so
  // the real Help component has a working `onFullScreenChange` the moment
  // it lands, instead of needing another round trip through panel.tsx.
  const [helpFullScreen, setHelpFullScreen] = useState(false);

  // Set only by Ask's escalate button, from the turns already on screen
  // (task 11, spec D8): the agent reading the resulting ticket must see
  // what the visitor was already told, not just what they typed into
  // Compose. Reset by every other route into Compose, so a transcript
  // from an earlier, abandoned conversation can never ride along on a
  // ticket that has nothing to do with it.
  const [transcript, setTranscript] = useState("");
  const compose = (nextTranscript = "") => {
    setTranscript(nextTranscript);
    // Always lands on the Home tab -- the message form has never lived
    // anywhere else, so a visitor who escalates from a future Help
    // article is brought back to Home to finish it, the same way Ask's
    // own escalate button already does today.
    setTab("home");
    setHomeView({ name: "compose" });
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
  // keystroke or an article re-opened twice must not inflate it. Only
  // `submitted` is posted from here today -- `searched` and `read` moved
  // with the search/results/article flow into the Help tab, and have
  // nowhere left to fire from until that component (built separately, in
  // `help.tsx`) wires them back in against its own search box and its own
  // article view.
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
  // for it -- Compose's own back button and Sent's "Back to home". `empty`
  // gates the panel's *initial* view (above), but a transition is a second,
  // independent way to reach `home`, and both of these were reachable even
  // when the knowledge base is empty: Compose is the initial screen there,
  // so both its back button and, after a real submission, Sent are always
  // live. Routing both through this rather than `{ name: "home" }` directly
  // is what stops a visitor on a zero-article workspace from ever reaching
  // the cards Home renders -- the exact failure mode spec D7 exists to
  // prevent.
  const goHome = () => setHomeView(empty ? { name: "compose" } : { name: "home" });

  // A full-height screen hides the tab bar and gets no back-chevron of its
  // own from Header -- it carries its own back control instead, exactly as
  // the reference does it: Compose's inline "Back" link, Sent's "Back to
  // home", and (once Help is built) an article's own way out. Nothing here
  // routes through Header's `onBack` today -- that prop existed only for
  // Results and Article, which have both moved behind the Help tab -- so it
  // is passed as `undefined` unconditionally until that component defines
  // its own equivalent.
  // Bigger while reading or in a conversation, back to normal on the way
  // out -- the two places a visitor is doing something that wants room.
  // A visitor who works the control themselves has said what they want,
  // so `chosen` stops the automatic behaviour second-guessing them for
  // the rest of the session.
  const [expanded, setExpanded] = useState(false);
  const chosen = useRef(false);

  const fullScreen =
    (tab === "home" && homeView.name !== "home") || (tab === "help" && helpFullScreen);

  // Only where there is room: the loader ignores these below 1024px, and
  // offering a control that does nothing is worse than offering none.
  const resizable = Boolean(wide);

  function setSize(next: boolean) {
    setExpanded(next);
    window.parent?.postMessage(next ? "relaydesk:expand" : "relaydesk:collapse", "*");
  }

  useEffect(() => {
    if (!resizable || chosen.current) return;
    setSize(fullScreen);
    // `setSize` is stable enough for this: it only closes over setState and
    // `window`, neither of which changes across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullScreen, resizable]);

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
      //
      // The height has to be divided back out. `zoom` scales the element's
      // own box too, so `h-screen` at 1.12 is 112% of the iframe -- the
      // header goes off the top and the footer off the bottom. Asking for
      // 100vh/1.12 and letting zoom multiply it lands exactly on the
      // viewport.
      style={wide ? { zoom: PANEL_ZOOM, height: `calc(100vh / ${PANEL_ZOOM})` } : undefined}
      className="motion-reduce:transition-none flex h-screen flex-col bg-white text-ink-900 dark:bg-ink-900 dark:text-ink-50"
    >
      <Header
        name={displayName}
        monogram={monogram}
        // A conversation hides the tab bar, so without this there is no
        // way back to Home short of the answer failing. Compose and Sent
        // carry their own back controls; Ask did not carry any.
        onBack={tab === "home" && homeView.name === "ask" ? goHome : undefined}
        onClose={close}
        expanded={expanded}
        onToggleExpand={
          resizable
            ? () => {
                chosen.current = true;
                setSize(!expanded);
              }
            : undefined
        }
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {/* Both tabs stay mounted regardless of which is showing --
            `hidden` only toggles `display`, not presence -- so switching
            tabs never loses where the visitor was: a conversation
            mid-stream, a half-typed message, or (once Help is real)
            wherever its own search left off. */}
        <div className={tab === "home" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
          {homeView.name === "home" && (
            <Home
              workspaceName={displayName}
              name={name}
              aiEnabled={aiEnabled}
              articleCount={articleCount}
              onAsk={() => setHomeView({ name: "ask" })}
              onCompose={() => compose()}
              onSearchHelp={() => setTab("help")}
            />
          )}
          {homeView.name === "compose" && (
            <Compose
              showBack={!empty}
              onBack={goHome}
              onSent={() => {
                recordEvent("submitted");
                setHomeView({ name: "sent" });
              }}
              onSubmit={onSubmit}
              initialEmail={email}
              initialName={name}
              transcript={transcript}
            />
          )}
          {homeView.name === "ask" && (
            <Ask
              widgetKey={widgetKey}
              greeting={branding.greeting}
              onDegrade={() => setHomeView({ name: "home" })}
              onCompose={compose}
              onSubmit={onSubmit}
            />
          )}
          {homeView.name === "sent" && <Sent onHome={goHome} />}
        </div>

        <div className={tab === "help" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
          <Help
            widgetKey={widgetKey}
            onCompose={() => setTab("home")}
            onEvent={recordEvent}
          />
        </div>
      </div>
      {!fullScreen && <TabBar tab={tab} onChange={setTab} />}
      <Footer />
    </div>
  );
}
