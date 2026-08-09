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
  ['eau minérale',   '💧', '#EAF3F5', '#2E7D8F'],
  ['coca',           '🥤', '#FBEDEC', '#C1272D'],
  ['pepsi',          '🥤', '#EAF3F5', '#256B7A'],
  ['ice tea',        '🧊', '#fefce8', '#ca8a04'],
  ["jus d'orange",   '🍹', '#FDF6EC', '#C4620F'],
  ['jus',            '🧃', '#FDF6EC', '#C4620F'],
  ['café',           '☕', '#f5f1ed', '#78350f'],
  ['thé',            '🍵', '#EEF6F1', '#0C3F30'],
  // Épicerie de base
  ["huile d'olive",  '🫒', '#f7fee7', '#4d7c0f'],
  ['huile',          '🫗', '#fefce8', '#8A6410'],
  ['sucre',          '🍬', '#fdf4ff', '#a21caf'],
  ['sel',            '🧂', '#F2F6F0', '#3C4F47'],
  ['farine',         '🌾', '#fefce8', '#8A6410'],
  ['levure',         '🫧', '#faf5ff', '#7e22ce'],
  ['couscous',       '🍚', '#fffbeb', '#b45309'],
  ['riz',            '🍚', '#fffbeb', '#b45309'],
  ['spaghetti',      '🍝', '#fffbeb', '#b45309'],
  ['penne',          '🍝', '#fffbeb', '#b45309'],
  ['vermicelles',    '🍜', '#fffbeb', '#b45309'],
  ['pain de mie',    '🍞', '#FDF6EC', '#c2410c'],
  ['biscottes',      '🍘', '#FDF6EC', '#c2410c'],
  // Légumineuses
  ['pois chiches',   '🫘', '#f7fee7', '#65a30d'],
  ['lentilles',      '🫘', '#f7fee7', '#65a30d'],
  ['haricots blancs','🫘', '#f7fee7', '#65a30d'],
  ['fèves',          '🫘', '#f7fee7', '#65a30d'],
  // Laitiers & œufs
  ['lait',           '🥛', '#EEF6F8', '#1F5F6B'],
  ['yaourt',         '🥣', '#EEF6F8', '#1F5F6B'],
  ['fromage',        '🧀', '#fefce8', '#ca8a04'],
  ['beurre',         '🧈', '#fefce8', '#ca8a04'],
  ['margarine',      '🧈', '#fefce8', '#ca8a04'],
  ['crème',          '🍶', '#EEF6F8', '#1F5F6B'],
  ['œufs',           '🥚', '#fffbeb', '#b45309'],
  ['oeufs',          '🥚', '#fffbeb', '#b45309'],
  // Viandes & poissons
  ['poulet',         '🍗', '#FDF6EC', '#c2410c'],
  ['dinde',          '🍗', '#FDF6EC', '#c2410c'],
  ['kefta',          '🥩', '#FBEDEC', '#9E2A25'],
  ['merguez',        '🌭', '#FBEDEC', '#9E2A25'],
  ['agneau',         '🥩', '#FBEDEC', '#9E2A25'],
  ['veau',           '🥩', '#FBEDEC', '#9E2A25'],
  ['viande',         '🥩', '#FBEDEC', '#9E2A25'],
  ['sardines',       '🐟', '#ecfeff', '#0e7490'],
  ['thon',           '🐟', '#ecfeff', '#0e7490'],
  ['sole',           '🐟', '#ecfeff', '#0e7490'],
  ['crevettes',      '🦐', '#fff1f2', '#be123c'],
  // Légumes
  ['tomates',        '🍅', '#FBEDEC', '#C1272D'],
  ['oignons',        '🧅', '#fdf4ff', '#a21caf'],
  ['pommes de terre','🥔', '#fffbeb', '#b45309'],
  ['carottes',       '🥕', '#FDF6EC', '#C4620F'],
  ['courgettes',     '🥒', '#EEF6F1', '#0F4C3A'],
  ['poivrons',       '🫑', '#EEF6F1', '#0F4C3A'],
  ['aubergines',     '🍆', '#faf5ff', '#7e22ce'],
  ['navets',         '🥬', '#EEF6F1', '#0F4C3A'],
  ['chou',           '🥬', '#EEF6F1', '#0F4C3A'],
  ['epinards',       '🥬', '#EEF6F1', '#0F4C3A'],
  ['épinards',       '🥬', '#EEF6F1', '#0F4C3A'],
  ['haricots verts', '🫛', '#EEF6F1', '#0F4C3A'],
  ['betteraves',     '🥬', '#fdf2f8', '#be185d'],
  ['petits pois',    '🫛', '#EEF6F1', '#0F4C3A'],
  ['ail',            '🧄', '#F2F6F0', '#3C4F47'],
  ['persil',         '🌿', '#EEF6F1', '#0F4C3A'],
  // Fruits
  ['oranges',        '🍊', '#FDF6EC', '#C4620F'],
  ['clémentines',    '🍊', '#FDF6EC', '#C4620F'],
  ['pommes',         '🍎', '#FBEDEC', '#C1272D'],
  ['bananes',        '🍌', '#fefce8', '#ca8a04'],
  ['grenades',       '🍎', '#fff1f2', '#be123c'],
  ['raisins',        '🍇', '#faf5ff', '#7e22ce'],
  ['pastèque',       '🍉', '#EEF6F1', '#0F4C3A'],
  ['dattes',         '🌴', '#fffbeb', '#b45309'],
  ['figues',         '🫒', '#faf5ff', '#7e22ce'],
  // Condiments & sucré
  ['harissa',        '🌶️', '#FBEDEC', '#C1272D'],
  ['concentré',      '🥫', '#FBEDEC', '#C1272D'],
  ['tomates pelées', '🥫', '#FBEDEC', '#C1272D'],
  ['olives',         '🫒', '#f7fee7', '#4d7c0f'],
  ['citrons',        '🍋', '#fefce8', '#ca8a04'],
  ['miel',           '🍯', '#fffbeb', '#b45309'],
  ['confiture',      '🍓', '#fff1f2', '#be123c'],
  ['amlou',          '🥜', '#fffbeb', '#b45309'],
  // Épices
  ['cumin',          '🧂', '#fffbeb', '#b45309'],
  ['paprika',        '🌶️', '#FBEDEC', '#C1272D'],
  ['ras el hanout',  '🧂', '#fffbeb', '#b45309'],
  ['gingembre',      '🫚', '#fffbeb', '#b45309'],
  ['curcuma',        '🧂', '#fffbeb', '#ca8a04'],
  ['cannelle',       '🧂', '#FDF6EC', '#c2410c'],
  ['safran',         '🌺', '#FDF6EC', '#C4620F'],
  ['poivre',         '🧂', '#F2F6F0', '#3C4F47'],
  // Hygiène & entretien
  ['dentifrice',     '🪥', '#EAF3F5', '#256B7A'],
  ['shampooing',     '🧴', '#EAF3F5', '#256B7A'],
  ['savon',          '🧼', '#EAF3F5', '#256B7A'],
  ['gel douche',     '🧴', '#EAF3F5', '#256B7A'],
  ['déodorant',      '🧴', '#EAF3F5', '#256B7A'],
  ['lessive',        '🧺', '#eef2ff', '#4338ca'],
  ['javel',          '🧽', '#eef2ff', '#4338ca'],
  ['vaisselle',      '🧽', '#eef2ff', '#4338ca'],
  ['nettoyant',      '🧽', '#eef2ff', '#4338ca'],
  ['papier toilette','🧻', '#F2F6F0', '#3C4F47'],
  // Bébé
  ['couches',        '👶', '#fdf2f8', '#be185d'],
  ['lingettes',      '👶', '#fdf2f8', '#be185d'],
];

const DEFAULT: [string, string, string] = ['🛒', '#E9F0E6', '#4A5B53'];

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
