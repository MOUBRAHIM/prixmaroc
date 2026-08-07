/**
 * Service Notifications Push — PrixMaroc
 * - Demande les permissions
 * - Récupère le token Expo Push
 * - Enregistre le token sur le backend
 * - Configure les handlers de réception + deep link (via navigationRef)
 */
import { Platform } from 'react-native';
import { NotificationsAPI } from './api';
import { navigateFromNotification } from '../navigation';

// Import conditionnel — expo-notifications non supporté dans Expo Go (SDK 53+)
// Fonctionne uniquement dans un development build ou en production
let Notifications: typeof import('expo-notifications') | null = null;
let _isExpoGo = false;
try {
  // Détecte Expo Go via la constante d'environnement
  const Constants = require('expo-constants').default;
  _isExpoGo = Constants?.executionEnvironment === 'storeClient';
} catch { /* ignore */ }

if (!_isExpoGo) {
  try {
    Notifications = require('expo-notifications');
  } catch {
    console.log('[Notifications] expo-notifications non disponible');
  }
} else {
  console.log('[Notifications] Expo Go détecté — notifications désactivées (utilisez un dev build)');
}

// ── Mapping screen → tab + stack ──────────────────────────────────────────────
// Les screens dans les notifications doivent correspondre aux noms de la navigation

const SCREEN_MAP: Record<string, { tab: string; stack?: string; params?: Record<string, unknown> }> = {
  Dashboard:       { tab: 'Accueil',  stack: 'Dashboard' },
  Promotions:      { tab: 'Accueil',  stack: 'Promotions' },
  MagasinsProches: { tab: 'Accueil',  stack: 'MagasinsProches' },
  MesListes:       { tab: 'Listes',   stack: 'MesListes' },
  NouvelleListeIA: { tab: 'Listes',   stack: 'NouvelleListeIA' },
  MonProfil:       { tab: 'Profil',   stack: 'MonProfil' },
  Scanner:         { tab: 'Scanner' },
};

// Configure l'affichage en foreground
if (Notifications) {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });
}

/**
 * Demande la permission et retourne le token push Expo.
 * Retourne null si permission refusée ou module non disponible.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  if (!Notifications) {
    console.log('[Notifications] Module non disponible');
    return null;
  }

  if (Platform.OS === 'web') {
    console.log('[Notifications] Web non supporté');
    return null;
  }

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.log('[Notifications] Permission refusée');
      return null;
    }

    // Canal Android
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('prixmaroc', {
        name: 'PrixMaroc',
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#0F4C3A',
        description: 'Alertes prix et listes de courses',
      });
    }

    const tokenData = await Notifications.getExpoPushTokenAsync();
    return tokenData.data;
  } catch (err) {
    console.log('[Notifications] Erreur token:', err);
    return null;
  }
}

/**
 * Enregistre le token push sur le backend PrixMaroc.
 */
export async function registerTokenOnBackend(token: string): Promise<void> {
  try {
    await NotificationsAPI.register(token, Platform.OS);
    console.log('[Notifications] Token enregistré sur le backend');
  } catch (err) {
    console.log('[Notifications] Erreur enregistrement backend:', err);
  }
}

/**
 * Dé-enregistre le token (à appeler au logout).
 */
export async function unregisterToken(): Promise<void> {
  try {
    await NotificationsAPI.unregister();
    console.log('[Notifications] Token supprimé du backend');
  } catch (err) {
    console.log('[Notifications] Erreur suppression token:', err);
  }
}

/**
 * Configure le handler de tap sur notification.
 * Utilise navigationRef pour naviguer sans prop navigate.
 * Retourne une fonction de cleanup.
 */
export function setupNotificationResponseHandler(): () => void {
  if (!Notifications) return () => {};

  const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data as Record<string, unknown> | undefined;
    if (!data) return;

    const screen = data.screen as string | undefined;
    if (!screen) return;

    console.log('[Notifications] Tap → screen:', screen);

    // Navigation via ref global
    const mapped = SCREEN_MAP[screen];
    if (mapped) {
      navigateFromNotification(mapped.stack ?? screen, data as Record<string, unknown>);
    } else {
      // Screen non mappé : tenter navigation directe
      navigateFromNotification(screen, data as Record<string, unknown>);
    }
  });

  return () => subscription.remove();
}
