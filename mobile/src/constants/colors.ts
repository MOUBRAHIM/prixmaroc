/**
 * Palette de couleurs PrixMaroc
 * Vert Maroc (#16a34a) + accents modernes
 */
export const Colors = {
  // ── Primaire — Vert Maroc ──────────────────────────────────────────────────
  primary: {
    50:  '#f0fdf4',
    100: '#dcfce7',
    200: '#bbf7d0',
    300: '#86efac',
    400: '#4ade80',
    500: '#22c55e',
    600: '#16a34a',   // ← couleur principale
    700: '#15803d',
    800: '#166534',
    900: '#14532d',
  },

  // ── Secondaire — Orange chaud ──────────────────────────────────────────────
  secondary: {
    400: '#fb923c',
    500: '#f97316',
    600: '#ea580c',
  },

  // ── Or / Accent drapeau ────────────────────────────────────────────────────
  gold: {
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
  },

  // ── Référence drapeau marocain ─────────────────────────────────────────────
  maroc: {
    vert: '#16a34a',
    rouge: '#c1272d',
    or: '#f59e0b',
  },

  // ── Surfaces ───────────────────────────────────────────────────────────────
  surface: {
    white: '#ffffff',
    secondary: '#f8fafc',
    tertiary: '#f1f5f9',
    card: '#ffffff',
    overlay: 'rgba(0,0,0,0.5)',
  },

  // ── Bordures ───────────────────────────────────────────────────────────────
  border: {
    light: '#e2e8f0',
    default: '#cbd5e1',
    strong: '#94a3b8',
  },

  // ── Texte ─────────────────────────────────────────────────────────────────
  text: {
    primary:   '#0f172a',
    secondary: '#475569',
    tertiary:  '#94a3b8',
    inverse:   '#ffffff',
    link:      '#16a34a',
  },

  // ── Sémantiques ────────────────────────────────────────────────────────────
  success: '#16a34a',
  warning: '#f59e0b',
  error:   '#ef4444',
  info:    '#3b82f6',
  promo:   '#dc2626',

  // ── Ombres ─────────────────────────────────────────────────────────────────
  shadow: {
    light: 'rgba(0,0,0,0.06)',
    medium: 'rgba(0,0,0,0.1)',
    strong: 'rgba(0,0,0,0.18)',
  },
} as const;

// Alias pratiques
export const C = {
  primary: Colors.primary[600],
  primaryLight: Colors.primary[100],
  primaryDark: Colors.primary[800],
  secondary: Colors.secondary[500],
  bg: Colors.surface.secondary,
  card: Colors.surface.card,
  border: Colors.border.light,
  text: Colors.text.primary,
  textSub: Colors.text.secondary,
  textMuted: Colors.text.tertiary,
  white: '#ffffff',
  promo: Colors.promo,
  gold: Colors.gold[500],
} as const;
