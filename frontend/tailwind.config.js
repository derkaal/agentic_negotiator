/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'war-bg': '#0a0e1a',
        'war-panel': '#111827',
        'war-border': '#1f2937',
        'war-accent': '#06b6d4',
        'war-green': '#10b981',
        'war-red': '#ef4444',
        'war-yellow': '#f59e0b',
        'war-purple': '#8b5cf6',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-fast': 'pulse 0.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'veto-flash': 'veto 0.3s ease-in-out 3',
        'fade-in': 'fadeIn 0.3s ease-in-out',
      },
      keyframes: {
        veto: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.4', transform: 'scale(1.05)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
