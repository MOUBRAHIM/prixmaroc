import React, { useEffect, useState } from 'react';
import { getDashboardStats } from '../api';

interface Stats {
  products: number | string;
  stores: number | string;
  promos: number | string;
}

function StatCard({ label, value, icon, color }: { label: string; value: string | number; icon: string; color: string }) {
  return (
    <div className={`bg-white rounded-2xl p-6 shadow-sm border border-gray-100`}>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 ${color}`}>
        {icon}
      </div>
      <p className="text-3xl font-black text-gray-900">{value}</p>
      <p className="text-sm text-gray-500 mt-1 font-medium">{label}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(() => setStats({ products: 'Erreur', stores: 'Erreur', promos: 'Erreur' }))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-black text-gray-900">Dashboard</h2>
        <p className="text-gray-500 mt-1">Vue d'ensemble de PrixMaroc en temps réel</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard label="Produits en base" value={stats?.products ?? '—'} icon="📦" color="bg-green-50" />
          <StatCard label="Magasins actifs" value={stats?.stores ?? '—'} icon="🏪" color="bg-blue-50" />
          <StatCard label="Promotions actives" value={stats?.promos ?? '—'} icon="🔥" color="bg-orange-50" />
        </div>
      )}

      {/* Info card */}
      <div className="bg-green-50 border border-green-200 rounded-2xl p-6">
        <h3 className="font-bold text-green-800 mb-2">🚀 Système opérationnel</h3>
        <p className="text-sm text-green-700">
          Les scrapers tournent automatiquement chaque nuit entre 3h et 5h (heure Maroc).
          Les notifications push sont envoyées le matin selon le planning configuré.
        </p>
        <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <div className="bg-white rounded-xl p-3 text-center">
            <p className="font-bold text-gray-700">Dimanche 9h</p>
            <p className="text-gray-500">Liste hebdo</p>
          </div>
          <div className="bg-white rounded-xl p-3 text-center">
            <p className="font-bold text-gray-700">Tous les jours 8h</p>
            <p className="text-gray-500">Promos du jour</p>
          </div>
          <div className="bg-white rounded-xl p-3 text-center">
            <p className="font-bold text-gray-700">Lundi 7h</p>
            <p className="text-gray-500">Bilan économies</p>
          </div>
        </div>
      </div>
    </div>
  );
}
