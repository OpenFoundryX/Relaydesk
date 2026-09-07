"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

import { OnboardingWizard } from "./onboarding-wizard";

const OnboardingContext = createContext<{ open: () => void }>({ open: () => {} });

export function useOnboarding() {
  return useContext(OnboardingContext);
}

/**
 * The wizard is opened deliberately, from the "Finish setup" card in the
 * sidebar. Auto-opening it on load would mean reading session storage during
 * render, which either mismatches on hydration or needs a setState in an
 * effect -- and a modal that ambushes you on every fresh tab is worse anyway.
 */
export function OnboardingProvider({
  children,
  isAdmin,
}: {
  children: ReactNode;
  isAdmin: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <OnboardingContext.Provider value={{ open: () => setOpen(true) }}>
      {children}
      {/* Every step of the wizard, and every link in its last one, points
          at workspace configuration an agent cannot open. The context
          stays mounted either way so useOnboarding() is always safe. */}
      {isAdmin && <OnboardingWizard open={open} onOpenChange={setOpen} />}
    </OnboardingContext.Provider>
  );
}
