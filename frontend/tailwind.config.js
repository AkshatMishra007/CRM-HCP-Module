/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Inter as the primary UI font, per assignment spec
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Single primary blue used across all buttons/links/focus states
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
        },
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
      },
    },
  },
  plugins: [],
}
