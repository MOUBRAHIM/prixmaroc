/**
 * fraicheur.ts — Âge d'un relevé de prix.
 *
 * Une application qui promet de comparer les prix et affiche des montants
 * périmés fait perdre de l'argent à qui lui fait confiance. Tant que la
 * collecte automatique n'a pas rattrapé tous les catalogues, l'utilisateur
 * doit au moins voir de quand date ce qu'on lui montre.
 */

export type NiveauFraicheur = 'recent' | 'ancien' | 'perime';

/** Au-delà, un prix de supermarché n'engage plus à grand-chose. */
const JOURS_ANCIEN = 7;
const JOURS_PERIME = 30;

const MS_PAR_JOUR = 86_400_000;

export function joursDepuis(iso: string): number | null {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  // Un relevé daté du futur vient d'une horloge décalée : on le traite comme
  // du jour même plutôt que d'afficher « il y a -3 jours ».
  return Math.max(0, Math.floor((Date.now() - t) / MS_PAR_JOUR));
}

export function niveauFraicheur(iso: string): NiveauFraicheur {
  const j = joursDepuis(iso);
  if (j === null || j > JOURS_PERIME) return 'perime';
  if (j > JOURS_ANCIEN) return 'ancien';
  return 'recent';
}

/**
 * Libellé court affiché sous le prix.
 *
 * En deçà d'un mois on donne l'ancienneté, qui parle tout de suite ; au-delà
 * on donne la date, parce que « il y a 184 jours » ne veut plus rien dire.
 */
export function libelleFraicheur(iso: string): string {
  const j = joursDepuis(iso);
  if (j === null) return 'date inconnue';
  if (j === 0) return "relevé aujourd'hui";
  if (j === 1) return 'relevé hier';
  if (j <= JOURS_PERIME) return `relevé il y a ${j} jours`;

  const d = new Date(iso);
  const jour = d.toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' });
  const memeAnnee = d.getFullYear() === new Date().getFullYear();
  return `relevé le ${jour}${memeAnnee ? '' : ` ${d.getFullYear()}`}`;
}
