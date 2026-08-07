/**
 * ProductVisual — vignette illustrée d'un produit.
 *
 * Si le produit a une vraie photo (image_url), on l'affiche.
 * Sinon on génère une vignette : pictogramme + teinte dérivés du type de
 * produit. Aucun appel réseau, rendu instantané et identité visuelle
 * cohérente dans toute l'app (plutôt qu'une image cassée ou un placeholder gris).
 */
import React, { memo } from 'react';
import { View, Text, Image, StyleSheet, type ViewStyle } from 'react-native';

// (mot-clé dans le nom, pictogramme, fond, teinte du pictogramme)
// Parcouru dans l'ordre : le plus spécifique d'abord.
const VISUALS: [string, string, string, string][] = [
  // Boissons
  ['eau minérale',   '💧', '#eff6ff', '#3b82f6'],
  ['coca',           '🥤', '#fef2f2', '#dc2626'],
  ['pepsi',          '🥤', '#eff6ff', '#2563eb'],
  ['ice tea',        '🧊', '#fefce8', '#ca8a04'],
  ["jus d'orange",   '🍹', '#fff7ed', '#ea580c'],
  ['jus',            '🧃', '#fff7ed', '#ea580c'],
  ['café',           '☕', '#f5f1ed', '#78350f'],
  ['thé',            '🍵', '#f0fdf4', '#15803d'],
  // Épicerie de base
  ["huile d'olive",  '🫒', '#f7fee7', '#4d7c0f'],
  ['huile',          '🫗', '#fefce8', '#a16207'],
  ['sucre',          '🍬', '#fdf4ff', '#a21caf'],
  ['sel',            '🧂', '#f8fafc', '#475569'],
  ['farine',         '🌾', '#fefce8', '#a16207'],
  ['levure',         '🫧', '#faf5ff', '#7e22ce'],
  ['couscous',       '🍚', '#fffbeb', '#b45309'],
  ['riz',            '🍚', '#fffbeb', '#b45309'],
  ['spaghetti',      '🍝', '#fffbeb', '#b45309'],
  ['penne',          '🍝', '#fffbeb', '#b45309'],
  ['vermicelles',    '🍜', '#fffbeb', '#b45309'],
  ['pain de mie',    '🍞', '#fff7ed', '#c2410c'],
  ['biscottes',      '🍘', '#fff7ed', '#c2410c'],
  // Légumineuses
  ['pois chiches',   '🫘', '#f7fee7', '#65a30d'],
  ['lentilles',      '🫘', '#f7fee7', '#65a30d'],
  ['haricots blancs','🫘', '#f7fee7', '#65a30d'],
  ['fèves',          '🫘', '#f7fee7', '#65a30d'],
  // Laitiers & œufs
  ['lait',           '🥛', '#f0f9ff', '#0369a1'],
  ['yaourt',         '🥣', '#f0f9ff', '#0369a1'],
  ['fromage',        '🧀', '#fefce8', '#ca8a04'],
  ['beurre',         '🧈', '#fefce8', '#ca8a04'],
  ['margarine',      '🧈', '#fefce8', '#ca8a04'],
  ['crème',          '🍶', '#f0f9ff', '#0369a1'],
  ['œufs',           '🥚', '#fffbeb', '#b45309'],
  ['oeufs',          '🥚', '#fffbeb', '#b45309'],
  // Viandes & poissons
  ['poulet',         '🍗', '#fff7ed', '#c2410c'],
  ['dinde',          '🍗', '#fff7ed', '#c2410c'],
  ['kefta',          '🥩', '#fef2f2', '#b91c1c'],
  ['merguez',        '🌭', '#fef2f2', '#b91c1c'],
  ['agneau',         '🥩', '#fef2f2', '#b91c1c'],
  ['veau',           '🥩', '#fef2f2', '#b91c1c'],
  ['viande',         '🥩', '#fef2f2', '#b91c1c'],
  ['sardines',       '🐟', '#ecfeff', '#0e7490'],
  ['thon',           '🐟', '#ecfeff', '#0e7490'],
  ['sole',           '🐟', '#ecfeff', '#0e7490'],
  ['crevettes',      '🦐', '#fff1f2', '#be123c'],
  // Légumes
  ['tomates',        '🍅', '#fef2f2', '#dc2626'],
  ['oignons',        '🧅', '#fdf4ff', '#a21caf'],
  ['pommes de terre','🥔', '#fffbeb', '#b45309'],
  ['carottes',       '🥕', '#fff7ed', '#ea580c'],
  ['courgettes',     '🥒', '#f0fdf4', '#16a34a'],
  ['poivrons',       '🫑', '#f0fdf4', '#16a34a'],
  ['aubergines',     '🍆', '#faf5ff', '#7e22ce'],
  ['navets',         '🥬', '#f0fdf4', '#16a34a'],
  ['chou',           '🥬', '#f0fdf4', '#16a34a'],
  ['epinards',       '🥬', '#f0fdf4', '#16a34a'],
  ['épinards',       '🥬', '#f0fdf4', '#16a34a'],
  ['haricots verts', '🫛', '#f0fdf4', '#16a34a'],
  ['betteraves',     '🥬', '#fdf2f8', '#be185d'],
  ['petits pois',    '🫛', '#f0fdf4', '#16a34a'],
  ['ail',            '🧄', '#f8fafc', '#475569'],
  ['persil',         '🌿', '#f0fdf4', '#16a34a'],
  // Fruits
  ['oranges',        '🍊', '#fff7ed', '#ea580c'],
  ['clémentines',    '🍊', '#fff7ed', '#ea580c'],
  ['pommes',         '🍎', '#fef2f2', '#dc2626'],
  ['bananes',        '🍌', '#fefce8', '#ca8a04'],
  ['grenades',       '🍎', '#fff1f2', '#be123c'],
  ['raisins',        '🍇', '#faf5ff', '#7e22ce'],
  ['pastèque',       '🍉', '#f0fdf4', '#16a34a'],
  ['dattes',         '🌴', '#fffbeb', '#b45309'],
  ['figues',         '🫒', '#faf5ff', '#7e22ce'],
  // Condiments & sucré
  ['harissa',        '🌶️', '#fef2f2', '#dc2626'],
  ['concentré',      '🥫', '#fef2f2', '#dc2626'],
  ['tomates pelées', '🥫', '#fef2f2', '#dc2626'],
  ['olives',         '🫒', '#f7fee7', '#4d7c0f'],
  ['citrons',        '🍋', '#fefce8', '#ca8a04'],
  ['miel',           '🍯', '#fffbeb', '#b45309'],
  ['confiture',      '🍓', '#fff1f2', '#be123c'],
  ['amlou',          '🥜', '#fffbeb', '#b45309'],
  // Épices
  ['cumin',          '🧂', '#fffbeb', '#b45309'],
  ['paprika',        '🌶️', '#fef2f2', '#dc2626'],
  ['ras el hanout',  '🧂', '#fffbeb', '#b45309'],
  ['gingembre',      '🫚', '#fffbeb', '#b45309'],
  ['curcuma',        '🧂', '#fffbeb', '#ca8a04'],
  ['cannelle',       '🧂', '#fff7ed', '#c2410c'],
  ['safran',         '🌺', '#fff7ed', '#ea580c'],
  ['poivre',         '🧂', '#f8fafc', '#475569'],
  // Hygiène & entretien
  ['dentifrice',     '🪥', '#eff6ff', '#2563eb'],
  ['shampooing',     '🧴', '#eff6ff', '#2563eb'],
  ['savon',          '🧼', '#eff6ff', '#2563eb'],
  ['gel douche',     '🧴', '#eff6ff', '#2563eb'],
  ['déodorant',      '🧴', '#eff6ff', '#2563eb'],
  ['lessive',        '🧺', '#eef2ff', '#4338ca'],
  ['javel',          '🧽', '#eef2ff', '#4338ca'],
  ['vaisselle',      '🧽', '#eef2ff', '#4338ca'],
  ['nettoyant',      '🧽', '#eef2ff', '#4338ca'],
  ['papier toilette','🧻', '#f8fafc', '#475569'],
  // Bébé
  ['couches',        '👶', '#fdf2f8', '#be185d'],
  ['lingettes',      '👶', '#fdf2f8', '#be185d'],
];

const DEFAULT: [string, string, string] = ['🛒', '#f1f5f9', '#64748b'];

export function visualFor(name: string): { icon: string; bg: string; fg: string } {
  const n = (name || '').toLowerCase();
  for (const [keyword, icon, bg, fg] of VISUALS) {
    if (n.includes(keyword)) return { icon, bg, fg };
  }
  const [icon, bg, fg] = DEFAULT;
  return { icon, bg, fg };
}

interface Props {
  name: string;
  imageUrl?: string | null;
  size?: number;
  radius?: number;
  style?: ViewStyle;
}

const ProductVisual: React.FC<Props> = ({ name, imageUrl, size = 72, radius = 12, style }) => {
  const { icon, bg, fg } = visualFor(name);

  if (imageUrl) {
    return (
      <Image
        source={{ uri: imageUrl }}
        style={[{ width: size, height: size, borderRadius: radius }, style]}
        resizeMode="contain"
      />
    );
  }

  return (
    <View
      style={[
        styles.tile,
        { width: size, height: size, borderRadius: radius, backgroundColor: bg, borderColor: `${fg}22` },
        style,
      ]}
    >
      <Text style={{ fontSize: size * 0.46 }}>{icon}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  tile: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
});

export default memo(ProductVisual);
