/**
 * Palette PrixMaroc
 *
 * Direction : vert forêt profond (sérieux, premium) sur fond menthe chaud,
 * relevé d'un citron vert pour les mises en avant et d'un ambre pour les
 * économies. La terre cuite reste réservée au souk (identité marocaine).
 *
 * Le vert profond porte les surfaces d'action (boutons, en-têtes) ; le vert
 * vif est conservé pour les signaux positifs (baisse de prix, validation).
 */
export const Colors = {
  // ── Primaire — Vert forêt ──────────────────────────────────────────────────
  primary: {
    50:  '#EEF6F1',
    100: '#D3E8DC',
    200: '#A7D1BA',
    300: '#6FB294',
    400: '#3D8F6E',
    500: '#1E6B4F',
    600: '#0F4C3A',   // ← couleur principale (boutons, en-têtes)
    700: '#0C3F30',
    800: '#093126',
    900: '#06231B',
  },

  // ── Accent — Citron vert (mises en avant, "meilleur prix") ─────────────────
  accent: {
    100: '#F0F8D9',
    300: '#CDE87F',
    500: '#A3D93B',
    600: '#8BC22C',
  },

  // ── Secondaire — Terre cuite (souk, marchés) ───────────────────────────────
  secondary: {
    400: '#E08A4E',
    500: '#C2571A',
    600: '#A04512',
  },

  // ── Or / Économies ─────────────────────────────────────────────────────────
  gold: {
    400: '#F5C25B',
    500: '#E8A020',
    600: '#C4820F',
  },

  // ── Référence drapeau marocain ─────────────────────────────────────────────
  maroc: {
    vert: '#0F4C3A',
    rouge: '#C1272D',
    or: '#E8A020',
  },

  // ── Surfaces ───────────────────────────────────────────────────────────────
  surface: {
    white: '#FFFFFF',
    secondary: '#F2F6F0',   // fond général — menthe très pâle, chaud
    tertiary: '#E9F0E6',    // aplats, vignettes produit
    card: '#FFFFFF',
    overlay: 'rgba(6,35,27,0.55)',
  },

  // ── Bordures ───────────────────────────────────────────────────────────────
  border: {
    light: '#E2E9DF',
    default: '#C9D5C4',
    strong: '#93A28D',
  },

  // ── Texte ─────────────────────────────────────────────────────────────────
  text: {
    primary:   '#0B2019',
    secondary: '#4A5B53',
    tertiary:  '#8A9A92',
    inverse:   '#FFFFFF',
    link:      '#0F4C3A',
  },

  // ── Sémantiques ────────────────────────────────────────────────────────────
  success: '#16A34A',
  warning: '#E8A020',
  error:   '#DC2626',
  info:    '#2563EB',
  promo:   '#C1272D',

  // ── Ombres ─────────────────────────────────────────────────────────────────
  shadow: {
    light: 'rgba(11,32,25,0.05)',
    medium: 'rgba(11,32,25,0.09)',
    strong: 'rgba(11,32,25,0.16)',
  },
} as const;

// Alias pratiques
export const C = {
  primary: Colors.primary[600],
  primaryLight: Colors.primary[100],
  primaryDark: Colors.primary[800],
  accent: Colors.accent[500],
  accentSoft: Colors.accent[100],
  secondary: Colors.secondary[500],
  bg: Colors.surface.secondary,
  card: Colors.surface.card,
  border: Colors.border.light,
  text: Colors.text.primary,
  textSub: Colors.text.secondary,
  textMuted: Colors.text.tertiary,
  white: '#FFFFFF',
  promo: Colors.promo,
  gold: Colors.gold[500],
  goldSoft: '#FDF3DE',
  success: Colors.success,
} as const;

/** Rayons de coin — cartes très arrondies, dans l'esprit des apps de courses. */
export const Radius = {
  sm: 10,
  md: 14,
  lg: 20,
  xl: 26,
  pill: 999,
} as const;
