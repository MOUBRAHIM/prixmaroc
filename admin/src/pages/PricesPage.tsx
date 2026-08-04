import React, { useEffect, useRef, useState } from 'react';
import { getAdminPrices, importCsvPrices, patchAdminPrice, deleteAdminPrice } from '../api';

const CSV_EXAMPLE = `product_name,store_name,city,price,is_promo
Lait Centrale 1L,Marjane,Casablanca,8.50,false
Eau Sidi Ali 1.5L,BIM,Rabat,4.00,false
Huile Lesieur 1L,Carrefour,Marrakech,29.90,true`;

type PriceItem = {
  id: number;
  price: number;
  is_promo: boolean;
  source: string;
  recorded_at: string;
  product_name: string;
  store_name: string;
  store_city: string | null;
};

export default function PricesPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [prices, setPrices] = useState<PriceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editPrice, setEditPrice] = useState('');

  // Import
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ inserted: number; updated: number; skipped: number; errors: string[] } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [showExample, setShowExample] = useState(false);

  const LIMIT = 50;

  const load = async (p = page, src = sourceFilter) => {
    setLoading(true);
    try {
      const res = await getAdminPrices(p, LIMIT, undefined, undefined, src || undefined);
      setPrices(res.items as PriceItem[]);
      setTotal(res.total);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [page, sourceFilter]);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    setImportError(null);
    try {
      const res = await importCsvPrices(file);
      setImportResult(res);
      setPage(1);
      load(1, sourceFilter);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur d'import";
      setImportError(msg);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Supprimer ce prix définitivement ?')) return;
    await deleteAdminPrice(id);
    load();
  };

  const handleSaveEdit = async (id: number) => {
    const val = parseFloat(editPrice.replace(',', '.'));
    if (isNaN(val) || val <= 0) { alert('Prix invalide'); return; }
    await patchAdminPrice(id, { price: val });
    setEditingId(null);
    load();
  };

  // Anomaly detection
  const median = prices.length > 0
    ? [...prices].sort((a, b) => a.price - b.price)[Math.floor(prices.length / 2)]?.price ?? 0
    : 0;
  const isAnomaly = (p: number) => p <= 0 || (median > 0 && p > median * 3);

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-black text-gray-900">💰 Prix</h2>
          <p className="text-gray-500 mt-1">{total.toLocaleString()} prix en base</p>
        </div>
        <div className="flex gap-2">
          {(['', 'manual', 'scraper', 'ocr', 'ai'] as const).map(s => (
            <button key={s}
              onClick={() => { setSourceFilter(s); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${sourceFilter === s ? 'bg-green-600 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'}`}
            >
              {s === '' ? 'Tous' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* CSV Import */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mb-6">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="font-bold text-gray-800">📤 Import CSV de prix</h3>
          <button
            onClick={() => setShowExample(v => !v)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showExample ? 'Masquer exemple' : 'Voir format CSV'}
          </button>
        </div>

        {showExample && (
          <pre className="bg-gray-50 rounded-xl border border-gray-100 p-3 text-xs mb-3 overflow-x-auto leading-relaxed text-gray-700">
            {CSV_EXAMPLE}
          </pre>
        )}

        <p className="text-xs text-gray-500 mb-3">
          Colonnes : <code className="bg-gray-100 px-1 rounded">product_name*</code>{' '}
          <code className="bg-gray-100 px-1 rounded">store_name</code>{' '}
          <code className="bg-gray-100 px-1 rounded">city</code>{' '}
          <code className="bg-gray-100 px-1 rounded">price*</code>{' '}
          <code className="bg-gray-100 px-1 rounded">is_promo</code>{' '}
          <code className="bg-gray-100 px-1 rounded">barcode</code>
          {' — '}séparateur <strong>virgule</strong> ou <strong>point-virgule</strong>
        </p>

        <div className="flex items-center gap-3">
          <label
            htmlFor="csv-prices-input"
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold text-white cursor-pointer transition-colors ${importing ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'}`}
          >
            {importing ? '⏳ Import…' : '📂 Choisir fichier CSV'}
          </label>
          <input
            ref={fileRef}
            id="csv-prices-input"
            type="file"
            accept=".csv"
            onChange={handleImport}
            disabled={importing}
            className="hidden"
          />
        </div>

        {importResult && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-xl p-4">
            <div className="font-bold text-green-700 mb-2">✅ Import terminé</div>
            <div className="flex gap-5 text-sm text-gray-700">
              <span>🆕 Insérés : <strong>{importResult.inserted}</strong></span>
              <span>🔄 Mis à jour : <strong>{importResult.updated}</strong></span>
              <span>⏭ Ignorés : <strong>{importResult.skipped}</strong></span>
            </div>
            {importResult.errors.length > 0 && (
              <details className="mt-3">
                <summary className="cursor-pointer text-red-600 text-sm font-semibold">
                  ⚠ {importResult.errors.length} erreur(s)
                </summary>
                <ul className="mt-2 ml-4 text-xs text-red-800 space-y-0.5">
                  {importResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </details>
            )}
          </div>
        )}

        {importError && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
            ❌ {importError}
          </div>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['Produit', 'Magasin', 'Ville', 'Prix', 'Source', 'Date', '⚠', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {prices.map((p) => {
                const anomaly = isAnomaly(p.price);
                return (
                  <tr key={p.id} className={`hover:bg-gray-50 transition-colors ${anomaly ? 'bg-red-50' : ''}`}>
                    <td className="px-4 py-3 font-medium text-gray-900 max-w-[200px]">
                      <span className="block truncate" title={p.product_name}>{p.product_name}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{p.store_name}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{p.store_city ?? '—'}</td>
                    <td className="px-4 py-3 font-bold">
                      {editingId === p.id ? (
                        <div className="flex items-center gap-1.5">
                          <input
                            type="number"
                            value={editPrice}
                            onChange={e => setEditPrice(e.target.value)}
                            className="w-20 border border-gray-300 rounded-lg px-2 py-1 text-sm"
                          />
                          <button onClick={() => handleSaveEdit(p.id)} className="bg-green-600 text-white rounded-md px-2 py-1 text-xs font-bold">✓</button>
                          <button onClick={() => setEditingId(null)} className="bg-gray-100 text-gray-600 rounded-md px-2 py-1 text-xs">✗</button>
                        </div>
                      ) : (
                        <span className={p.is_promo ? 'text-orange-600' : 'text-green-700'}>
                          {Number(p.price).toFixed(2)} MAD
                          {p.is_promo && <span className="ml-1.5 px-1 py-0.5 bg-orange-100 text-orange-600 rounded text-xs font-semibold">PROMO</span>}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs font-medium">{p.source}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(p.recorded_at).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short', year: '2-digit' })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {anomaly && <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-xs font-bold">⚠</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5">
                        <button
                          title="Modifier"
                          onClick={() => { setEditingId(p.id); setEditPrice(String(p.price)); }}
                          className="p-1.5 bg-blue-50 text-blue-600 rounded-md hover:bg-blue-100 text-xs"
                        >
                          ✏
                        </button>
                        <button
                          title="Supprimer"
                          onClick={() => handleDelete(p.id)}
                          className="p-1.5 bg-red-50 text-red-500 rounded-md hover:bg-red-100 text-xs"
                        >
                          🗑
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {prices.length === 0 && (
            <div className="text-center py-12 text-gray-400">Aucun prix trouvé</div>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-3 mt-4">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            ← Précédent
          </button>
          <span className="flex items-center text-sm text-gray-500">Page {page} / {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Suivant →
          </button>
        </div>
      )}
    </div>
  );
}
