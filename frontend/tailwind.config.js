/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'risk-low': '#22c55e',
        'risk-moderate': '#84cc16',
        'risk-elevated': '#f59e0b',
        'risk-high': '#f97316',
        'risk-critical': '#ef4444',
        'surface': '#0f172a',
        'surface-2': '#1e293b',
        'surface-3': '#334155',
        'accent': '#3b82f6',
        'accent-2': '#6366f1',
      },
    },
  },
  plugins: [],
}
