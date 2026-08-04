/**
 * Types TypeScript — Modèles PrixMaroc
 * Miroir exact des schémas Pydantic du backend FastAPI.
 */

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface Token {
  access_token: string;
  token_type: 'bearer';
}

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  phone: string | null;
  city: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string; // ISO 8601
  updated_at: string;
}

export interface UserCreate {
  email: string;
  username: string;
  password: string;
  full_name?: string;
  phone?: string;
  city?: string;
}

// ─── Catégorie ────────────────────────────────────────────────────────────────

export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string | null;
  parent_id: number | null;
}

// ─── Magasin ──────────────────────────────────────────────────────────────────

export interface Store {
  id: number;
  name: string;
  slug: string;
  address: string | null;
  city: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
  phone: string | null;
  website: string | null;
  logo_url: string | null;
  is_active: boolean;
}

export interface StoreNearby extends Store {
  distance_km: number;
  product_count: number;
}

// ─── Produit ──────────────────────────────────────────────────────────────────

export type PriceSource = 'scraper' | 'ocr' | 'manual' | 'ai';

export interface Price {
  id: number;
  product_id: number;
  store_id: number;
  price: number;
  currency: string;
  is_promo: boolean;
  promo_price: number | null;
  promo_start: string | null;
  promo_end: string | null;
  source: PriceSource;
  recorded_at: string;
}

export interface PriceInStore {
  store_id: number;
  store_name: string;
  store_city: string | null;
  price: number;
  is_promo: boolean;
  promo_price: number | null;
  effective_price: number;
  recorded_at: string;
  source: PriceSource;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  barcode: string | null;
  brand: string | null;
  description: string | null;
  image_url: string | null;
  unit: string | null;
  unit_size: string | null;
  category_id: number | null;
  category: Category | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Infos nutritionnelles (pour 100g)
  calories: number | null;
  proteins: number | null;
  lipids: number | null;
  carbs: number | null;
  fibers: number | null;
  nutriscore: string | null;
}

export interface ProductSummary {
  id: number;
  name: string;
  slug: string;
  brand: string | null;
  image_url: string | null;
  unit: string | null;
  unit_size: string | null;
  category: Category | null;
  lowest_price: number | null;
  highest_price: number | null;
  avg_price: number | null;
  store_count: number;
  has_promo: boolean;
}

export interface ProductDetail extends Product {
  prices: PriceInStore[];
  lowest_price: number | null;
  highest_price: number | null;
  avg_price: number | null;
}

// ─── Historique de prix ───────────────────────────────────────────────────────

export interface PricePoint {
  date: string;
  price: number;
  is_promo: boolean;
  store_id: number;
  store_name: string;
}

export interface PriceHistory {
  product_id: number;
  product_name: string;
  days: number;
  points: PricePoint[];
  min_price: number | null;
  max_price: number | null;
  avg_price: number | null;
}

// ─── Prix pas cher / Promotions ───────────────────────────────────────────────

export interface CheapestPrice {
  store_id: number;
  store_name: string;
  store_city: string | null;
  store_lat: number | null;
  store_lng: number | null;
  price: number;
  is_promo: boolean;
  promo_price: number | null;
  effective_price: number;
  recorded_at: string;
  savings_vs_avg: number | null;
  savings_pct: number | null;
}

export interface CheapestResponse {
  product_id: number;
  product_name: string;
  city: string | null;
  results: CheapestPrice[];
  average_price: number;
}

export interface PromoItem {
  product_id: number;
  product_name: string;
  product_image: string | null;
  store_id: number;
  store_name: string;
  store_city: string | null;
  regular_price: number;
  promo_price: number;
  discount_pct: number;
  promo_end: string | null;
  recorded_at: string;
}

// ─── Listes de courses ────────────────────────────────────────────────────────

export interface ShoppingListItem {
  id: number;
  list_id: number;
  product_id: number | null;
  custom_name: string | null;
  quantity: number;
  unit: string | null;
  is_checked: boolean;
  note: string | null;
  product?: ProductSummary;
}

export interface ShoppingList {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  is_shared: boolean;
  share_token: string | null;
  created_at: string;
  updated_at: string;
  items: ShoppingListItem[];
}

// ─── Alertes prix ─────────────────────────────────────────────────────────────

export interface PriceAlert {
  id: number;
  user_id: number;
  product_id: number;
  store_id: number | null;
  target_price: number;
  is_active: boolean;
  is_triggered: boolean;
  triggered_at: string | null;
  created_at: string;
  product?: ProductSummary;
  store?: Store;
  current_price?: number | null;
}

// ─── OCR Scan ─────────────────────────────────────────────────────────────────

export type ScanStatus = 'pending' | 'processing' | 'done' | 'failed';

export interface OcrScanItem {
  name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  is_promo?: boolean;
}

export interface OcrScan {
  id: number;
  user_id: number;
  store_id: number | null;
  image_url: string;
  raw_text: string | null;
  parsed_data: {
    store?: { name: string; chain: string };
    date?: string;
    items: OcrScanItem[];
    total?: number;
    /** Champs ajoutés après confirmation OCR */
    confirmed?: boolean;
    store_id?: number | null;
    prices_saved?: number;
    confirmed_at?: string;
  } | null;
  status: ScanStatus;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
}

