/**
 * Store Zustand — Authentification
 * Persiste le token dans SecureStore (natif) / localStorage (web)
 */
import { create } from 'zustand';
import * as SecureStore from '@services/secureStorage';
import { AuthAPI, authEventEmitter } from '@services/api';
import { STORAGE_KEYS } from '@constants/index';
import { messageErreur } from '@utils/erreurs';
import type { User, UserCreate } from '@types/models';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  /**
   * Restauration de la session au démarrage — distincte de `isLoading`.
   *
   * La racine masquait toute l'application dès que `isLoading` passait à vrai,
   * donc aussi pendant une connexion : l'écran de connexion était démonté, la
   * saisie perdue, et l'utilisateur fixait « Chargement… » jusqu'à la fin du
   * réveil du serveur. Seule la restauration initiale justifie cet écran.
   */
  isRestoring: boolean;
  isAuthenticated: boolean;
  isGuest: boolean;
  error: string | null;

  // Actions
  login: (username: string, password: string) => Promise<void>;
  register: (payload: UserCreate) => Promise<void>;
  logout: () => Promise<void>;
  loginAsGuest: () => void;
  loadFromStorage: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: false,
  // Vrai dès le départ : sans cela, l'écran de connexion apparaît une fraction
  // de seconde avant que la session enregistrée ne soit relue.
  isRestoring: true,
  isAuthenticated: false,
  isGuest: false,
  error: null,

  login: async (username, password) => {
    set({ isLoading: true, error: null });
    try {
      const tokenData = await AuthAPI.login(username, password);
      await SecureStore.setItemAsync(STORAGE_KEYS.accessToken, tokenData.access_token);

      const user = await AuthAPI.me();
      await SecureStore.setItemAsync(STORAGE_KEYS.user, JSON.stringify(user));

      set({ token: tokenData.access_token, user, isAuthenticated: true, isLoading: false });
    } catch (err: unknown) {
      // Sans réponse du serveur, ce n'est pas le mot de passe qui est en
      // cause : c'est le réseau, ou le service encore endormi. Le dire
      // « identifiants incorrects » envoyait l'utilisateur sur une fausse piste.
      const e = err as {
        response?: { status?: number; data?: { detail?: string } };
        code?: string;
      };
      let msg: string;
      if (!e.response) {
        msg = e.code === 'ECONNABORTED'
          ? "Le serveur met trop de temps à répondre. Il se réveille : réessayez dans une minute."
          : 'Serveur injoignable. Vérifiez votre connexion.';
      } else if (e.response.status === 401) {
        msg = 'Adresse e-mail ou mot de passe incorrect.';
      } else {
        msg = e.response.data?.detail || 'Connexion impossible. Réessayez.';
      }
      set({ error: msg, isLoading: false });
      throw err;
    }
  },

  register: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await AuthAPI.register(payload);
    } catch (err: unknown) {
      set({ error: messageErreur(err, "Inscription impossible. Réessayez."), isLoading: false });
      throw err;
    }
    // Le compte existe désormais. Si la connexion automatique échoue — service
    // endormi, réseau coupé — c'est son message qu'il faut garder : annoncer
    // « erreur d'inscription » ferait recommencer une inscription qui a réussi,
    // et le serveur refuserait alors l'adresse comme déjà prise.
    await get().login(payload.username, payload.password);
  },

  logout: async () => {
    await SecureStore.deleteItemAsync(STORAGE_KEYS.accessToken);
    await SecureStore.deleteItemAsync(STORAGE_KEYS.user);
    set({ user: null, token: null, isAuthenticated: false, isGuest: false, error: null });
  },

  loginAsGuest: () => {
    set({ user: null, token: null, isAuthenticated: true, isGuest: true, isLoading: false, error: null });
  },

  loadFromStorage: async () => {
    set({ isRestoring: true });
    try {
      const token = await SecureStore.getItemAsync(STORAGE_KEYS.accessToken);
      const userStr = await SecureStore.getItemAsync(STORAGE_KEYS.user);

      if (token && userStr) {
        const user: User = JSON.parse(userStr);
        // Vérifie que le token est encore valide
        try {
          const freshUser = await AuthAPI.me();
          set({ token, user: freshUser, isAuthenticated: true });
        } catch {
          // Token expiré
          await get().logout();
        }
      }
    } finally {
      set({ isRestoring: false });
    }
  },

  clearError: () => set({ error: null }),
}));

// Écoute les événements 401 pour déconnecter automatiquement
authEventEmitter.on('unauthorized', () => {
  useAuthStore.getState().logout();
});
