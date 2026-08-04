/**
 * Service API — PrixMaroc
 * axios + interceptors JWT (auto-attach token, 401 → logout, retry)
 */
import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import * as SecureStore from './secureStorage';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL, STORAGE_KEYS } from '@constants/index';
import type {
  CheapestResponse,
  DashboardResponse,
  GeneratedList,
  ListType,
  OcrScan,
  Paginated,
  PriceAlert,
  PriceHistory,
  PromoAlert,
  PromoItem,
  ProductDetail,
  ProductSummary,
  ShoppingList,
  StoreNearby,
  Token,
  User,
  UserCreate,
  SoukPrice,
  SoukMedianItem,
  SoukCategoryInfo,
  SoukCategory,
  SoukPriceCreate,
} from '@types/models';

// ─── URL dynamique ────────────────────────────────────────────────────────────

export const API_URL_STORAGE_KEY = 'prixmaroc:api_url';

/** Retourne l'URL de base stockée, ou la valeur par défaut */
export async function getStoredApiUrl(): Promise<string> {
  try {
    const stored = await AsyncStorage.getItem(API_URL_STORAGE_KEY);
    return stored && stored.trim() ? stored.trim() : API_BASE_URL;
  } catch {
    return API_BASE_URL;
  }
}

/** Met à jour l'URL de base en live */
export async function setApiUrl(url: string): Promise<void> {
  const cleaned = url.trim().replace(/\/$/, '');
  await AsyncStorage.setItem(API_URL_STORAGE_KEY, cleaned);
  api.defaults.baseURL = cleaned;
}

/** Initialise l'URL au démarrage */
export async function initApiUrl(): Promise<void> {
  const url = await getStoredApiUrl();
  api.defaults.baseURL = url;
}

// ─── Instance axios ───────────────────────────────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// ─── Interceptor Request : attach JWT ────────────────────────────────────────

api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await SecureStore.getItemAsync(STORAGE_KEYS.accessToken);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ─── Interceptor Response : gestion 401 + refresh ────────────────────────────

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Si la requête n'avait pas de token (mode invité), ne pas déconnecter
      const sentToken = (originalRequest.headers as Record<string, string>)?.['Authorization'];
      if (!sentToken) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (originalRequest.headers && token) {
            originalRequest.headers['Authorization'] = `Bearer ${token}`;
          }
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      // Pas de refresh token dans ce backend — on déconnecte proprement
      await SecureStore.deleteItemAsync(STORAGE_KEYS.accessToken);
      await SecureStore.deleteItemAsync(STORAGE_KEYS.user);
      processQueue(error, null);
      isRefreshing = false;

      // Émet un événement pour que le store Zustand redirige vers Login
      authEventEmitter.emit('unauthorized');
    }

    return Promise.reject(error);
  },
);

// ─── EventEmitter minimaliste pour la navigation ──────────────────────────────

type AuthEvent = 'unauthorized';
type Listener = () => void;

