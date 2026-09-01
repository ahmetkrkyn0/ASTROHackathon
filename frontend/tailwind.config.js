/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],

  // Preflight is OFF on purpose. App.css is ~1800 lines of hand-written rules
  // that predate Tailwind and style bare elements (button, input[type=range],
  // h1-h6) directly. Tailwind's reset would flatten all of it on first load.
  // Utilities are additive here; the cascade stays where it was.
  corePlugins: { preflight: false },

  theme: {
    extend: {
      colors: {
        // The two accents are an axis, not a brand pair: at the lunar south
        // pole the sun grazes the horizon, so every cell in this dataset is
        // either lit or in permanent shadow. Amber reads as sunlit -- energy,
        // and the action you take. Cyan reads as shadowed -- cold, and the
        // data you read. Anything already carrying meaning (the risk ramp,
        // battery green) is deliberately absent: it is defined in App.css and
        // must not be restyled for looks.
        terminator: {
          DEFAULT: '#ffb84d',
          dim: 'rgba(255, 184, 77, 0.16)',
        },
        umbra: {
          DEFAULT: '#5ad2ff',
          dim: 'rgba(90, 210, 255, 0.16)',
        },
        void: '#05070d',
        glass: {
          DEFAULT: 'rgba(9, 13, 22, 0.62)',
          strong: 'rgba(9, 13, 22, 0.78)',
        },
        hairline: 'rgba(148, 163, 184, 0.22)',
      },
      fontFamily: {
        display: ['Outfit', 'Segoe UI', 'sans-serif'],
        body: ['Manrope', 'Segoe UI', 'sans-serif'],
        data: ['IBM Plex Mono', 'Cascadia Code', 'monospace'],
      },
      backdropBlur: {
        console: '18px',
      },
    },
  },

  plugins: [],
}
