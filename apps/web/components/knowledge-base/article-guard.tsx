"use client";

import {
  createContext,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

/**
 * The channel between the sidebar and whichever article is open beside it.
 *
 * Saving is explicit, so an article with unsaved edits has to be able to
 * stop a navigation and ask first. In the old two-page flow the only way out
 * was the editor's own back link, which the editor could intercept by
 * itself. In a master-detail layout the likelier exit is a click on a
 * *different article in the sidebar* -- and the sidebar lives in the layout,
 * a sibling of the editor with no way to see its state.
 *
 * So the editor registers the question and the sidebar asks it. The dialog,
 * the dirty flag and the decision to leave all stay inside the editor, which
 * is the only thing that knows whether anything is unsaved; the sidebar
 * learns one bit -- "I have taken this over, do not navigate" -- and nothing
 * else.
 */
interface ArticleGuard {
  /**
   * Called by the open editor. `ask` returns true when it has taken
   * responsibility for what was about to happen, and will run `proceed`
   * itself if the reader says to go ahead. Returns an unregister function.
   */
  register: (ask: (proceed: () => void) => boolean) => () => void;
  /**
   * Called before doing something that leaves the open article behind --
   * following a link, or opening the dialog whose Create redirects into a
   * new one. True means stop: something else is asking the reader first,
   * and will run `proceed` if they agree.
   */
  askBefore: (proceed: () => void) => boolean;
}

/**
 * With no provider above it -- an editor rendered on its own, as the unit
 * tests do -- nothing registers and nothing blocks, and the editor's own
 * breadcrumb guard is unaffected.
 */
const fallback: ArticleGuard = {
  register: () => () => {},
  askBefore: () => false,
};

const ArticleGuardContext = createContext<ArticleGuard>(fallback);

export function useArticleGuard(): ArticleGuard {
  return useContext(ArticleGuardContext);
}

/**
 * Holds the registration in a ref rather than in state on purpose: the
 * editor registering itself must not re-render the sidebar, and the value
 * handed down never changes identity.
 */
export function ArticleGuardProvider({ children }: { children: ReactNode }) {
  const asker = useRef<((proceed: () => void) => boolean) | null>(null);

  const value = useMemo<ArticleGuard>(
    () => ({
      register(ask) {
        asker.current = ask;
        return () => {
          // Only clear our own registration. Two editors are never mounted
          // together, but an unmount that ran after the next mount would
          // otherwise leave the sidebar unguarded.
          if (asker.current === ask) asker.current = null;
        };
      },
      askBefore(proceed) {
        return asker.current?.(proceed) ?? false;
      },
    }),
    [],
  );

  return (
    <ArticleGuardContext.Provider value={value}>
      {children}
    </ArticleGuardContext.Provider>
  );
}
