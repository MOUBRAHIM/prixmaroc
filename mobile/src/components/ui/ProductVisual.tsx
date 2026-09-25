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
  ['coca',           '🥤', '#FCEDE9', '#D0402F'],
  ['pepsi',          '🥤', '#EAF3F5', '#256B7A'],
  ['ice tea',        '🧊', '#fefce8', '#ca8a04'],
  ["jus d'orange",   '🍹', '#FDF6EC', '#C4620F'],
  ['jus',            '🧃', '#FDF6EC', '#C4620F'],
  ['café',           '☕', '#f5f1ed', '#78350f'],
  ['thé',            '🍵', '#E4F1EA', '#0A4835'],
  // Épicerie de base
  ["huile d'olive",  '🫒', '#f7fee7', '#4d7c0f'],
  ['huile',          '🫗', '#fefce8', '#8A6410'],
  ['sucre',          '🍬', '#fdf4ff', '#a21caf'],
  ['sel',            '🧂', '#FBF7F1', '#47564F'],
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
  ['kefta',          '🥩', '#FCEDE9', '#9E2A25'],
  ['merguez',        '🌭', '#FCEDE9', '#9E2A25'],
  ['agneau',         '🥩', '#FCEDE9', '#9E2A25'],
  ['veau',           '🥩', '#FCEDE9', '#9E2A25'],
  ['viande',         '🥩', '#FCEDE9', '#9E2A25'],
  ['sardines',       '🐟', '#ecfeff', '#0e7490'],
  ['thon',           '🐟', '#ecfeff', '#0e7490'],
  ['sole',           '🐟', '#ecfeff', '#0e7490'],
  ['crevettes',      '🦐', '#fff1f2', '#be123c'],
  // Légumes
  ['tomates',        '🍅', '#FCEDE9', '#D0402F'],
  ['oignons',        '🧅', '#fdf4ff', '#a21caf'],
  ['pommes de terre','🥔', '#fffbeb', '#b45309'],
  ['carottes',       '🥕', '#FDF6EC', '#C4620F'],
  ['courgettes',     '🥒', '#E4F1EA', '#0E5C44'],
  ['poivrons',       '🫑', '#E4F1EA', '#0E5C44'],
  ['aubergines',     '🍆', '#faf5ff', '#7e22ce'],
  ['navets',         '🥬', '#E4F1EA', '#0E5C44'],
  ['chou',           '🥬', '#E4F1EA', '#0E5C44'],
  ['epinards',       '🥬', '#E4F1EA', '#0E5C44'],
  ['épinards',       '🥬', '#E4F1EA', '#0E5C44'],
  ['haricots verts', '🫛', '#E4F1EA', '#0E5C44'],
  ['betteraves',     '🥬', '#fdf2f8', '#be185d'],
  ['petits pois',    '🫛', '#E4F1EA', '#0E5C44'],
  ['ail',            '🧄', '#FBF7F1', '#47564F'],
  ['persil',         '🌿', '#E4F1EA', '#0E5C44'],
  // Fruits
  ['oranges',        '🍊', '#FDF6EC', '#C4620F'],
  ['clémentines',    '🍊', '#FDF6EC', '#C4620F'],
  ['pommes',         '🍎', '#FCEDE9', '#D0402F'],
  ['bananes',        '🍌', '#fefce8', '#ca8a04'],
  ['grenades',       '🍎', '#fff1f2', '#be123c'],
  ['raisins',        '🍇', '#faf5ff', '#7e22ce'],
  ['pastèque',       '🍉', '#E4F1EA', '#0E5C44'],
  ['dattes',         '🌴', '#fffbeb', '#b45309'],
  ['figues',         '🫒', '#faf5ff', '#7e22ce'],
  // Condiments & sucré
  ['harissa',        '🌶️', '#FCEDE9', '#D0402F'],
  ['concentré',      '🥫', '#FCEDE9', '#D0402F'],
  ['tomates pelées', '🥫', '#FCEDE9', '#D0402F'],
  ['olives',         '🫒', '#f7fee7', '#4d7c0f'],
  ['citrons',        '🍋', '#fefce8', '#ca8a04'],
  ['miel',           '🍯', '#fffbeb', '#b45309'],
  ['confiture',      '🍓', '#fff1f2', '#be123c'],
  ['amlou',          '🥜', '#fffbeb', '#b45309'],
  // Épices
  ['cumin',          '🧂', '#fffbeb', '#b45309'],
  ['paprika',        '🌶️', '#FCEDE9', '#D0402F'],
  ['ras el hanout',  '🧂', '#fffbeb', '#b45309'],
  ['gingembre',      '🫚', '#fffbeb', '#b45309'],
  ['curcuma',        '🧂', '#fffbeb', '#ca8a04'],
  ['cannelle',       '🧂', '#FDF6EC', '#c2410c'],
  ['safran',         '🌺', '#FDF6EC', '#C4620F'],
  ['poivre',         '🧂', '#FBF7F1', '#47564F'],
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
  ['papier toilette','🧻', '#FBF7F1', '#47564F'],
  // Bébé
  ['couches',        '👶', '#fdf2f8', '#be185d'],
  ['lingettes',      '👶', '#fdf2f8', '#be185d'],
];

const DEFAULT: [string, string, string] = ['🛒', '#F3EDE3', '#5A6A61'];

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