export const authEventEmitter = {
  listeners: new Map<AuthEvent, Listener[]>(),
  emit(event: AuthEvent) {
    (this.listeners.get(event) || []).forEach((l) => l());
  },
  on(event: AuthEvent, listener: Listener) {
    const existing = this.listeners.get(event) || [];
    this.listeners.set(event, [...existing, listener]);
    return () => {
      const updated = (this.listeners.get(event) || []).filter((l) => l !== listener);
      this.listeners.set(event, updated);
    };
  },
};

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const AuthAPI = {
  login: async (username: string, password: string): Promise<Token> => {
    const body = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`;
    const { data } = await api.post<Token>('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return data;
  },

  register: async (payload: UserCreate): Promise<User> => {
    const { data } = await api.post<User>('/auth/register', payload);
    return data;
  },

  me: async (): Promise<User> => {
    const { data } = await api.get<User>('/utilisateurs/me');
    return data;
  },

  updateMe: async (payload: Partial<UserCreate>): Promise<User> => {
    const { data } = await api.put<User>('/utilisateurs/me', payload);
    return data;
  },
};

// ─── Dashboard ────────────────────────────────────────────────────────────────

export const DashboardAPI = {
  get: async (): Promise<DashboardResponse> => {
    const { data } = await api.get<DashboardResponse>('/api/dashboard');
    return data;
  },
};

// ─── Produits ─────────────────────────────────────────────────────────────────

export const ProductsAPI = {
  search: async (params: {
    q?: string;
    category_id?: number;
    city?: string;
    brand?: string;
    skip?: number;
    limit?: number;
  }): Promise<Paginated<ProductSummary>> => {
    const { data } = await api.get<Paginated<ProductSummary>>('/api/products', { params });
    return data;
  },

  getDetail: async (id: number): Promise<ProductDetail> => {
    const { data } = await api.get<ProductDetail>(`/api/products/${id}`);
    return data;
  },

  getPriceHistory: async (id: number, days: 30 | 90 = 30): Promise<PriceHistory> => {
    const { data } = await api.get<PriceHistory>(`/api/products/${id}/price-history`, {
      params: { days },
    });
    return data;
  },

  compare: async (ids: number[]) => {
    const { data } = await api.get('/api/products/compare', {
      params: { ids: ids.join(',') },
    });
    return data;
  },
};

// ─── Prix ─────────────────────────────────────────────────────────────────────

export const PricesAPI = {
  getCheapest: async (productId: number, city?: string): Promise<CheapestResponse> => {
    const { data } = await api.get<CheapestResponse>('/api/prices/cheapest', {
      params: { product_id: productId, city },
    });
    return data;
  },

  getPromos: async (params?: { city?: string; limit?: number }): Promise<{ promotions: PromoItem[]; count: number }> => {
    const { data } = await api.get('/api/prices/promotions', { params });
    return data;
  },
};

// ─── Magasins ─────────────────────────────────────────────────────────────────

export const StoresAPI = {
  getNearby: async (lat: number, lng: number, radius = 5): Promise<StoreNearby[]> => {
    const { data } = await api.get<StoreNearby[]>('/api/stores/nearby', {
      params: { lat, lng, radius },
    });
    return data;
  },

  getProducts: async (storeId: number, params?: { skip?: number; limit?: number; search?: string }) => {
    const { data } = await api.get(`/api/stores/${storeId}/products`, { params });
    return data;
  },

  optimizeRoute: async (storeIds: number[], productIds?: number[]) => {
    const { data } = await api.get('/api/stores/route-optimize', {
      params: {
        store_ids: storeIds.join(','),
        product_ids: productIds?.join(','),
      },
    });
    return data;
  },
};

// ─── IA ───────────────────────────────────────────────────────────────────────

export const IAAPI = {
  generateList: async (params: {
    list_type: ListType;
    budget_max?: number;
    household_size?: number;
  }): Promise<GeneratedList> => {
    const { data } = await api.post<GeneratedList>('/api/ai/generate-list', params);
    return data;
  },

  getHabits: async (windowDays = 90) => {
    const { data } = await api.get('/api/ai/habits', {
      params: { window_days: windowDays },
    });
    return data;
  },

  getPromoAlerts: async (threshold = 0.15): Promise<PromoAlert[]> => {
    const { data } = await api.get<PromoAlert[]>('/api/ai/promo-alerts', {
      params: { threshold },
    });
    return data;
  },
};

// ─── Souk (prix communautaires) ───────────────────────────────────────────────

export const SoukAPI = {
  getCategories: async (): Promise<SoukCategoryInfo[]> => {
    const { data } = await api.get<SoukCategoryInfo[]>('/api/souk/categories');
    return data;
  },

  list: async (params?: {
    city?: string;
    category?: SoukCategory;
    item_name?: string;
    include_pending?: boolean;
    limit?: number;
  }): Promise<SoukPrice[]> => {
    const { data } = await api.get<SoukPrice[]>('/api/souk/prices', { params });
    return data;
  },

  median: async (city: string, category?: SoukCategory): Promise<SoukMedianItem[]> => {
    const { data } = await api.get<SoukMedianItem[]>('/api/souk/median', {
      params: { city, category },
    });
    return data;
  },

  submit: async (payload: SoukPriceCreate): Promise<SoukPrice> => {
    const { data } = await api.post<SoukPrice>('/api/souk/prices', payload);
    return data;
  },

  vote: async (priceId: number, value: 1 | -1): Promise<SoukPrice> => {
    const { data } = await api.post<SoukPrice>(`/api/souk/prices/${priceId}/vote`, { value });
    return data;
  },
};

// ─── OCR ──────────────────────────────────────────────────────────────────────

export const OcrAPI = {
  scan: async (imageUri: string): Promise<OcrScan> => {
    const form = new FormData();
    form.append('file', {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'receipt.jpg',
    } as unknown as Blob);
    const { data } = await api.post<OcrScan>('/ocr/scan', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60_000,
    });
    return data;
  },

  getScans: async (): Promise<OcrScan[]> => {
    const { data } = await api.get<OcrScan[]>('/ocr/scans');
    return data;
  },

  /**
   * Confirme un scan OCR et enregistre les prix détectés en base de données.
   * Les prix du ticket corrigent/complètent les données scraping pour ce magasin.
   * Si `corrections` est fourni, les items corrigés par l'utilisateur sont utilisés
   * à la place des résultats bruts de l'OCR.
   */
  confirm: async (
    scanId: number,
    storeId?: number,
    corrections?: Array<{ name: string; quantity: number; unit_price: number; total_price: number; is_promo?: boolean }>,
  ): Promise<{ status: string; store_id: number | null; prices_saved: number; message: string }> => {
    const body: Record<string, unknown> = {};
    if (storeId) body.store_id = storeId;
    if (corrections && corrections.length > 0) body.corrections = corrections;
    const { data } = await api.post(`/ocr/confirm/${scanId}`, body);
    return data;
  },
};

// ─── Listes de courses ────────────────────────────────────────────────────────

export const ListsAPI = {
  getAll: async (): Promise<ShoppingList[]> => {
    const { data } = await api.get<ShoppingList[]>('/listes');
    return data;
  },

  getOne: async (id: number): Promise<ShoppingList> => {
    const { data } = await api.get<ShoppingList>(`/listes/${id}`);
    return data;
  },

  create: async (payload: { name: string; description?: string }): Promise<ShoppingList> => {
    const { data } = await api.post<ShoppingList>('/listes', payload);
    return data;
  },

  addItem: async (listId: number, payload: { product_id?: number; custom_name?: string; quantity: number }) => {
    const { data } = await api.post(`/listes/${listId}/items`, payload);
    return data;
  },

  toggleItem: async (listId: number, itemId: number, isChecked: boolean) => {
    const { data } = await api.patch(`/listes/${listId}/items/${itemId}`, { is_checked: isChecked });
    return data;
  },

  updateItemQty: async (listId: number, itemId: number, quantity: number) => {
    const { data } = await api.patch(`/listes/${listId}/items/${itemId}`, { quantity });
    return data;
  },

  deleteItem: async (listId: number, itemId: number): Promise<void> => {
    await api.delete(`/listes/${listId}/items/${itemId}`);
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/listes/${id}`);
  },
};

