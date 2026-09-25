/**
 * CarteWeb — carte des magasins dans le navigateur.
 *
 * react-native-maps ne fonctionne pas sur le web : sa version navigateur
 * n'existe pas. On s'appuie donc sur Leaflet et les fonds OpenStreetMap —
 * gratuits, sans clé API, et suffisants pour situer des magasins.
 *
 * Leaflet est chargé à la demande depuis cdnjs, au premier affichage de la
 * carte : les utilisateurs qui n'ouvrent jamais cet écran ne le téléchargent
 * pas, et l'application mobile n'en embarque rien.
 */
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';

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
  /** Magasin à mettre en avant (touché dans la liste) ; `nonce` force le recentrage. */
  focus?: { lat: number; lng: number; nonce: number } | null;
}

const VERSION = '1.9.4';
const CDN = `https://cdnjs.cloudflare.com/ajax/libs/leaflet/${VERSION}`;
const BLEU_POSITION = '#2F6FE0';

// Un seul chargement pour toute la session, même si l'écran est rouvert.
let chargement: Promise<any> | null = null;

function chargerLeaflet(): Promise<any> {
  const w = window as any;
  if (w.L) return Promise.resolve(w.L);
  if (chargement) return chargement;

  chargement = new Promise((resolve, reject) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = `${CDN}/leaflet.min.css`;
    document.head.appendChild(css);

    const js = document.createElement('script');
    js.src = `${CDN}/leaflet.min.js`;
    js.async = true;
    js.onload = () => resolve(w.L);
    js.onerror = () => {
      chargement = null;           // un nouvel essai reste possible
      reject(new Error('Leaflet indisponible'));
    };
    document.head.appendChild(js);
  });
  return chargement;
}

function echapper(t: string): string {
  return t.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c] as string));
}

export default function CarteWeb({ centre, magasins, onBasculer, focus }: Props) {
  const conteneur = useRef<HTMLDivElement | null>(null);
  const carte = useRef<any>(null);
  const calque = useRef<any>(null);
  const dejaCadree = useRef(false);
  // Le gestionnaire de clic est créé une fois par marqueur : il doit lire la
  // dernière version du rappel, pas celle du premier rendu.
  const rappel = useRef(onBasculer);
  rappel.current = onBasculer;

  const [etat, setEtat] = useState<'chargement' | 'prete' | 'erreur'>('chargement');

  // ── Création de la carte ──────────────────────────────────────────────────
  useEffect(() => {
    let annule = false;
    chargerLeaflet()
      .then((L) => {
        if (annule || !conteneur.current || carte.current) return;
        const m = L.map(conteneur.current, { zoomControl: true, attributionControl: true })
          .setView([centre.lat, centre.lng], 13);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '© contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(m);
        calque.current = L.layerGroup().addTo(m);
        carte.current = m;
        setEtat('prete');
      })
      .catch(() => { if (!annule) setEtat('erreur'); });

    return () => {
      annule = true;
      carte.current?.remove();
      carte.current = null;
      calque.current = null;
      dejaCadree.current = false;
    };
    // La carte se crée une fois ; les déplacements passent par les effets suivants.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Marqueurs ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const L = (window as any).L;
    const m = carte.current;
    const g = calque.current;
    if (etat !== 'prete' || !L || !m || !g) return;

    g.clearLayers();

    L.circleMarker([centre.lat, centre.lng], {
      radius: 8, color: '#FFFFFF', weight: 3, fillColor: BLEU_POSITION, fillOpacity: 1,
    }).bindTooltip('Vous êtes ici').addTo(g);

    const points: [number, number][] = [[centre.lat, centre.lng]];
    for (const s of magasins) {
      points.push([s.lat, s.lng]);
      const marqueur = L.circleMarker([s.lat, s.lng], {
        radius: s.selectionne ? 12 : 9,
        color: s.selectionne ? '#14211B' : '#FFFFFF',
        weight: s.selectionne ? 3 : 2,
        fillColor: s.couleur,
        fillOpacity: 0.95,
      });
      const ville = s.ville ? ` · ${echapper(s.ville)}` : '';
      marqueur.bindTooltip(
        `<strong>${echapper(s.nom)}</strong>${ville}<br>${s.nbProduits} produits`,
        { direction: 'top', offset: [0, -8] },
      );
      marqueur.on('click', () => rappel.current(s.id));
      marqueur.addTo(g);
    }

    // On cadre une seule fois : recadrer à chaque sélection ferait sauter
    // la vue sous le doigt de l'utilisateur.
    if (!dejaCadree.current) {
      if (points.length > 1) m.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
      dejaCadree.current = true;
    }
  }, [etat, magasins, centre.lat, centre.lng]);

  // ── Recentrage sur un magasin touché dans la liste ────────────────────────
  useEffect(() => {
    if (etat === 'prete' && focus && carte.current) {
      carte.current.flyTo([focus.lat, focus.lng], 16, { duration: 0.6 });
    }
  }, [etat, focus]);

  return (
    <View style={StyleSheet.absoluteFill}>
      <div ref={conteneur} style={{ position: 'absolute', inset: 0 }} />
      {etat !== 'prete' && (
        <View style={styles.voile} pointerEvents="none">
          <Text style={styles.voileTexte}>
            {etat === 'chargement'
              ? 'Chargement de la carte…'
              : 'Carte indisponible — vérifiez votre connexion. La liste reste utilisable.'}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  voile: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F3EDE3',
    paddingHorizontal: 24,
  },
  voileTexte: { color: '#5A6A61', fontSize: 14, textAlign: 'center' },
});
