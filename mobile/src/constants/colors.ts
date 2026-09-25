/**
 * Palette PrixMaroc
 *
 * Direction : émeraude profond sur ivoire chaud, relevé de safran.
 *
 * Le fond était un vert menthe froid — la teinte des applications
 * administratives, pas celle d'une application de courses. L'ivoire réchauffe
 * l'ensemble et fait ressortir les produits, qui sont l'essentiel.
 *
 * Le safran porte ce qui doit attirer l'œil : les prix, les promotions, les
 * boutons secondaires. C'est la couleur de l'épice marocaine la plus connue,
 * et celle qui donne faim. L'émeraude reste l'identité : en-têtes, boutons
 * d'action, navigation.
 *
 * La terre cuite signale la baisse de prix et le souk.
 */
export const Colors = {
  // ── Primaire — Vert forêt ──────────────────────────────────────────────────
  primary: {
    50:  '#E4F1EA',
    100: '#C6E5D6',
    200: '#95CEB4',
    300: '#5CB393',
    400: '#2E9670',
    500: '#157155',
    600: '#0E5C44',   // ← couleur principale (boutons, en-têtes)
    700: '#0A4835',
    800: '#073A2B',
    900: '#052A1F',
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
    400: '#F8C874',
    500: '#F2A93B',
    600: '#CE8B18',
  },

  // ── Référence drapeau marocain ─────────────────────────────────────────────
  maroc: {
    vert: '#0E5C44',
    rouge: '#D0402F',
    or: '#F2A93B',
  },

  // ── Surfaces ───────────────────────────────────────────────────────────────
  surface: {
    white: '#FFFFFF',
    secondary: '#FBF7F1',   // fond général — menthe très pâle, chaud
    tertiary: '#F3EDE3',    // aplats, vignettes produit
    card: '#FFFFFF',
    overlay: 'rgba(10,45,34,0.55)',
  },

  // ── Bordures ───────────────────────────────────────────────────────────────
  border: {
    light: '#EBE3D7',
    default: '#DBD0BF',
    strong: '#B3A692',
  },

  // ── Texte ─────────────────────────────────────────────────────────────────
  text: {
    primary:   '#14211B',
    secondary: '#5A6A61',
    tertiary:  '#93A09A',
    inverse:   '#FFFFFF',
    link:      '#0E5C44',
  },

  // ── Sémantiques ────────────────────────────────────────────────────────────
  success: '#16A34A',
  warning: '#F2A93B',
  error:   '#DC2626',
  info:    '#2563EB',
  promo:   '#D0402F',

  // ── Ombres ─────────────────────────────────────────────────────────────────
  shadow: {
    light: 'rgba(20,33,27,0.05)',
    medium: 'rgba(20,33,27,0.08)',
    strong: 'rgba(20,33,27,0.14)',
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
  /** Safran — prix, promotions, boutons secondaires. */
  safran: '#F2A93B',
  safranPale: '#FDF0DA',
  /** Terre cuite — baisse de prix, souk. */
  terre: '#D0402F',
} as const;

/** Rayons de coin — cartes très arrondies, dans l'esprit des apps de courses. */
export const Radius = {
  sm: 10,
  md: 14,
  lg: 20,
  xl: 26,
  pill: 999,
} as const;
