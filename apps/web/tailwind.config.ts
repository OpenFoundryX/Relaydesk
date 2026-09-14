import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import defaultTheme from "tailwindcss/defaultTheme";

/**
 * Relaydesk design tokens.
 *
 * `ink` and `accent` are the CONSOLE's scale: text, borders, surfaces and
 * primary buttons for the product surfaces someone stares at all day.
 *
 * Everything below them is the marketing site's "Steep" system and is used
 * nowhere in the console, the portal or the widget. It is deliberately a
 * separate set of tokens rather than a redefinition of `ink`/`accent`, so
 * restyling the public site can never silently restyle the product.
 *
 * The base is ink on paper with three greys for recessive text. On top of
 * that sit four ACCENT PAIRS, each a soft tint with its own deep ink:
 *
 *     blush-peach  / sienna-brown
 *     mist-blue    / navy-ink
 *     sage-green   / forest-ink
 *     lilac-haze   / plum-ink
 *
 * A tint is only ever a surface and its partner ink is the only text colour
 * allowed on it -- never the reverse, and never an ink on white. That pairing
 * is what keeps four colours from reading as four brands.
 *
 * Spacing intentionally has no custom tokens: Steep's 4px base unit already
 * maps 1:1 onto Tailwind's default scale (p-5 = 20px, gap-20 = 80px), and
 * overriding numeric spacing keys here would resize the whole console.
 */
const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", ...defaultTheme.fontFamily.sans],
        mono: ["var(--font-geist-mono)", ...defaultTheme.fontFamily.mono],
        // The marketing display face: Bricolage Grotesque, loaded in the
        // marketing layout. Keyed by ROLE, not by family, so swapping the
        // family again cannot leave a token here naming a font nobody uses.
        // (`font-display` and `text-display` are different utilities --
        // fontFamily and fontSize do not share a prefix.)
        display: [
          "var(--font-display)",
          "ui-sans-serif",
          "system-ui",
          "Helvetica Neue",
          "sans-serif",
        ],
        // The marketing text face: Inter. Variable, so the 430/450/480
        // half-steps below are real interpolated weights, not rounded ones.
        body: [
          "var(--font-body)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      fontSize: {
        caption: ["15px", { lineHeight: "1.5" }],
        body: ["17px", { lineHeight: "1.35" }],
        "body-lg": ["20px", { lineHeight: "1.35" }],
        subheading: ["22px", { lineHeight: "1.5" }],
        "heading-sm": [
          "26px",
          { lineHeight: "1.18", letterSpacing: "-0.23px" },
        ],
        heading: ["44px", { lineHeight: "1.3", letterSpacing: "-0.66px" }],
        "heading-lg": ["64px", { lineHeight: "1.3", letterSpacing: "-0.96px" }],
        display: ["90px", { lineHeight: "1.3", letterSpacing: "-2.25px" }],
      },
      fontWeight: {
        w430: "430",
        w450: "450",
        w480: "480",
      },
      colors: {
        ink: {
          50: "#FAFAFA",
          100: "#F4F4F5",
          200: "#E4E4E7",
          300: "#D4D4D8",
          400: "#A1A1AA",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B",
          950: "#09090B",
        },
        accent: {
          50: "#F9FCE9",
          100: "#F1F9C5",
          200: "#E5F495",
          300: "#D6EC5F",
          400: "#CBE84A",
          500: "#C4E538",
          600: "#A6C42D",
          700: "#8FA82B",
          800: "#6E8225",
          900: "#5A6A23",
          950: "#2F3A0F",
        },
        "ink-black": "#17191c",
        "paper-white": "#ffffff",
        "mist-gray": "#f2f2f3",
        "fog-white": "#fafafb",
        "slate-gray": "#777b86",
        "ash-gray": "#979799",
        "smoke-gray": "#a3a6af",
        "blush-peach": "#fbe1d1",
        "sienna-brown": "#5d2a1a",
        "mist-blue": "#dbe5fb",
        "navy-ink": "#1f3a6d",
        "sage-green": "#d8ecdb",
        "forest-ink": "#1f4a31",
        "lilac-haze": "#e7dcf6",
        "plum-ink": "#402663",
        hairline: "#ececec",
        danger: {
          50: "#FEF2F2",
          200: "#FECACA",
          600: "#DC2626",
          700: "#B91C1C",
        },
        positive: {
          50: "#F0FDF4",
          200: "#BBF7D0",
          600: "#16A34A",
        },
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
        // Steep's two structural radii, plus the artifact and input sizes.
        // Named rather than reusing 2xl/3xl so the intent survives a reader.
        image: "12px",
        input: "16px",
        elevated: "20px",
        card: "24px",
      },
      boxShadow: {
        overlay:
          "0 10px 38px -10px rgb(9 9 11 / 0.20), 0 10px 20px -15px rgb(9 9 11 / 0.15)",
        // Steep, marketing only. Floating product artifacts are the ONLY
        // elements that earn elevation -- content cards stay flat.
        artifact:
          "rgba(4,23,43,0.05) 0px 0px 0px 1px, rgba(0,0,0,0.1) 0px 20px 25px -5px, rgba(0,0,0,0.1) 0px 8px 10px -6px",
        "overlay-card":
          "oklab(0 0 0 / 0.05) 0px 0px 0px 1px, rgba(0,0,0,0.1) 0px 8px 40px 0px",
        popover:
          "oklab(0 0 0 / 0.05) 0px 0px 0px 1px, rgba(0,0,0,0.08) 0px 4px 24px 0px",
      },
      keyframes: {
        // --- Marketing motion. Matches steep.app's approach: a handful of
        // CSS keyframes, no animation library, no video or GIF assets. ---

        // The duplicated strip translates exactly half its width, so the
        // seam lands where the second copy starts and the loop is invisible.
        carousel: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
        "fade-in-y": {
          from: { opacity: "0", transform: "translateY(18px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        // Paths carry pathLength={1}, so the offset is a plain 0..1 fraction
        // and one keyframe serves every line whatever its real length.
        "draw-line": {
          from: { strokeDashoffset: "1" },
          to: { strokeDashoffset: "0" },
        },
        // Stops at the ring's own value rather than 0, set per instance.
        "draw-ring": {
          from: { strokeDashoffset: "1" },
          to: { strokeDashoffset: "var(--ring-to)" },
        },
        caret: {
          "0%, 45%": { opacity: "1" },
          "50%, 95%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "overlay-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "content-in": {
          from: { opacity: "0", transform: "translateY(4px) scale(0.98)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        carousel: "carousel 45s linear infinite",
        "fade-in-y": "fade-in-y 750ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "draw-line": "draw-line 1.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        "draw-ring": "draw-ring 1.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        caret: "caret 1.1s steps(1, end) infinite",
        "overlay-in": "overlay-in 150ms ease-out",
        "content-in": "content-in 150ms ease-out",
      },
    },
  },
  plugins: [animate],
};

export default config;
