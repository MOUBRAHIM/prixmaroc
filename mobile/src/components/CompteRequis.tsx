/**
 * CompteRequis — ce qu'on montre à un visiteur sans compte.
 *
 * Les listes, les tickets et les alertes appartiennent à un compte. En mode
 * invité, ces écrans appelaient quand même le serveur, recevaient un 401 et
 * affichaient « Session expirée. Reconnectez-vous. » — un message qui parle
 * d'une session que le visiteur n'a jamais ouverte.
 *
 * Ici on ne parle pas d'erreur : on explique ce que le compte apporte.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { C } from '@constants/colors';

interface Props {
  /** Ce que le compte débloque, par exemple « enregistrer vos listes ». */
  usage: string;
  icone?: keyof typeof Ionicons.glyphMap;
  onCreerCompte?: () => void;
}

export default function CompteRequis({ usage, icone = 'person-circle-outline', onCreerCompte }: Props) {
  return (
    <View style={styles.bloc}>
      <Ionicons name={icone} size={52} color={C.primary} />
      <Text style={styles.titre}>Réservé aux comptes</Text>
      <Text style={styles.texte}>Créez un compte gratuit pour {usage}.</Text>
      {onCreerCompte && (
        <TouchableOpacity style={styles.bouton} onPress={onCreerCompte} accessibilityRole="button">
          <Text style={styles.boutonTexte}>Créer un compte</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bloc: { alignItems: 'center', paddingTop: 64, paddingHorizontal: 36, gap: 10 },
  titre: { fontSize: 18, fontWeight: '800', color: C.text },
  texte: { fontSize: 14, color: C.textSub, textAlign: 'center', lineHeight: 20 },
  bouton: {
    backgroundColor: C.primary, borderRadius: 12,
    paddingHorizontal: 24, paddingVertical: 12, marginTop: 6,
  },
  boutonTexte: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
});
