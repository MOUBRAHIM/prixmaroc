/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./App.tsx', './src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        // Palette PrixMaroc — Vert Maroc + accents modernes
        primary: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',   // Couleur principale (vert drapeau marocain)
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        secondary: {
          50:  '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f97316',   // Orange accent (chaud)
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
        },
        gold: {
          400: '#fbbf24',
          500: '#f59e0b',   // Or (référence drapeau)
          600: '#d97706',
        },
        red: {
          maroc: '#c1272d',  // Rouge du drapeau marocain
        },
        surface: {
          DEFAULT: '#ffffff',
          secondary: '#f8fafc',
          tertiary: '#f1f5f9',
        },
        border: {
          light: '#e2e8f0',
          DEFAULT: '#cbd5e1',
        },
        text: {
          primary:   '#0f172a',
          secondary: '#475569',
          tertiary:  '#94a3b8',
          inverse:   '#ffffff',
        },
        success: '#16a34a',
        warning: '#f59e0b',
        error:   '#ef4444',
        info:    '#3b82f6',
        promo:   '#dc2626',   // Rouge promotions
      },
      fontFamily: {
        sans: ['System'],
        bold: ['System'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        card: '0 2px 8px rgba(0,0,0,0.08)',
        'card-lg': '0 4px 16px rgba(0,0,0,0.12)',
      },
    },
  },
  plugins: [],
};
