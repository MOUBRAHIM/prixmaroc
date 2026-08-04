import React, { useEffect, useRef, useState } from 'react';
import { getScraperStatus, triggerScraper, getWsBase } from '../api';

const SCRAPERS = [
  { slug: 'marjane',   name: 'Marjane',    color: 'text-red-600 bg-red-50',    dot: 'bg-red-500' },
  { slug: 'carrefour', name: 'Carrefour',  color: 'text-blue-600 bg-blue-50',  dot: 'bg-blue-500' },
  { slug: 'labelvie',  name: "Label'Vie",  color: 'text-green-600 bg-green-50',dot: 'bg-green-500' },
  { slug: 'bim',       name: 'BIM',        color: 'text-yellow-600 bg-yellow-50', dot: 'bg-yellow-500' },
  { slug: 'kazyon',    name: 'Kazyon',     color: 'text-orange-600 bg-orange-50', dot: 'bg-orange-500' },
  { slug: 'sopreco',   name: 'Sopreco',    color: 'text-purple-600 bg-purple-50', dot: 'bg-purple-500' },
  { slug: 'hmizate',   name: 'Hmizate',    color: 'text-cyan-600 bg-cyan-50',   dot: 'bg-cyan-500' },
];

interface LogEntry {
  type: 'log' | 'status' | 'heartbeat' | 'done' | 'error';
  level?: string;
  message?: string;
  time?: string;
  status?: string;
  run_id?: number;
  products_found?: number;
  pages_scraped?: number;
}

const LOG_COLORS: Record<string, string> = {
  ERROR: 'text-red-400',
  WARN: 'text-yellow-400',
  INFO: 'text-green-400',
};

