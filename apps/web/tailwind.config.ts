import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import defaultTheme from "tailwindcss/defaultTheme";

/**
 * Relaydesk design tokens.
 *
 * `ink` is the neutral spine of the UI: text, borders, surfaces, and primary
 * buttons all come from it. `accent` is citron, used only for active states,
 * focus rings, and data marks -- never for text on a light surface, where it
 * cannot hold contrast below `accent-800`.
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
      },
      boxShadow: {
        overlay:
          "0 10px 38px -10px rgb(9 9 11 / 0.20), 0 10px 20px -15px rgb(9 9 11 / 0.15)",
      },
      keyframes: {
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
        "overlay-in": "overlay-in 150ms ease-out",
        "content-in": "content-in 150ms ease-out",
      },
    },
  },
  plugins: [animate],
};

export default config;
