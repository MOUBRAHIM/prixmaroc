import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  getProducts, deleteProduct, patchProduct,
  searchOpenFoodFacts, importCsvProducts,
  uploadProductPhoto, getProductsWithoutPhotos,
} from '../api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Product {
  id: number;
  name: string;
  brand: string | null;
  barcode: string | null;
  category: { name: string } | null;
  lowest_price: number | null;
  store_count: number;
  image_url: string | null;
  nutriscore?: string | null;
  calories?: number | null;
  proteins?: number | null;
  lipids?: number | null;
  carbs?: number | null;
  fibers?: number | null;
}

interface OffSuggestion {
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
}

// ── Nutri-Score badge ─────────────────────────────────────────────────────────

const NS_COLORS: Record<string, string> = {
  A: 'bg-green-700', B: 'bg-green-500', C: 'bg-yellow-400',
  D: 'bg-orange-500', E: 'bg-red-600',
};

const NutriBadge = ({ score }: { score: string }) => (
  <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-white text-xs font-black ${NS_COLORS[score.toUpperCase()] ?? 'bg-gray-400'}`}>
    {score.toUpperCase()}
  </span>
);

// ── Modal d'édition ───────────────────────────────────────────────────────────

interface EditModalProps {
  product: Product;
  onClose: () => void;
  onSaved: () => void;
}

function EditModal({ product, onClose, onSaved }: EditModalProps) {
  const [form, setForm] = useState({
    name: product.name,
    brand: product.brand ?? '',
    image_url: product.image_url ?? '',
    nutriscore: product.nutriscore ?? '',
    calories: product.calories != null ? String(product.calories) : '',
    proteins: product.proteins != null ? String(product.proteins) : '',
    lipids: product.lipids != null ? String(product.lipids) : '',
    carbs: product.carbs != null ? String(product.carbs) : '',
    fibers: product.fibers != null ? String(product.fibers) : '',
  });

  const [offQuery, setOffQuery] = useState('');
  const [offResults, setOffResults] = useState<OffSuggestion[]>([]);
  const [offLoading, setOffLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const offTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  // Debounced Open Food Facts search
  useEffect(() => {
    if (offTimerRef.current) clearTimeout(offTimerRef.current);
    if (offQuery.length < 2) { setOffResults([]); return; }
    offTimerRef.current = setTimeout(async () => {
      setOffLoading(true);
      try {
        const results = await searchOpenFoodFacts(offQuery);
        setOffResults(results);
      } catch {
        setOffResults([]);
      } finally {
        setOffLoading(false);
      }
    }, 500);
    return () => { if (offTimerRef.current) clearTimeout(offTimerRef.current); };
  }, [offQuery]);

  const applyOff = (s: OffSuggestion) => {
    setForm((f) => ({
      ...f,
      name: s.name || f.name,
      brand: s.brand ?? f.brand,
      image_url: s.image_url ?? f.image_url,
      nutriscore: s.nutriscore ?? f.nutriscore,
      calories: s.calories != null ? String(s.calories) : f.calories,
      proteins: s.proteins != null ? String(s.proteins) : f.proteins,
      lipids: s.lipids != null ? String(s.lipids) : f.lipids,
      carbs: s.carbs != null ? String(s.carbs) : f.carbs,
      fibers: s.fibers != null ? String(s.fibers) : f.fibers,
    }));
    setOffResults([]);
    setOffQuery('');
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Le nom est requis'); return; }
    setSaving(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        brand: form.brand.trim() || null,
        image_url: form.image_url.trim() || null,
        nutriscore: form.nutriscore.trim().toUpperCase().slice(0, 1) || null,
        calories: form.calories ? parseFloat(form.calories) : null,
        proteins: form.proteins ? parseFloat(form.proteins) : null,
        lipids: form.lipids ? parseFloat(form.lipids) : null,
        carbs: form.carbs ? parseFloat(form.carbs) : null,
        fibers: form.fibers ? parseFloat(form.fibers) : null,
      };
      await patchProduct(product.id, payload);
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const Field = ({
    label, name, type = 'text', placeholder,
  }: { label: string; name: string; type?: string; placeholder?: string }) => (
    <div>
      <label className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>
      <input
        type={type}
        value={(form as any)[name]}
        onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
      />
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div>
            <h3 className="text-lg font-black text-gray-900">Modifier le produit</h3>
            <p className="text-xs text-gray-400 mt-0.5">ID #{product.id} · {product.barcode ?? 'Sans code-barres'}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Open Food Facts autocomplete */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              🔍 Rechercher sur Open Food Facts (auto-remplissage)
            </label>
            <div className="relative">
              <input
                type="text"
                value={offQuery}
                onChange={(e) => setOffQuery(e.target.value)}
                placeholder="Nom du produit, marque…"
                className="w-full px-3 py-2 border border-blue-200 bg-blue-50 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              {offLoading && (
                <div className="absolute right-3 top-2.5 w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
              )}
            </div>
            {offResults.length > 0 && (
              <div className="mt-1 border border-gray-200 rounded-xl overflow-hidden shadow-lg z-10 relative bg-white">
                {offResults.map((r, i) => (
                  <button
                    key={i}
                    onClick={() => applyOff(r)}
                    className="flex items-center gap-3 w-full px-4 py-2.5 hover:bg-blue-50 text-left border-b border-gray-50 last:border-0 transition-colors"
                  >
                    {r.image_url && (
                      <img src={r.image_url} alt="" className="w-8 h-8 rounded object-cover shrink-0 bg-gray-100" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 truncate">{r.name}</p>
                      <p className="text-xs text-gray-500">{r.brand ?? '—'} · {r.barcode ?? '—'}</p>
                    </div>
                    {r.nutriscore && <NutriBadge score={r.nutriscore} />}
                    <span className="text-xs text-blue-600 font-semibold shrink-0">Appliquer →</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Aperçu photo */}
          {form.image_url && (
            <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-xl border border-gray-100">
              <img
                src={form.image_url}
                alt=""
                className="w-16 h-16 object-contain rounded-lg bg-white border border-gray-100"
                onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
              />
              <p className="text-xs text-gray-500 break-all">{form.image_url}</p>
            </div>
          )}

          {/* Champs principaux */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Field label="Nom du produit *" name="name" placeholder="Ex: Lait Centrale 1L" />
            </div>
            <Field label="Marque" name="brand" placeholder="Ex: Centrale Danone" />
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Nutri-Score</label>
              <div className="flex gap-2">
                {['A', 'B', 'C', 'D', 'E'].map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, nutriscore: f.nutriscore === g ? '' : g }))}
                    className={`w-9 h-9 rounded-lg font-black text-sm transition-all ${
                      form.nutriscore?.toUpperCase() === g
                        ? `${NS_COLORS[g]} text-white scale-110 shadow-md`
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">URL de la photo</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.image_url}
                  onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))}
                  placeholder="https://… ou uploader un fichier →"
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    setUploading(true);
                    setError('');
                    try {
                      const res = await uploadProductPhoto(product.id, f);
                      setForm((prev) => ({ ...prev, image_url: res.image_url }));
                    } catch (err: any) {
                      setError(err.response?.data?.detail ?? 'Erreur upload photo');
                    } finally {
                      setUploading(false);
                      if (photoInputRef.current) photoInputRef.current.value = '';
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={() => photoInputRef.current?.click()}
                  disabled={uploading}
                  className="px-3 py-2 bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 text-xs font-bold rounded-lg disabled:opacity-50 whitespace-nowrap flex items-center gap-1.5"
                >
                  {uploading ? (
                    <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin inline-block" />
                  ) : (
                    '📷'
                  )}
                  {uploading ? 'Upload…' : 'Uploader'}
                </button>
              </div>
            </div>

          {/* Nutrition */}
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">Valeurs nutritionnelles (pour 100g)</p>
            <div className="grid grid-cols-5 gap-2">
              {[
                { label: 'Calories (kcal)', name: 'calories' },
                { label: 'Protéines (g)', name: 'proteins' },
                { label: 'Lipides (g)', name: 'lipids' },
                { label: 'Glucides (g)', name: 'carbs' },
                { label: 'Fibres (g)', name: 'fibers' },
              ].map(({ label, name }) => (
                <div key={name}>
                  <label className="block text-[10px] text-gray-500 mb-1">{label}</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={(form as any)[name]}
                    onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
                    className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm text-center focus:outline-none focus:ring-2 focus:ring-green-400"
                    placeholder="—"
                  />
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button
            onClick={onClose}
            className="px-5 py-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl transition-colors flex items-center gap-2"
          >
            {saving ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Sauvegarde…
              </>
            ) : (
              '✓ Sauvegarder'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Modal Import CSV ──────────────────────────────────────────────────────────

function CsvImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [updateExisting, setUpdateExisting] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    inserted: number; updated: number; skipped: number; errors: string[]
  } | null>(null);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const res = await importCsvProducts(file, updateExisting);
      setResult(res);
      onDone();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Erreur lors de l\'import');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div>
            <h3 className="text-lg font-black text-gray-900">Import CSV</h3>
            <p className="text-xs text-gray-400 mt-0.5">Importer des produits en masse</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Format attendu */}
          <div className="bg-gray-50 rounded-xl p-4 text-xs font-mono text-gray-600 border border-gray-200">
            <p className="font-bold text-gray-700 mb-2 not-italic font-sans">Colonnes acceptées :</p>
            <p className="text-green-700 font-bold">name</p>
            <p className="text-gray-500">brand, barcode, category, unit_size, image_url</p>
            <p className="text-blue-600">nutriscore, calories, proteins, lipids, carbs, fibers</p>
          </div>

          {/* Zone upload */}
          <div
            onClick={() => fileRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              file ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-green-400 hover:bg-gray-50'
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <p className="text-2xl mb-2">{file ? '📄' : '📁'}</p>
            {file ? (
              <>
                <p className="font-bold text-green-700 text-sm">{file.name}</p>
                <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
              </>
            ) : (
              <>
                <p className="font-semibold text-gray-700 text-sm">Cliquer pour sélectionner</p>
                <p className="text-xs text-gray-400 mt-1">Fichier CSV, encodage UTF-8</p>
              </>
            )}
          </div>

          {/* Options */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={updateExisting}
              onChange={(e) => setUpdateExisting(e.target.checked)}
              className="w-4 h-4 rounded accent-green-600"
            />
            <span className="text-sm text-gray-700">
              Mettre à jour les produits existants (par code-barres)
            </span>
          </label>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Résultat */}
          {result && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-2">
              <p className="font-bold text-green-800 text-sm">Import terminé !</p>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-white rounded-lg p-2 border border-green-100">
                  <p className="text-xl font-black text-green-700">{result.inserted}</p>
                  <p className="text-xs text-gray-500">Insérés</p>
                </div>
                <div className="bg-white rounded-lg p-2 border border-green-100">
                  <p className="text-xl font-black text-blue-700">{result.updated}</p>
                  <p className="text-xs text-gray-500">Mis à jour</p>
                </div>
                <div className="bg-white rounded-lg p-2 border border-green-100">
                  <p className="text-xl font-black text-gray-500">{result.skipped}</p>
                  <p className="text-xs text-gray-500">Ignorés</p>
                </div>
              </div>
              {result.errors.length > 0 && (
                <div className="bg-red-50 rounded-lg p-2 mt-2">
                  <p className="text-xs font-bold text-red-700 mb-1">{result.errors.length} erreur(s) :</p>
                  {result.errors.slice(0, 5).map((e, i) => (
                    <p key={i} className="text-xs text-red-600">{e}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button onClick={onClose} className="px-5 py-2 text-sm font-semibold text-gray-600 hover:text-gray-900">
            {result ? 'Fermer' : 'Annuler'}
          </button>
          {!result && (
            <button
              onClick={handleImport}
              disabled={!file || loading}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl flex items-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Import en cours…
                </>
              ) : (
                '⬆ Importer'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [showCsvModal, setShowCsvModal] = useState(false);
  const [withoutPhotosMode, setWithoutPhotosMode] = useState(false);
  const [withoutPhotosTotal, setWithoutPhotosTotal] = useState<number | null>(null);
  const LIMIT = 50;

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      if (withoutPhotosMode) {
        const data = await getProductsWithoutPhotos(page * LIMIT, LIMIT);
        // Adapt to Product type (fields may differ)
        setProducts(data.products.map((p: any) => ({
          id: p.id, name: p.name, brand: p.brand, barcode: p.barcode,
          category: null, lowest_price: null, store_count: 0, image_url: null,
        })));
        setTotal(data.total);
        setWithoutPhotosTotal(data.total);
      } else {
        const data = await getProducts(page * LIMIT, LIMIT, search || undefined);
        setProducts(data.data ?? data);
        setTotal(data.meta?.total ?? data.length ?? 0);
      }
    } catch {
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }, [page, search, withoutPhotosMode]);

  useEffect(() => {
    const t = setTimeout(fetchProducts, 300);
    return () => clearTimeout(t);
  }, [fetchProducts]);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Supprimer le produit « ${name} » ?`)) return;
    await deleteProduct(id);
    fetchProducts();
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-black text-gray-900">Produits</h2>
          <p className="text-gray-500 mt-1">{total.toLocaleString('fr-MA')} produits en base</p>
        </div>
        <div className="flex items-center gap-3">
          {!withoutPhotosMode && (
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="Rechercher un produit…"
              className="px-4 py-2.5 border border-gray-200 rounded-xl text-sm w-60 focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          )}
          <button
            onClick={() => { setWithoutPhotosMode((v) => !v); setPage(0); }}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-bold rounded-xl transition-colors ${
              withoutPhotosMode
                ? 'bg-amber-500 hover:bg-amber-600 text-white'
                : 'bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200'
            }`}
          >
            📷 Sans photo
            {withoutPhotosTotal !== null && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-black ${
                withoutPhotosMode ? 'bg-white/25 text-white' : 'bg-amber-200 text-amber-800'
              }`}>
                {withoutPhotosTotal}
              </span>
            )}
          </button>
          <button
            onClick={() => setShowCsvModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors"
          >
            ⬆ Import CSV
          </button>
        </div>
      </div>

      {/* Tableau */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Produit</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Marque</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Catégorie</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Nutri</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Cal.</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Prix min</th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Magasins</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {products.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors group">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {p.image_url ? (
                          <img
                            src={p.image_url}
                            alt=""
                            className="w-9 h-9 rounded-lg object-cover bg-gray-100 border border-gray-100"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center text-gray-300 text-base">
                            📦
                          </div>
                        )}
                        <div>
                          <span className="font-medium text-gray-900 line-clamp-1">{p.name}</span>
                          {p.barcode && (
                            <span className="text-[10px] text-gray-400 font-mono">{p.barcode}</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{p.brand ?? '—'}</td>
                    <td className="px-4 py-3">
                      {p.category ? (
                        <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded-full text-xs font-medium">
                          {p.category.name}
                        </span>
                      ) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {p.nutriscore ? <NutriBadge score={p.nutriscore} /> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {p.calories != null ? `${p.calories} kcal` : '—'}
                    </td>
                    <td className="px-4 py-3 font-semibold text-green-700">
                      {p.lowest_price != null ? `${p.lowest_price.toFixed(2)} MAD` : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{p.store_count}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => setEditProduct(p)}
                          className="text-blue-600 hover:text-blue-800 text-xs font-semibold px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
                        >
                          ✏ Éditer
                        </button>
                        <button
                          onClick={() => handleDelete(p.id, p.name)}
                          className="text-red-500 hover:text-red-700 text-xs font-semibold px-2 py-1 rounded-lg hover:bg-red-50 transition-colors"
                        >
                          🗑 Supp.
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {products.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-16 text-gray-400">
                      Aucun produit trouvé
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-500">
              {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} sur {total.toLocaleString('fr-MA')}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 text-sm font-semibold border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                ← Précédent
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * LIMIT >= total}
                className="px-3 py-1.5 text-sm font-semibold border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                Suivant →
              </button>
            </div>
          </div>
        </>
      )}

      {/* Modals */}
      {editProduct && (
        <EditModal
          product={editProduct}
          onClose={() => setEditProduct(null)}
          onSaved={fetchProducts}
        />
      )}
      {showCsvModal && (
        <CsvImportModal
          onClose={() => setShowCsvModal(false)}
          onDone={fetchProducts}
        />
      )}
    </div>
  );
}
