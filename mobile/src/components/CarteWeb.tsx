/**
 * CarteWeb — version mobile : rien.
 *
 * Sur téléphone, la carte native (react-native-maps) s'en charge. Ce fichier
 * existe pour que l'import se résolve ; Metro choisit CarteWeb.web.tsx dans
 * le navigateur.
 */
export interface MagasinCarte {
  id: number;
  nom: string;
  ville: string | null;
  lat: number;
  lng: number;
  couleur: string;
  nbProduits: number;
  selectionne: boolean;
}

interface Props {
  centre: { lat: number; lng: number };
  magasins: MagasinCarte[];
  onBasculer: (id: number) => void;
  focus?: { lat: number; lng: number; nonce: number } | null;
}

export default function CarteWeb(_props: Props) {
  return null;
}
