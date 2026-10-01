/**
 * BasculeComparer — les deux façons d'arriver à un prix.
 *
 * « Rechercher » quand on sait ce qu'on veut, « Derniers relevés » quand on
 * vient voir ce que la collecte a rapporté cette semaine. Les deux vivent
 * sous l'onglet Comparer et se répondent, d'où une bascule plutôt que deux
 * entrées sans lien dans la barre du bas.
 *
 * On remplace l'écran au lieu de l'empiler : revenir en arrière depuis les
 * relevés doit quitter Comparer, pas rejouer la bascule.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { C, Radius } from '@constants/colors';
import type { ComparerStackParamList } from '@types/models';

type Onglet = 'Recherche' | 'DerniersReleves';

const ONGLETS: { cle: Onglet; libelle: string }[] = [
  { cle: 'Recherche', libelle: 'Rechercher' },
  { cle: 'DerniersReleves', libelle: 'Derniers relevés' },
];

interface Props {
  actif: Onglet;
}

export default function BasculeComparer({ actif }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<ComparerStackParamList>>();

  return (
    <View style={styles.barre}>
      {ONGLETS.map(({ cle, libelle }) => {
        const selectionne = cle === actif;
        return (
          <TouchableOpacity
            key={cle}
            style={[styles.onglet, selectionne && styles.ongletActif]}
            onPress={() => { if (!selectionne) navigation.replace(cle); }}
            accessibilityRole="tab"
            accessibilityState={{ selected: selectionne }}
            activeOpacity={0.8}
          >
            <Text style={[styles.libelle, selectionne && styles.libelleActif]}>
              {libelle}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  barre: {
    flexDirection: 'row',
    gap: 6,
    padding: 5,
    margin: 16,
    marginBottom: 8,
    backgroundColor: C.bg,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: C.border,
  },
  onglet: {
    flex: 1,
    paddingVertical: 9,
    borderRadius: Radius.pill,
    alignItems: 'center',
  },
  ongletActif: { backgroundColor: C.primary },
  libelle: { fontSize: 14, fontWeight: '700', color: C.textSub },
  libelleActif: { color: C.white },
});
