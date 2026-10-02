/**
 * Quantités d'une liste de courses.
 *
 * Une quantité n'est pas toujours un compte d'articles : ce qui se vend au
 * poids se note au poids, et le souk vend au demi-kilo. « 1,5 kg de viande »
 * doit donc s'afficher, se décrémenter et s'additionner correctement.
 */

/** Deux décimales au plus, virgule française, sans zéro inutile. */
export function formaterQuantite(valeur: number): string {
  if (!Number.isFinite(valeur)) return '1';
  const arrondi = Math.round(valeur * 100) / 100;
  return Number.isInteger(arrondi)
    ? String(arrondi)
    : arrondi.toFixed(2).replace(/0$/, '').replace('.', ',');
}

/**
 * Le pas des boutons + et −.
 *
 * Un entier avance par 1, une quantité au poids par demi-unité : avec un pas
 * de 1, retirer une unité à « 1,5 kg » donnait 0,5 — jugé inférieur au
 * minimum, ce qui supprimait la ligne au lieu de la réduire.
 */
export function pasDeQuantite(valeur: number): number {
  return Number.isInteger(valeur) ? 1 : 0.5;
}

/** La quantité après un appui sur + ou −. Zéro ou moins signifie « retirer ». */
export function quantiteSuivante(valeur: number, sens: number): number {
  const suivante = valeur + sens * pasDeQuantite(valeur);
  return Math.round(suivante * 100) / 100;
}
