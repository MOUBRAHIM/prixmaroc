/**
 * erreurs.ts — Traduire une erreur réseau en phrase utile.
 *
 * Les écrans affichaient chacun leur propre message générique — « Impossible
 * de lancer le scraper bim. » — en jetant celui du serveur. L'utilisateur
 * voyait donc « impossible » là où le serveur disait « accès réservé aux
 * administrateurs » : un refus de droits passait pour une panne.
 *
 * Cette fonction rend, dans l'ordre : le message du serveur s'il y en a un,
 * sinon une explication tirée du code d'état, sinon la cause réseau.
 */
import axios from 'axios';

const PAR_STATUT: Record<number, string> = {
  400: 'Requête invalide.',
  401: 'Session expirée. Reconnectez-vous.',
  403: 'Action réservée aux administrateurs.',
  404: 'Introuvable.',
  409: 'Cette action a déjà été faite.',
  413: 'Fichier trop volumineux.',
  415: 'Format de fichier non accepté.',
  422: 'Données incomplètes ou mal formées.',
  429: 'Trop de demandes. Patientez un instant.',
  500: 'Le serveur a rencontré une erreur.',
  502: 'Le serveur est en cours de redémarrage.',
  503: 'Service momentanément indisponible.',
};

/**
 * Messages par défaut de FastAPI : de l'anglais technique, affiché tel quel à
 * un utilisateur francophone (« Not authenticated »). On les ignore au profit
 * de nos propres phrases ; les détails écrits pour l'utilisateur, eux, passent.
 */
const BOILERPLATE = new Set([
  'not authenticated',
  'could not validate credentials',
  'not found',
  'forbidden',
  'unauthorized',
  'bad request',
  'internal server error',
  'unprocessable entity',
]);

export function messageErreur(err: unknown, defaut = 'Une erreur est survenue.'): string {
  if (!axios.isAxiosError(err)) {
    return err instanceof Error && err.message ? err.message : defaut;
  }

  // Le serveur explique souvent lui-même ce qui bloque : on le préfère.
  const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === 'string' && detail.trim() && !BOILERPLATE.has(detail.trim().toLowerCase())) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length) {
    const premier = detail[0] as { msg?: string };
    if (premier?.msg) return premier.msg;
  }

  if (err.response) {
    return PAR_STATUT[err.response.status] ?? `${defaut} (code ${err.response.status})`;
  }
  if (err.code === 'ECONNABORTED') {
    return "Le serveur met trop de temps à répondre. Il se réveille : réessayez dans une minute.";
  }
  return 'Serveur injoignable. Vérifiez votre connexion.';
}