// ─── Alertes prix ─────────────────────────────────────────────────────────────

export const AlertsAPI = {
  getAll: async (): Promise<PriceAlert[]> => {
    const { data } = await api.get<PriceAlert[]>('/prix/alertes');
    return data;
  },

  create: async (payload: { product_id: number; target_price: number; store_id?: number }): Promise<PriceAlert> => {
    const { data } = await api.post<PriceAlert>('/prix/alertes', payload);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/prix/alertes/${id}`);
  },
};

// ─── Notifications push ───────────────────────────────────────────────────────

export const NotificationsAPI = {
  register: async (fcmToken: string, platform: string = 'android'): Promise<void> => {
    await api.post('/api/notifications/register', { fcm_token: fcmToken, platform });
  },

  unregister: async (): Promise<void> => {
    await api.delete('/api/notifications/register');
  },
};

// ─── Profil étendu ────────────────────────────────────────────────────────────

// ─── Admin scraper ────────────────────────────────────────────────────────────

export const AdminAPI = {
  getScraperStatus: async (): Promise<Record<string, { status: string; last_run: string | null; products_found: number }>> => {
    const { data } = await api.get('/admin/scrapers/status');
    return data;
  },
  triggerScraper: async (slug: string): Promise<{ message: string }> => {
    const { data } = await api.post(`/admin/scrapers/${slug}/trigger`);
    return data;
  },
};

export const ProfileAPI = {
  getStats: async (): Promise<{ scans: number; listes: number; economies: number }> => {
    const { data } = await api.get('/utilisateurs/me/stats');
    return data;
  },

  uploadAvatar: async (imageUri: string): Promise<{ avatar_url: string }> => {
    const form = new FormData();
    form.append('file', {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'avatar.jpg',
    } as unknown as Blob);
    const { data } = await api.post<{ avatar_url: string }>('/utilisateurs/me/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

export default api;
