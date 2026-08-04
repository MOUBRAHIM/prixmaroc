/**
 * PrixMaroc — App.tsx
 * Point d'entrée Expo avec QueryClient, GestureHandler, SafeArea
 * et initialisation des notifications push.
 */
import 'react-native-gesture-handler';
import React, { useEffect } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@store/authStore';
import Navigation from '@nav/index';
import { C } from '@constants/colors';
import {
  registerForPushNotifications,
  registerTokenOnBackend,
  setupNotificationResponseHandler,
} from './src/services/notifications';
import { initApiUrl } from './src/services/api';

// ── React Query config ────────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      gcTime: 1000 * 60 * 30,
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: { retry: 1 },
  },
});

// ─────────────────────────────────────────────────────────────────────────────

export default function App() {
  const loadFromStorage = useAuthStore((s) => s.loadFromStorage);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Initialise l'URL API stockée + restaure la session
  useEffect(() => {
    initApiUrl().then(() => loadFromStorage());
  }, []);

  // Initialise les notifications push après authentification
  useEffect(() => {
    if (!isAuthenticated) return;

    let cleanup: (() => void) | undefined;

    const init = async () => {
      // Setup du handler de tap (deep links) — avant d'enregistrer le token
      cleanup = setupNotificationResponseHandler();

      // Enregistrement du token
      const token = await registerForPushNotifications();
      if (token) {
        await registerTokenOnBackend(token);
      }
    };

    init().catch(console.error);

    return () => {
      cleanup?.();
    };
  }, [isAuthenticated]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="light" backgroundColor={C.primary} />
          <Navigation />
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
