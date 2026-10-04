/**
 * Préparer une photo avant de l'envoyer au serveur.
 *
 * L'appareil photo d'un téléphone récent produit un JPEG de plusieurs
 * mégaoctets. Envoyé tel quel depuis un navigateur, l'appel dépassait la
 * limite du serveur ou se faisait couper en route, et l'application affichait
 * « Serveur injoignable » alors que le serveur allait très bien.
 *
 * Un ticket de caisse reste parfaitement lisible à 1600 px de côté : on
 * réduit donc avant d'envoyer. L'envoi devient rapide, la lecture aussi, et
 * l'appel au modèle coûte moins cher.
 *
 * La réduction ne doit jamais empêcher l'envoi : si quoi que ce soit échoue,
 * on repart sur l'image d'origine.
 */
import { Platform } from 'react-native';

/** Au-delà, le texte d'un ticket n'y gagne plus rien. */
const COTE_MAX = 1600;
const QUALITE = 0.82;

/** En dessous, réduire ne rapporterait rien. */
const TAILLE_ACCEPTABLE = 1_200_000;

/** Refus côté serveur à 10 Mo : on s'arrête avant, avec une phrase utile. */
export const TAILLE_MAX = 10 * 1024 * 1024;

async function dimensions(blob: Blob): Promise<{ l: number; h: number; source: CanvasImageSource } | null> {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(blob);
    return { l: bitmap.width, h: bitmap.height, source: bitmap };
  }
  // Safari ancien : pas de createImageBitmap.
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const e = new Image();
      e.onload = () => resolve(e);
      e.onerror = () => reject(new Error('image illisible'));
      e.src = url;
    });
    return { l: img.naturalWidth, h: img.naturalHeight, source: img };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function reduire(blob: Blob): Promise<Blob | null> {
  const infos = await dimensions(blob);
  if (!infos) return null;

  const cote = Math.max(infos.l, infos.h);
  if (cote <= COTE_MAX && blob.size <= TAILLE_ACCEPTABLE) return null;

  const facteur = Math.min(1, COTE_MAX / cote);
  const toile = document.createElement('canvas');
  toile.width = Math.round(infos.l * facteur);
  toile.height = Math.round(infos.h * facteur);

  const contexte = toile.getContext('2d');
  if (!contexte) return null;
  contexte.drawImage(infos.source, 0, 0, toile.width, toile.height);

  const reduit = await new Promise<Blob | null>((resolve) =>
    toile.toBlob(resolve, 'image/jpeg', QUALITE),
  );
  // Une réduction qui alourdit n'en est pas une.
  return reduit && reduit.size < blob.size ? reduit : null;
}

/**
 * Le contenu à envoyer pour cette photo, réduit quand c'est utile.
 * Lève seulement si l'image est inexploitable ou reste trop lourde.
 */
export async function contenuPourEnvoi(uri: string): Promise<Blob> {
  const original = await (await fetch(uri)).blob();
  if (original.size === 0) {
    throw new Error("L'image est vide. Reprenez la photo.");
  }

  let envoi = original;
  if (Platform.OS === 'web') {
    try {
      envoi = (await reduire(original)) ?? original;
    } catch {
      envoi = original;          // jamais bloquer l'envoi pour un redimensionnement
    }
  }

  if (envoi.size > TAILLE_MAX) {
    throw new Error(
      "La photo est trop lourde. Réduisez la définition de l'appareil photo, "
      + 'ou cadrez de plus près.',
    );
  }
  return envoi;
}
