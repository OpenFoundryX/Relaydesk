import type { ReactNode } from "react";
import { Bricolage_Grotesque, Inter } from "next/font/google";

import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

/**
 * The marketing site's two faces.
 *
 * Display is Bricolage Grotesque: a variable grotesque with genuine quirk in
 * the letterforms, loaded with its `opsz` and `wdth` axes so headlines at
 * 90px and labels at 14px each get drawing meant for that size rather than
 * one outline scaled up and down.
 *
 * Body stays Inter, and that pairing is deliberate: the display face carries
 * all the personality, so the text face is chosen to be unremarkable and
 * highly readable. Inter is also variable, which is what makes the 430/450/480
 * half-steps real interpolated weights rather than rounded ones.
 *
 * Both are loaded here rather than in the root layout so the console, portal
 * and widget never pay for two fonts they do not render.
 */
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  axes: ["opsz", "wdth"],
  display: "swap",
  variable: "--font-display",
});

const body = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body",
});

/**
 * Public marketing site. Paper-white canvas, grotesque display, and four
 * accent tints; the console's tokens are not used anywhere below here.
 */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className={`site-marketing ${display.variable} ${body.variable} min-h-screen bg-paper-white font-body text-ink-black antialiased`}
    >
      <SiteHeader />
      <main>{children}</main>
      <SiteFooter />
    </div>
  );
}
