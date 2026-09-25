/**
 * dialogue.ts — Demander et informer, sur mobile comme dans le navigateur.
 *
 * `Alert.alert` de React Native ne fait rien sur le web : la fonction existe,
 * ne lève aucune erreur, et n'affiche rien. Toute action placée derrière une
 * confirmation devenait donc silencieusement impossible — c'est pourquoi le
 * bouton « Supprimer » d'une liste ne supprimait rien, et pourquoi
 * l'enregistrement semblait échouer alors qu'il réussissait sans le dire.
 *
 * Ces deux fonctions s'appuient sur les boîtes natives du navigateur sur le
 * web, et sur Alert ailleurs.
 */
import { Alert, Platform } from 'react-native';

interface DemandeConfirmation {
  titre: string;
  message: string;
  /** Libellé du bouton qui valide. Par défaut « Confirmer ». */
  action?: string;
  /** Action irréversible : le bouton prend le style destructeur sur iOS. */
  destructif?: boolean;
}

export function confirmer({
  titre,
  message,
  action = 'Confirmer',
  destructif = false,
}: DemandeConfirmation): Promise<boolean> {
  if (Platform.OS === 'web') {
    // window.confirm est bloquant et synchrone : on enveloppe pour offrir la
    // même signature qu'ailleurs.
    return Promise.resolve(
      typeof window !== 'undefined' && typeof window.confirm === 'function'
        ? window.confirm(`${titre}\n\n${message}`)
        : true,
    );
  }
  return new Promise((resoudre) => {
    Alert.alert(titre, message, [
      { text: 'Annuler', style: 'cancel', onPress: () => resoudre(false) },
      {
        text: action,
        style: destructif ? 'destructive' : 'default',
        onPress: () => resoudre(true),
      },
    ]);
  });
}

export function prevenir(titre: string, message?: string): void {
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && typeof window.alert === 'function') {
      window.alert(message ? `${titre}\n\n${message}` : titre);
    }
    return;
  }
  Alert.alert(titre, message);
}
