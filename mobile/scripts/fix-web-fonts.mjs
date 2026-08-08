/**
 * Corrige l'export web : rend les polices d'icônes réellement déployables.
 *
 * Problème constaté en production (Netlify) : `expo export --platform web`
 * range les polices sous
 *   dist/assets/node_modules/@expo/vector-icons/.../Fonts/Ionicons.<hash>.ttf
 * Ce chemin cumule deux éléments que les hébergeurs statiques gèrent mal :
 *   • `node_modules`, souvent exclu des déploiements ;
 *   • un segment commençant par `@`.
 * Résultat : les .ttf n'étaient pas servis (réponse = index.html), donc chaque
 * icône s'affichait en carré vide, alors que les emoji passaient.
 *
 * Correctif : on aplatit toutes les polices dans `dist/fonts/` (nom de fichier
 * seul, aucun sous-dossier, aucun `@`) puis on réécrit les références dans les
 * bundles JS. On ajoute enfin une règle _redirects explicite pour que la route
 * de repli SPA n'intercepte jamais /fonts/.
 *
 * Usage : node scripts/fix-web-fonts.mjs [dossier_dist]
 */
import {
  readdirSync, readFileSync, writeFileSync, copyFileSync,
  mkdirSync, existsSync, statSync, rmSync, renameSync,
} from 'node:fs';
import { join, basename, dirname } from 'node:path';
import { createHash } from 'node:crypto';

const DIST = process.argv[2] ?? 'dist';
const ASSETS = join(DIST, 'assets');
const FONTS = join(DIST, 'fonts');

function walk(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((e) => {
    const p = join(dir, e);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

if (!existsSync(ASSETS)) {
  console.log(`[fix-web-fonts] rien à faire : ${ASSETS} absent`);
  process.exit(0);
}

// 1. Aplatir toutes les polices dans dist/fonts/
mkdirSync(FONTS, { recursive: true });
const polices = walk(ASSETS).filter((f) => /\.(ttf|otf|woff2?)$/i.test(f));
const correspondances = new Map(); // ancien chemin URL -> nouveau chemin URL

for (const f of polices) {
  const nom = basename(f);
  copyFileSync(f, join(FONTS, nom));
  const urlAncienne = '/' + f.replace(/\\/g, '/').replace(DIST.replace(/\\/g, '/') + '/', '');
  correspondances.set(urlAncienne, `/fonts/${nom}`);
}

// 2. Réécrire les références dans les bundles JS
const bundles = walk(join(DIST, '_expo')).filter((f) => f.endsWith('.js'));
let reecrites = 0;
for (const b of bundles) {
  let texte = readFileSync(b, 'utf8');
  let modifie = false;
  for (const [avant, apres] of correspondances) {
    if (texte.includes(avant)) {
      texte = texte.split(avant).join(apres);
      reecrites++;
      modifie = true;
    }
  }
  if (modifie) writeFileSync(b, texte, 'utf8');
}

// 3. Supprimer l'ancienne arborescence (non déployable de toute façon)
rmSync(ASSETS, { recursive: true, force: true });

// 3b. Renommer les bundles modifiés selon leur NOUVEAU contenu.
//     Indispensable : le hash du nom est calculé par expo AVANT cette
//     réécriture. Sans renommage, le CDN et le navigateur continuent de servir
//     l'ancien bundle (même nom de fichier) et les polices restent introuvables.
const indexHtml = join(DIST, 'index.html');
let html = existsSync(indexHtml) ? readFileSync(indexHtml, 'utf8') : '';
let renommes = 0;

for (const b of bundles) {
  const contenu = readFileSync(b);
  const nouveauHash = createHash('md5').update(contenu).digest('hex');
  const nom = basename(b);
  const remplace = nom.replace(/-([a-f0-9]{32})\.js$/, `-${nouveauHash}.js`);
  if (remplace === nom) continue;              // pas de hash reconnaissable
  renameSync(b, join(dirname(b), remplace));
  html = html.split(nom).join(remplace);
  renommes++;
}
if (html) writeFileSync(indexHtml, html, 'utf8');

// 4. Garantir que la route SPA n'avale pas /fonts/
const redirects = join(DIST, '_redirects');
const regles = ['/fonts/*  /fonts/:splat  200', '/*  /index.html  200', ''].join('\n');
writeFileSync(redirects, regles, 'utf8');

console.log(
  `[fix-web-fonts] ${polices.length} polices aplaties dans /fonts · ` +
  `${reecrites} références réécrites · ${renommes} bundle(s) renommé(s) · _redirects mis à jour`
);