// ─── IA / Recommandations ─────────────────────────────────────────────────────

export interface PurchaseHabit {
  product_name: string;
  product_id: number | null;
  purchase_frequency: number;
  avg_quantity: number;
  avg_price: number;
  category: string | null;
  is_recurrent: boolean;
  last_seen: string;
  total_purchases: number;
}

export interface GeneratedListItem {
  product_name: string;
  product_id: number | null;
  quantity: number;
  unit: string | null;
  estimated_price_unit: number;
  estimated_price_total: number;
  store_id: number | null;
  store_name: string | null;
  is_promo: boolean;
  reasoning: string;
  category: string;
}

export type ListType = 'hebdo' | 'bi-mensuel' | 'mensuel';

export interface GeneratedList {
  user_id: number;
  list_type: ListType;
  budget_max: number | null;
  total_estimated: number;
  items: GeneratedListItem[];
  recommended_stores: string[];
  budget_status: 'dans_budget' | 'dépasse_budget' | 'pas_de_budget';
  global_reasoning: string;
  generated_at: string;
  claude_model: string;
  fallback_mode: boolean;
}

export interface PromoAlert {
  product_id: number;
  product_name: string;
  product_image: string | null;
  store_id: number;
  store_name: string;
  store_city: string | null;
  regular_price: number;
  promo_price: number;
  discount_pct: number;
  purchase_frequency: number;
  relevance_score: number;
  reason: string;
  recorded_at: string;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface DayPoint {
  date: string;
  savings: number;
}

export interface DashboardEconomies {
  ce_mois: number;
  cumul_annee: number;
  graphique_30j: DayPoint[];
}

export interface DashboardStats {
  tickets_scannes: number;
  produits_suivis: number;
  magasin_prefere: string | null;
  score_econome: number;
}

export interface DashboardAlerte {
  alert_id: number;
  product_id: number;
  product_name: string;
  product_image: string | null;
  target_price: number;
  current_price: number | null;
  current_store: string | null;
  is_triggered: boolean;
}

export interface DashboardResponse {
  user_id: number;
  generated_at: string;
  economies: DashboardEconomies;
  statistiques: DashboardStats;
  alertes_actives: DashboardAlerte[];
  prochaine_liste: {
    list_type: string;
    total_estimated: number;
    item_count: number;
    top_items: GeneratedListItem[];
    fallback_mode: boolean;
  } | null;
  magasin_conseille: {
    store_id: number;
    nom: string;
    ville: string | null;
    distance: string | null;
    economie_estimee: number;
    nb_promos_pertinentes: number;
  } | null;
}

// ─── Pagination ───────────────────────────────────────────────────────────────

export interface PageMeta {
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export interface Paginated<T> {
  data: T[];
  meta: PageMeta;
}

// ─── Navigation params ────────────────────────────────────────────────────────

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
};

export type MainTabParamList = {
  Accueil: undefined;
  Scanner: undefined;
  Comparer: undefined;
  Listes: undefined;
  Profil: undefined;
};

export type AccueilStackParamList = {
  Dashboard: undefined;
  ProduitDetail: { productId: number; productName: string };
  Promotions: undefined;
  MagasinsProches: undefined;
  SoukPrices: undefined;
  Alertes: undefined;
};

// ─── Prix communautaires du souk ──────────────────────────────────────────────

export type SoukCategory = 'legumes' | 'fruits' | 'viande' | 'poisson';
export type SoukStatus = 'approved' | 'pending' | 'rejected';

export interface SoukPrice {
  id: number;
  user_id: number;
  contributor: string | null;
  item_name: string;
  category: SoukCategory;
  unit: string;
  price: number;
  currency: string;
  city: string;
  neighborhood: string | null;
  latitude: number | null;
  longitude: number | null;
  photo_url: string | null;
  note: string | null;
  status: SoukStatus;
  moderation_reason: string | null;
  upvotes: number;
  downvotes: number;
  my_vote: number | null;
  created_at: string;
}

export interface SoukMedianItem {
  item_name: string;
  category: SoukCategory;
  unit: string;
  median_price: number;
  min_price: number;
  max_price: number;
  sample_count: number;
  city: string;
  last_updated: string | null;
}

export interface SoukCategoryInfo {
  value: SoukCategory;
  label: string;
  icon: string;
  suggestions: string[];
}

export interface SoukPriceCreate {
  item_name: string;
  category: SoukCategory;
  price: number;
  unit?: string;
  city: string;
  neighborhood?: string;
  note?: string;
}

export type ComparerStackParamList = {
  Recherche: { query?: string };
  ProduitDetail: { productId: number; productName: string };
  ComparerPrix: { productIds: number[] };
  HistoriquePrix: { productId: number; productName: string };
};

export type ListesStackParamList = {
  MesListes: undefined;
  DetailListe: { listId: number; listName: string };
  NouvelleListeIA: undefined;
};

export type ProfilStackParamList = {
  MonProfil: undefined;
  MesScans: undefined;
  MesAlertes: undefined;
  Parametres: undefined;
};
