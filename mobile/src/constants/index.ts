export * from './colors';

import { Platform } from 'react-native';
import Constants, { ExecutionEnvironment } from 'expo-constants';

// ── URL API ──────────────────────────────────────────────────────────────────
//
//  POUR CHANGER L'URL : modifiez UNIQUEMENT la variable ENV et l'URL correspondante
//
//  'tunnel'  → Tunnel Cloudflare permanent (recommandé pour APK distribué)
//  'dev'     → IP locale WiFi (téléphone sur le même réseau que le PC)
//  'prod'    → Serveur de production VPS
//
// ── CHANGER ICI POUR LA PROD ──────────────────────────────────────────────────
//  'tunnel'  → Tunnel Cloudflare temporaire (dev sur PC)
//  'dev'     → IP locale WiFi (même réseau que le PC)
//  'prod'    → VPS permanent (app distribuable, PC éteint OK)
const ENV: 'tunnel' | 'dev' | 'prod' = 'dev'; // ← dev = backend local sur le PC (test Expo Go, même WiFi)

const _FALLBACK_URL =
  ENV === 'prod'   ? 'https://backend-production-b834.up.railway.app'              : // ← Railway Cloud (permanent)
  ENV === 'tunnel' ? 'https://parents-reconstruction-kinase-survive.trycloudflare.com' : // ← URL tunnel actif
                     'http://192.168.0.116:8000';                                    // ← IP WiFi locale

/**
 * URL de l'API.
 *
 * En production (site web déployé), on la fournit au moment du build via la
 * variable d'environnement EXPO_PUBLIC_API_URL — pas besoin de modifier le code :
 *
 *   Windows :  $env:EXPO_PUBLIC_API_URL="https://api.exemple.com"; npx expo export --platform web
 *   Netlify :  définir EXPO_PUBLIC_API_URL dans les variables du site
 *
 * Sans cette variable, on retombe sur la valeur locale ci-dessus.
 */
export const API_BASE_URL =
  (process.env.EXPO_PUBLIC_API_URL || '').trim() || _FALLBACK_URL;

export const QUERY_KEYS = {
  dashboard: ['dashboard'] as const,
  products: (params?: object) => ['products', params] as const,
  productDetail: (id: number) => ['product', id] as const,
  priceHistory: (id: number, days: number) => ['price-history', id, days] as const,
  cheapest: (productId: number, city?: string) => ['cheapest', productId, city] as const,
  promotions: (city?: string) => ['promotions', city] as const,
  storesNearby: (lat: number, lng: number, radius: number) => ['stores-nearby', lat, lng, radius] as const,
  habits: ['habits'] as const,
  promoAlerts: ['promo-alerts'] as const,
  shoppingLists: ['shopping-lists'] as const,
  shoppingList: (id: number) => ['shopping-list', id] as const,
  priceAlerts: ['price-alerts'] as const,
} as const;

export const STORAGE_KEYS = {
  accessToken: 'pm_access_token',
  user: 'pm_user',
  city: 'pm_city',
  lastSyncAt: 'pm_last_sync',
} as const;

export const PAGINATION = {
  limit: 20,
  searchLimit: 10,
} as const;

// ── Carte ──────────────────────────────────────────────────────────────────
//  react-native-maps N'EXISTE PAS dans Expo Go (SDK 54). On active donc la
//  MapView native UNIQUEMENT dans un vrai build (APK/dev-client) — où la clé
//  Google Maps du AndroidManifest est présente. Dans Expo Go, l'écran
//  "Magasins proches" affiche la liste seule (aucun montage natif → pas de crash).
//  Web : react-native-maps n'existe pas en navigateur → toujours désactivé.
const _isExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
export const MAPS_ENABLED = Platform.OS !== 'web' && !_isExpoGo;

export const MAP_DEFAULTS = {
  // Casablanca par défaut
  latitude: 33.5731,
  longitude: -7.5898,
  latitudeDelta: 0.0922,
  longitudeDelta: 0.0421,
} as const;
