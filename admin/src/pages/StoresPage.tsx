import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  triggerStoreUpdate,
  getStoreUpdateStatus,
  getAdminStores,
  deactivateStore,
} from '../api';

interface StoreRow {
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
}

interface UpdateStatus {
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
}

export default function StoresPage() {
  const [stores, setStores] = useState<StoreRow[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const LIMIT = 50;

  const [search, setSearch] = useState('');
  const [cityFilter, setCityFilter] = useState('');
  const [loading, setLoading] = useState(false);

  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>(['osm', 'locator']);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch stores ───────────────────────────────────────────────────────────

  const fetchStores = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAdminStores(skip, LIMIT, search || undefined, cityFilter || undefined);
      setStores(data.stores);
      setTotal(data.total);
    } catch {
      /* silently ignore */
    } finally {
      setLoading(false);
    }
  }, [skip, search, cityFilter]);

  useEffect(() => {
    fetchStores();
  }, [fetchStores]);

  // ── Poll update status ─────────────────────────────────────────────────────

  const fetchUpdateStatus = useCallback(async () => {
    try {
      const s = await getStoreUpdateStatus();
      setUpdateStatus(s);
      if (!s.running && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        fetchStores(); // Refresh after update completes
      }
    } catch {
      /* ignore */
    }
  }, [fetchStores]);

  useEffect(() => {
    fetchUpdateStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchUpdateStatus]);

  // ── Trigger update ────────────────────────────────────────────────────────

  const handleTriggerUpdate = async () => {
    setTriggering(true);
    try {
      await triggerStoreUpdate(selectedSources);
      // Start polling every 5s
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(fetchUpdateStatus, 5000);
      fetchUpdateStatus();
    } catch (err: any) {
      alert(`Erreur : ${err?.response?.data?.detail ?? err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  // ── Deactivate store ──────────────────────────────────────────────────────

  const handleDeactivate = async (store: StoreRow) => {
    if (!confirm(`Désactiver "${store.name}" ?`)) return;
    try {
      await deactivateStore(store.id);
      setStores((prev) => prev.map((s) => s.id === store.id ? { ...s, is_active: false } : s));
    } catch {
      alert('Erreur lors de la désactivation');
    }
  };

  // ── Search debounce ────────────────────────────────────────────────────────

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = (v: string) => {
    setSearch(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setSkip(0); }, 400);
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  const lr = updateStatus?.last_result;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-gray-900">Magasins</h2>
        <p className="text-gray-500 mt-1">
          {total} magasin{total > 1 ? 's' : ''} en base — mise à jour automatique chaque lundi à 02:00
        </p>
      </div>

      {/* Update control panel */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="text-base font-bold text-gray-800">Mise à jour des magasins</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              Sources : OpenStreetMap (Overpass API) + store locators officiels
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Source toggles */}
            {['osm', 'locator'].map((src) => (
              <label key={src} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selectedSources.includes(src)}
                  onChange={(e) =>
                    setSelectedSources((prev) =>
                      e.target.checked ? [...prev, src] : prev.filter((s) => s !== src)
                    )
                  }
                  className="rounded"
                />
                <span className="text-sm font-medium text-gray-700">
                  {src === 'osm' ? '🗺️ OpenStreetMap' : '🏪 Store Locators'}
                </span>
              </label>
            ))}

            <button
              onClick={handleTriggerUpdate}
              disabled={triggering || updateStatus?.running || selectedSources.length === 0}
              className="px-5 py-2 text-sm font-semibold bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-xl transition-colors"
            >
              {triggering || updateStatus?.running ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  {updateStatus?.running ? 'En cours…' : 'Démarrage…'}
                </span>
              ) : (
                '🔄 Lancer la mise à jour'
              )}
            </button>
          </div>
        </div>

        {/* Status card */}
        {updateStatus && (
          <div className={`rounded-xl p-4 text-sm ${
            updateStatus.running
              ? 'bg-blue-50 border border-blue-200'
              : lr?.status === 'success'
              ? 'bg-green-50 border border-green-200'
              : lr?.status === 'error'
              ? 'bg-red-50 border border-red-200'
              : 'bg-gray-50 border border-gray-200'
          }`}>
            {updateStatus.running ? (
              <div className="flex items-center gap-3 text-blue-700">
                <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />
                <span>
                  Mise à jour en cours depuis {updateStatus.started_at
                    ? new Date(updateStatus.started_at).toLocaleTimeString('fr-MA')
                    : '…'}
                  <span className="text-blue-500 ml-2">· vérification toutes les 5s</span>
                </span>
              </div>
            ) : lr ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-semibold text-gray-800">
                  {lr.status === 'success' ? '✅' : '❌'} Dernière mise à jour —{' '}
                  {lr.finished_at ? new Date(lr.finished_at).toLocaleString('fr-MA') : '—'}
                </div>
                {lr.status === 'success' && (
                  <div className="flex flex-wrap gap-4 text-gray-600">
                    <span>📥 <strong>{lr.fetched}</strong> collectés</span>
                    <span>🔍 <strong>{lr.after_dedup}</strong> après dédup</span>
                    <span className="text-green-700">➕ <strong>{lr.inserted}</strong> insérés</span>
                    <span className="text-blue-700">✏️ <strong>{lr.updated}</strong> mis à jour</span>
                    {lr.sources_ok && lr.sources_ok.length > 0 && (
                      <span className="text-green-600">✓ {lr.sources_ok.join(', ')}</span>
                    )}
                    {lr.sources_failed && lr.sources_failed.length > 0 && (
                      <span className="text-orange-600">⚠ {lr.sources_failed.join(', ')}</span>
                    )}
                  </div>
                )}
                {lr.warning && (
                  <p className="text-orange-600">⚠️ {lr.warning}</p>
                )}
                {lr.error && (
                  <p className="text-red-600">❌ {lr.error}</p>
                )}
              </div>
            ) : (
              <p className="text-gray-500 italic">Aucune mise à jour effectuée dans cette session.</p>
            )}
          </div>
        )}

        <p className="text-xs text-gray-400">
          ℹ️ La mise à jour automatique s'exécute <strong>chaque lundi à 02h00</strong> (Africa/Casablanca).
          Le job de démarrage initial est déclenché au lancement du serveur.
          Pour peupler la base de zéro, exécutez : <code className="bg-gray-100 px-1 rounded">python seed_stores_osm.py</code>
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          placeholder="🔍 Rechercher un magasin…"
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="flex-1 min-w-48 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
        />
        <input
          type="text"
          placeholder="Filtrer par ville…"
          value={cityFilter}
          onChange={(e) => { setCityFilter(e.target.value); setSkip(0); }}
          className="w-40 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
        />
        <button
          onClick={() => { setSearch(''); setCityFilter(''); setSkip(0); }}
          className="px-4 py-2.5 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
        >
          Effacer
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Nom</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Ville</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Région</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Adresse</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">GPS</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Statut</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-gray-400">
                    <span className="inline-block w-5 h-5 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                  </td>
                </tr>
              ) : stores.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-gray-400 italic">
                    Aucun magasin trouvé
                  </td>
                </tr>
              ) : (
                stores.map((s) => (
                  <tr key={s.id} className={`hover:bg-gray-50 transition-colors ${!s.is_active ? 'opacity-40' : ''}`}>
                    <td className="px-4 py-3 font-medium text-gray-800">{s.name}</td>
                    <td className="px-4 py-3 text-gray-600">{s.city ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{s.region ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-xs truncate">{s.address ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                      {s.latitude && s.longitude
                        ? `${s.latitude.toFixed(4)}, ${s.longitude.toFixed(4)}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                        s.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {s.is_active ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        {s.latitude && s.longitude && (
                          <a
                            href={`https://www.openstreetmap.org/?mlat=${s.latitude}&mlon=${s.longitude}&zoom=16`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-500 hover:underline"
                          >
                            🗺️ OSM
                          </a>
                        )}
                        {s.is_active && (
                          <button
                            onClick={() => handleDeactivate(s)}
                            className="text-xs text-red-500 hover:text-red-700"
                          >
                            Désactiver
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
            <span className="text-sm text-gray-500">
              {skip + 1}–{Math.min(skip + LIMIT, total)} / {total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={skip === 0}
                onClick={() => setSkip((p) => Math.max(0, p - LIMIT))}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40 hover:bg-white"
              >
                ← Précédent
              </button>
              <button
                disabled={skip + LIMIT >= total}
                onClick={() => setSkip((p) => p + LIMIT)}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40 hover:bg-white"
              >
                Suivant →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
