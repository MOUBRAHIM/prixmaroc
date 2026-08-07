/**
 * Corrige l'export web : sort les polices d'icônes de `assets/node_modules/`.
 *
 * Pourquoi : `expo export --platform web` place les polices sous
 *   dist/assets/node_modules/@expo/vector-icons/.../Fonts/Ionicons.<hash>.ttf
 * Or les hébergeurs statiques (Netlify, Vercel…) ignorent tout chemin contenant
 * `node_modules`. Les polices n'étaient donc jamais déployées : chaque icône
 * s'affichait en carré vide, alors que les emoji passaient.
 *
 * Ce script déplace `assets/node_modules/**` vers `assets/vendor/**` puis
 * réécrit les références correspondantes dans les bundles JS.
 *
 * Usage : node scripts/fix-web-fonts.mjs [dossier_dist]
 */
import { readdirSync, readFileSync, writeFileSync, renameSync, mkdirSync, existsSync, statSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';

const DIST = process.argv[2] ?? 'dist';
const FROM = 'assets/node_modules';
const TO = 'assets/vendor';

function walk(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((entry) => {
    const p = join(dir, entry);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

const src = join(DIST, 'node_modules'.length ? FROM : FROM);
if (!existsSync(src)) {
  console.log(`[fix-web-fonts] rien à faire : ${src} absent`);
  process.exit(0);
}

// 1. Déplacer les fichiers
const fichiers = walk(src);
let deplaces = 0;
for (const f of fichiers) {
  const dest = f.replace(join(DIST, FROM), join(DIST, TO));
  mkdirSync(dirname(dest), { recursive: true });
  renameSync(f, dest);
  deplaces++;
}

// 1b. Supprimer l'arborescence vide restante (elle ne serait pas déployée)
rmSync(src, { recursive: true, force: true });

// 2. Réécrire les références dans les bundles JS
const bundles = walk(join(DIST, '_expo')).filter((f) => f.endsWith('.js'));
let reecrits = 0;
let occurrences = 0;
for (const b of bundles) {
  const avant = readFileSync(b, 'utf8');
  const apres = avant.split(`/${FROM}/`).join(`/${TO}/`);
  if (apres !== avant) {
    occurrences += avant.split(`/${FROM}/`).length - 1;
    writeFileSync(b, apres, 'utf8');
    reecrits++;
  }
}

console.log(
  `[fix-web-fonts] ${deplaces} fichiers déplacés vers ${TO} · ` +
  `${occurrences} références réécrites dans ${reecrits} bundle(s)`
);
