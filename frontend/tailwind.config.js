/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom colors based on the report
        'tech-blue': '#3B82F6',
        'tech-purple': '#A855F7',
        'warm-orange': '#F97316',
        'warm-pink': '#EC4899',
      },
      animation: {
        'typing': 'typing 1.4s infinite both',
      },
      keyframes: {
        typing: {
          '0%, 80%, 100%': { opacity: '0.4' },
          '40%': { opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}