export default function ScrapersPage() {
  const [status, setStatus] = useState<Record<string, any>>({});
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [logs, setLogs] = useState<Array<{ text: string; level: string; time: string }>>([]);
  const [wsStatus, setWsStatus] = useState<'idle' | 'connecting' | 'connected' | 'done' | 'error'>('idle');
  const [runStats, setRunStats] = useState<{ products_found: number; pages_scraped: number } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Poll statut toutes les 30s
  useEffect(() => {
    const fetch = () => getScraperStatus().then(setStatus).catch(() => {});
    fetch();
    const id = setInterval(fetch, 30_000);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Cleanup WS on unmount
  useEffect(() => () => wsRef.current?.close(), []);

  const connectWebSocket = (slug: string) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const token = localStorage.getItem('admin_token') ?? '';
    const wsBase = getWsBase();
    const url = `${wsBase}/admin/scrapers/${slug}/logs/stream?token=${encodeURIComponent(token)}`;

    setWsStatus('connecting');
    setActiveSlug(slug);
    setLogs([]);
    setRunStats(null);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus('connected');

    ws.onmessage = (evt) => {
      const msg: LogEntry = JSON.parse(evt.data);
      if (msg.type === 'log') {
        const level = msg.level ?? 'INFO';
        const time = msg.time ? new Date(msg.time).toLocaleTimeString('fr-MA') : '';
        setLogs((prev) => [...prev, { text: msg.message ?? '', level, time }]);
      } else if (msg.type === 'status') {
        if (msg.products_found !== undefined) {
          setRunStats({ products_found: msg.products_found!, pages_scraped: msg.pages_scraped! });
        }
      } else if (msg.type === 'done') {
        setWsStatus('done');
        ws.close();
        getScraperStatus().then(setStatus).catch(() => {});
      } else if (msg.type === 'error') {
        setLogs((prev) => [...prev, { text: `❌ ${msg.message}`, level: 'ERROR', time: '' }]);
        setWsStatus('error');
      }
    };

    ws.onerror = () => {
      setWsStatus('error');
      setLogs((prev) => [...prev, { text: '⚠️ Connexion WebSocket perdue', level: 'ERROR', time: '' }]);
    };

    ws.onclose = (evt) => {
      if (evt.code !== 1000 && wsStatus === 'connected') {
        setWsStatus('error');
      }
    };
  };

  const handleTrigger = async (slug: string) => {
    setTriggering(slug);
    try {
      await triggerScraper(slug);
      // Connexion WS après un court délai (le run doit être créé)
      setTimeout(() => connectWebSocket(slug), 800);
    } catch (err: any) {
      setLogs([{ text: `❌ Erreur déclenchement : ${err.message}`, level: 'ERROR', time: '' }]);
      setActiveSlug(slug);
      setWsStatus('error');
    } finally {
      setTriggering(null);
    }
  };

  const WS_BADGE: Record<string, string> = {
    idle: 'bg-gray-100 text-gray-500',
    connecting: 'bg-yellow-100 text-yellow-700',
    connected: 'bg-green-100 text-green-700',
    done: 'bg-blue-100 text-blue-700',
    error: 'bg-red-100 text-red-700',
  };
  const WS_LABEL: Record<string, string> = {
    idle: 'En attente',
    connecting: 'Connexion…',
    connected: '● Live',
    done: 'Terminé',
    error: 'Erreur',
  };

  return (
    <div className="p-8 space-y-8">
      <div>
        <h2 className="text-2xl font-black text-gray-900">Scrapers</h2>
        <p className="text-gray-500 mt-1">Gestion et déclenchement manuel — logs en temps réel via WebSocket</p>
      </div>

      {/* Grille scrapers */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {SCRAPERS.map((s) => {
          const info = status[s.slug];
          const isActive = activeSlug === s.slug;
          return (
            <div
              key={s.slug}
              className={`bg-white rounded-2xl p-5 shadow-sm border transition-all ${
                isActive ? 'border-green-400 ring-2 ring-green-100' : 'border-gray-100'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`text-sm font-bold px-3 py-1 rounded-full ${s.color}`}>{s.name}</span>
                <div className="flex items-center gap-2">
                  {info?.status === 'success' && (
                    <span className="text-xs text-green-600 font-semibold">✓ OK</span>
                  )}
                  {info?.status === 'failed' && (
                    <span className="text-xs text-red-500 font-semibold">✗ Échec</span>
                  )}
                  <span className="text-xs text-gray-400">
                    {info?.last_run ? new Date(info.last_run).toLocaleString('fr-MA') : 'Jamais'}
                  </span>
                </div>
              </div>

              <div className="text-sm text-gray-600 mb-4 space-y-1">
                <div className="flex justify-between">
                  <span>Produits récupérés</span>
                  <span className="font-semibold">{info?.products_count ?? '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Statut</span>
                  <span className={`font-semibold ${
                    info?.status === 'success' ? 'text-green-600' :
                    info?.status === 'running' ? 'text-blue-500' :
                    info?.status === 'failed' ? 'text-red-600' : 'text-gray-400'
                  }`}>
                    {info?.status ?? 'inconnu'}
                  </span>
                </div>
              </div>

              <button
                onClick={() => handleTrigger(s.slug)}
                disabled={triggering === s.slug || info?.status === 'running'}
                className="w-full py-2 text-sm font-semibold bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-xl transition-colors"
              >
                {triggering === s.slug ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Démarrage…
                  </span>
                ) : info?.status === 'running' ? (
                  '⏳ En cours…'
                ) : (
                  '▶ Déclencher maintenant'
                )}
              </button>

              {isActive && (
                <button
                  onClick={() => connectWebSocket(s.slug)}
                  className="w-full mt-2 py-1.5 text-xs font-semibold border border-gray-200 hover:bg-gray-50 rounded-xl text-gray-600 transition-colors"
                >
                  🔄 Reconnecter les logs
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Terminal logs WebSocket */}
      {activeSlug && (
        <div className="bg-gray-950 rounded-2xl overflow-hidden border border-gray-800">
          {/* Barre de titre */}
          <div className="flex items-center justify-between px-5 py-3 bg-gray-900 border-b border-gray-800">
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
              </div>
              <span className="text-gray-300 text-sm font-mono font-semibold">
                scraper/{activeSlug} — logs temps réel
              </span>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${WS_BADGE[wsStatus]}`}>
                {WS_LABEL[wsStatus]}
              </span>
            </div>
            <div className="flex items-center gap-3">
              {runStats && (
                <span className="text-xs text-gray-400 font-mono">
                  {runStats.products_found} produits · {runStats.pages_scraped} pages
                </span>
              )}
              <button
                onClick={() => setLogs([])}
                className="text-gray-500 hover:text-gray-300 text-xs"
              >
                Effacer
              </button>
              <button
                onClick={() => { wsRef.current?.close(); setActiveSlug(null); setWsStatus('idle'); }}
                className="text-gray-500 hover:text-gray-300 text-xs"
              >
                ✕ Fermer
              </button>
            </div>
          </div>

          {/* Contenu logs */}
          <div className="p-4 h-72 overflow-y-auto font-mono text-xs space-y-0.5">
            {logs.length === 0 ? (
              <p className="text-gray-600 italic">
                {wsStatus === 'connecting'
                  ? 'Connexion au stream de logs…'
                  : wsStatus === 'connected'
                  ? 'En attente des premiers logs…'
                  : 'Aucun log disponible. Déclenchez un scraper.'}
              </p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-3 leading-5">
                  {log.time && (
                    <span className="text-gray-600 shrink-0">{log.time}</span>
                  )}
                  <span className={`shrink-0 w-12 ${LOG_COLORS[log.level] ?? 'text-gray-400'}`}>
                    [{log.level}]
                  </span>
                  <span className="text-gray-200 break-all">{log.text}</span>
                </div>
              ))
            )}
            {wsStatus === 'connected' && (
              <div className="flex items-center gap-1 text-green-500 mt-1">
                <span className="inline-block w-1.5 h-3 bg-green-500 animate-pulse rounded-sm" />
                <span className="text-gray-600">live</span>
              </div>
            )}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}
