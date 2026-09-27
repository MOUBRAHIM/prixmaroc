/**
 * EtatErreur — le bloc affiché quand un chargement échoue.
 *
 * Chaque écran écrivait le sien, avec un titre figé : « Impossible de charger
 * les listes », « Erreur lors de la recherche ». L'utilisateur apprenait que
 * quelque chose n'allait pas, jamais quoi — un serveur endormi, une session
 * expirée et une vraie panne se ressemblaient toutes.
 *
 * Ce composant garde le titre de l'écran et ajoute dessous la cause réelle,
 * tirée de la réponse du serveur par `messageErreur`.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { C } from '@constants/colors';
import { messageErreur } from '@utils/erreurs';

interface Props {
  /** Ce que l'écran n'a pas pu faire, par exemple « Impossible de charger les listes ». */
  titre: string;
  /** L'erreur remontée par la requête ; sa cause est affichée sous le titre. */
  error?: unknown;
  onRetry?: () => void;
}

export default function EtatErreur({ titre, error, onRetry }: Props) {
  const cause = error ? messageErreur(error, '') : '';

  return (
    <View style={styles.bloc}>
      <Ionicons name="alert-circle-outline" size={44} color={C.terre} />
      <Text style={styles.titre}>{titre}</Text>
      {!!cause && cause !== titre && <Text style={styles.cause}>{cause}</Text>}
      {onRetry && (
        <TouchableOpacity style={styles.bouton} onPress={onRetry} accessibilityRole="button">
          <Text style={styles.boutonTexte}>Réessayer</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 32, gap: 10 },
  titre: { color: C.terre, fontSize: 15, fontWeight: '600', textAlign: 'center' },
  cause: { color: C.textMuted, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  bouton: {
    backgroundColor: C.primary, borderRadius: 12,
    paddingHorizontal: 24, paddingVertical: 12, marginTop: 4,
  },
  boutonTexte: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
});
