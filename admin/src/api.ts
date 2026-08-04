import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  timeout: 15_000,
});

// Attach token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token && config.headers) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

export default api;

// ── Auth ─────────────────────────────────────────────────────────────────────

export const login = async (username: string, password: string) => {
  const form = new URLSearchParams({ username, password });
  const { data } = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data as { access_token: string; token_type: string };
};

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const getDashboardStats = async () => {
  const [products, stores, prices] = await Promise.all([
    api.get('/api/products?limit=1'),
    api.get('/api/stores?limit=1'),
    api.get('/api/prices/promotions?limit=1'),
  ]);
  return {
    products: products.data?.meta?.total ?? '—',
    stores: stores.data?.meta?.total ?? stores.data?.length ?? '—',
    promos: prices.data?.count ?? '—',
  };
};

// ── Products ──────────────────────────────────────────────────────────────────

export const getProducts = async (skip = 0, limit = 50, search?: string) => {
  const { data } = await api.get('/api/products', { params: { skip, limit, search } });
  return data;
};

export const updateProduct = async (id: number, payload: Record<string, unknown>) => {
  const { data } = await api.put(`/produits/${id}`, payload);
  return data;
};

export const deleteProduct = async (id: number) => {
  await api.delete(`/produits/${id}`);
};

// ── Stores ────────────────────────────────────────────────────────────────────

export const getStores = async (skip = 0, limit = 50) => {
  const { data } = await api.get('/magasins', { params: { skip, limit } });
  return data;
};

// ── Scrapers ──────────────────────────────────────────────────────────────────

export const getScraperStatus = async () => {
  const { data } = await api.get('/admin/scrapers/status');
  return data;
};

export const triggerScraper = async (slug: string) => {
  const { data } = await api.post(`/admin/scrapers/${slug}/trigger`);
  return data;
};

export const getScraperLogs = async (slug: string, limit = 50) => {
  const { data } = await api.get(`/admin/scrapers/${slug}/logs`, { params: { limit } });
  return data;
};

// ── Admin Products ────────────────────────────────────────────────────────────

export const patchProduct = async (id: number, payload: Record<string, unknown>) => {
  const { data } = await api.patch(`/admin/products/${id}`, payload);
  return data;
};

export const searchOpenFoodFacts = async (q: string, limit = 8) => {
  const { data } = await api.get('/admin/products/openfoodfacts', { params: { q, limit } });
  return data as Array<{
    barcode: string | null;
    name: string;
    brand: string | null;
    nutriscore: string | null;
    image_url: string | null;
    calories: number | null;
    proteins: number | null;
    lipids: number | null;
    carbs: number | null;
    fibers: number | null;
  }>;
};

export const importCsvProducts = async (file: File, updateExisting = true) => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/admin/products/import-csv', form, {
    params: { update_existing: updateExisting },
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data as { inserted: number; updated: number; skipped: number; errors: string[] };
};

export const uploadProductPhoto = async (productId: number, file: File) => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(`/admin/products/${productId}/photo`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30_000,
  });
  return data as { product_id: number; image_url: string; size_bytes: number };
};

export const getProductsWithoutPhotos = async (skip = 0, limit = 50) => {
  const { data } = await api.get('/admin/products/without-photos', { params: { skip, limit } });
  return data as { total: number; skip: number; limit: number; products: Array<{ id: number; name: string; brand: string | null; barcode: string | null }> };
};

// WebSocket helper
export const getWsBase = () => {
  const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  return base.replace(/^http/, 'ws');
};

// ── Admin Stores ──────────────────────────────────────────────────────────────

export const triggerStoreUpdate = async (sources: string[] = ['osm', 'locator']) => {
  const { data } = await api.post('/admin/stores/update', { sources });
  return data as { status: string; message: string; sources: string[] };
};

export const getStoreUpdateStatus = async () => {
  const { data } = await api.get('/admin/stores/update/status');
  return data as {
    running: boolean;
    started_at: string | null;
    last_result: {
      status: string;
      fetched?: number;
      after_dedup?: number;
      inserted?: number;
      updated?: number;
      sources_ok?: string[];
      sources_failed?: string[];
      started_at?: string;
      finished_at?: string;
      warning?: string;
      error?: string;
    } | null;
  };
};

export const getAdminStores = async (skip = 0, limit = 50, search?: string, city?: string) => {
  const { data } = await api.get('/admin/stores', { params: { skip, limit, search, city } });
  return data as {
    total: number;
    skip: number;
    limit: number;
    stores: Array<{
      id: number;
      name: string;
      slug: string;
      city: string | null;
      region: string | null;
      address: string | null;
      latitude: number | null;
      longitude: number | null;
      phone: string | null;
      website: string | null;
      logo_url: string | null;
      is_active: boolean;
    }>;
  };
};

export const patchStore = async (id: number, payload: Record<string, unknown>) => {
  const { data } = await api.patch(`/admin/stores/${id}`, payload);
  return data;
};

export const deactivateStore = async (id: number) => {
  const { data } = await api.delete(`/admin/stores/${id}`);
  return data;
};

// ── Prices ────────────────────────────────────────────────────────────────────

export const getPrices = async (productId?: number, storeId?: number, limit = 50) => {
  const { data } = await api.get('/api/prices', {
    params: { product_id: productId, store_id: storeId, limit },
  });
  return data;
};

export const importCsvPrices = async (file: File) => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/admin/prices/import-csv', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  });
  return data as { inserted: number; updated: number; skipped: number; errors: string[] };
};

export const getAdminPrices = async (page = 1, limit = 50, productId?: number, storeId?: number, source?: string) => {
  const { data } = await api.get('/admin/prices', {
    params: { page, limit, product_id: productId, store_id: storeId, source },
  });
  return data as {
    total: number;
    page: number;
    limit: number;
    items: Array<{
      id: number;
      price: number;
      is_promo: boolean;
      source: string;
      recorded_at: string;
      product_name: string;
      store_name: string;
      store_city: string | null;
    }>;
  };
};

export const patchAdminPrice = async (id: number, payload: { price?: number; is_promo?: boolean }) => {
  const { data } = await api.patch(`/admin/prices/${id}`, payload);
  return data;
};

export const deleteAdminPrice = async (id: number) => {
  const { data } = await api.delete(`/admin/prices/${id}`);
  return data;
};
