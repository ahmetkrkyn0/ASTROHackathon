/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#1e293b",
        secondary: "#10b981",
        tertiary: "#f59e0b",
        error: "#ef4444",
        surface: "#ffffff",
        "surface-variant": "#f8fafc",
        outline: "#e2e8f0",
      },
      borderRadius: {
        DEFAULT: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
};
