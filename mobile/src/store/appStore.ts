/**
 * Store Zustand — État global de l'application
 */
import { create } from 'zustand';

interface AppState {
  city: string | null;               // Ville sélectionnée pour filtrer les prix
  searchQuery: string;               // Barre de recherche partagée
  compareProductIds: number[];       // Produits en cours de comparaison (max 4)
  isNetworkOnline: boolean;

  setCity: (city: string | null) => void;
  setSearchQuery: (query: string) => void;
  addToCompare: (id: number) => void;
  removeFromCompare: (id: number) => void;
  clearCompare: () => void;
  setNetworkStatus: (online: boolean) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  city: null,
  searchQuery: '',
  compareProductIds: [],
  isNetworkOnline: true,

  setCity: (city) => set({ city }),
  setSearchQuery: (query) => set({ searchQuery: query }),

  addToCompare: (id) => {
    const ids = get().compareProductIds;
    if (ids.length >= 4 || ids.includes(id)) return;
    set({ compareProductIds: [...ids, id] });
  },

  removeFromCompare: (id) => {
    set({ compareProductIds: get().compareProductIds.filter((i) => i !== id) });
  },

  clearCompare: () => set({ compareProductIds: [] }),

  setNetworkStatus: (online) => set({ isNetworkOnline: online }),
}));
