import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    screens: { sm: "480px", md: "768px", lg: "1024px", xl: "1280px" },
    colors: {
      transparent: "transparent",
      current: "currentColor",
      paper: token("paper"),
      surface: token("surface"),
      sunken: token("sunken"),
      line: token("line"),
      ink: { DEFAULT: token("ink"), soft: token("ink-soft"), faint: token("ink-faint") },
      pine: { DEFAULT: token("pine"), strong: token("pine-strong"), soft: token("pine-soft") },
      mustard: {
        DEFAULT: token("mustard"),
        ink: token("mustard-ink"),
        soft: token("mustard-soft"),
      },
      berry: { DEFAULT: token("berry"), soft: token("berry-soft") },
      white: "#ffffff",
      "on-pine": token("on-pine"),
    },
    fontFamily: {
      display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
      body: ['"Atkinson Hyperlegible"', "ui-sans-serif", "system-ui", "sans-serif"],
    },
    fontSize: {
      xs: ["0.8125rem", { lineHeight: "1.25rem" }],
      sm: ["0.875rem", { lineHeight: "1.375rem" }],
      base: ["1rem", { lineHeight: "1.6rem" }],
      lg: ["1.1875rem", { lineHeight: "1.75rem" }],
      xl: ["1.5rem", { lineHeight: "1.9rem" }],
      "2xl": ["2rem", { lineHeight: "2.25rem" }],
      "3xl": ["2.75rem", { lineHeight: "2.9rem" }],
    },
    borderRadius: { none: "0", sm: "6px", md: "10px", lg: "18px", full: "9999px" },
    extend: {
      spacing: { 11: "2.75rem", 18: "4.5rem" },
      maxWidth: { prose: "68ch" },
      keyframes: {
        "progress-indeterminate": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(300%)" },
        },
      },
      animation: { "progress-indeterminate": "progress-indeterminate 1.2s ease-in-out infinite" },
    },
  },
  plugins: [],
} satisfies Config;
