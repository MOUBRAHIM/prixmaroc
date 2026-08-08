/**
 * DetailScanScreen — Détail d'un ticket de caisse scanné.
 *
 * Affiche le magasin reconnu, la date, les articles détectés avec leurs prix,
 * le total, et le texte brut lu par l'OCR (repliable, utile quand la lecture
 * est imparfaite).
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  TouchableOpacity, RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { OcrAPI } from '@services/api';
import { C, Radius } from '@constants/colors';
import type { ProfilStackParamList, OcrScanItem } from '@types/models';

type Props = NativeStackScreenProps<ProfilStackParamList, 'DetailScan'>;

const STATUTS: Record<string, { libelle: string; couleur: string; fond: string; icone: string }> = {
  done:       { libelle: 'Analysé',       couleur: '#0F4C3A', fond: '#EEF6F1', icone: 'checkmark-circle' },
  processing: { libelle: 'En cours',      couleur: '#8A6410', fond: '#FDF3DE', icone: 'time' },
  pending:    { libelle: 'En attente',    couleur: '#8A6410', fond: '#FDF3DE', icone: 'hourglass' },
  failed:     { libelle: 'Échec',         couleur: '#C1272D', fond: '#FBE9E6', icone: 'alert-circle' },
};

const prix = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)} MAD`);

// ── Ligne d'article ───────────────────────────────────────────────────────────
const LigneArticle: React.FC<{ article: OcrScanItem }> = ({ article }) => (
  <View style={s.ligne}>
    <View style={{ flex: 1 }}>
      <Text style={s.ligneNom} numberOfLines={2}>{article.name}</Text>
      <Text style={s.ligneDetail}>
        {article.quantity > 1 ? `${article.quantity} × ${prix(article.unit_price)}` : prix(article.unit_price)}
        {article.is_promo ? '  ·  promo' : ''}
      </Text>
    </View>
    <Text style={s.lignePrix}>{prix(article.total_price)}</Text>
  </View>
);

// ── Écran ─────────────────────────────────────────────────────────────────────
const DetailScanScreen: React.FC<Props> = ({ route }) => {
  const { scanId } = route.params;
  const [texteVisible, setTexteVisible] = useState(false);

  const { data: scan, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => OcrAPI.getScan(scanId),
  });

  if (isLoading) {
    return (
      <View style={s.centre}>
        <ActivityIndicator size="large" color={C.primary} />
        <Text style={s.chargement}>Chargement du ticket…</Text>
      </View>
    );
  }

  if (isError || !scan) {
    return (
      <View style={s.centre}>
        <Ionicons name="cloud-offline-outline" size={40} color="#8A9A92" />
        <Text style={s.videTitre}>Ticket introuvable</Text>
        <TouchableOpacity style={s.boutonReessayer} onPress={() => refetch()}>
          <Text style={s.boutonReessayerTexte}>Réessayer</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const st = STATUTS[scan.status] ?? STATUTS.pending;
  const donnees = scan.parsed_data;
  const articles = donnees?.items ?? [];
  const magasin = donnees?.store?.name ?? donnees?.store?.chain ?? 'Magasin non reconnu';
  const sommeArticles = articles.reduce((t, a) => t + (a.total_price || 0), 0);
  const total = donnees?.total ?? sommeArticles;
  const dateScan = new Date(scan.created_at).toLocaleDateString('fr-MA', {
    day: '2-digit', month: 'long', year: 'numeric',
  });
  const heureScan = new Date(scan.created_at).toLocaleTimeString('fr-MA', {
    hour: '2-digit', minute: '2-digit',
  });

  return (
    <ScrollView
      style={s.racine}
      contentContainerStyle={s.contenu}
      refreshControl={<RefreshControl refreshing={isFetching} onRefresh={refetch} colors={[C.primary]} />}
    >
      {/* En-tête ticket */}
      <View style={s.carteEntete}>
        <View style={s.enteteHaut}>
          <View style={{ flex: 1 }}>
            <Text style={s.magasin} numberOfLines={2}>{magasin}</Text>
            <Text style={s.dateTexte}>{dateScan} · {heureScan}</Text>
          </View>
          <View style={[s.badge, { backgroundColor: st.fond }]}>
            <Ionicons name={st.icone as never} size={13} color={st.couleur} />
            <Text style={[s.badgeTexte, { color: st.couleur }]}>{st.libelle}</Text>
          </View>
        </View>

        <View style={s.separateur} />

        <View style={s.totauxRangee}>
          <View>
            <Text style={s.totalLabel}>Total du ticket</Text>
            <Text style={s.totalValeur}>{prix(total)}</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={s.totalLabel}>Articles reconnus</Text>
            <Text style={s.articlesNombre}>{articles.length}</Text>
          </View>
        </View>

        {donnees?.confirmed && (
          <View style={s.confirme}>
            <Ionicons name="shield-checkmark" size={14} color="#0F4C3A" />
            <Text style={s.confirmeTexte}>
              Ticket confirmé · {donnees.prices_saved ?? 0} prix enregistrés
            </Text>
          </View>
        )}
      </View>

      {/* Erreur éventuelle */}
      {scan.status === 'failed' && scan.error_message && (
        <View style={s.carteErreur}>
          <Ionicons name="alert-circle-outline" size={18} color="#C1272D" />
          <Text style={s.erreurTexte}>{scan.error_message}</Text>
        </View>
      )}

      {/* Articles */}
      <Text style={s.sectionTitre}>Articles</Text>
      {articles.length > 0 ? (
        <View style={s.carteArticles}>
          {articles.map((a, i) => <LigneArticle key={`${a.name}-${i}`} article={a} />)}
          <View style={s.separateur} />
          <View style={s.sommeRangee}>
            <Text style={s.sommeLabel}>Somme des articles</Text>
            <Text style={s.sommeValeur}>{prix(sommeArticles)}</Text>
          </View>
          {Math.abs(sommeArticles - (donnees?.total ?? sommeArticles)) > 0.5 && (
            <Text style={s.avertissement}>
              La somme des articles diffère du total lu sur le ticket : certaines lignes
              n'ont pas été reconnues.
            </Text>
          )}
        </View>
      ) : (
        <View style={s.vide}>
          <Text style={s.videEmoji}>🧾</Text>
          <Text style={s.videTitre}>Aucun article reconnu</Text>
          <Text style={s.videTexte}>
            La lecture n'a rien pu extraire. Une photo bien à plat, nette et cadrée
            sur le ticket améliore nettement le résultat.
          </Text>
        </View>
      )}

      {/* Texte brut OCR */}
      {scan.raw_text ? (
        <>
          <TouchableOpacity
            style={s.basculeTexte}
            onPress={() => setTexteVisible((v) => !v)}
            activeOpacity={0.7}
          >
            <Ionicons name="document-text-outline" size={16} color={C.primary} />
            <Text style={s.basculeTexteLabel}>
              {texteVisible ? 'Masquer le texte lu' : 'Voir le texte lu par l\'OCR'}
            </Text>
            <Ionicons name={texteVisible ? 'chevron-up' : 'chevron-down'} size={16} color={C.primary} />
          </TouchableOpacity>
          {texteVisible && (
            <View style={s.carteTexte}>
              <Text style={s.texteBrut}>{scan.raw_text}</Text>
            </View>
          )}
        </>
      ) : null}

      <View style={{ height: 28 }} />
    </ScrollView>
  );
};

const s = StyleSheet.create({
  racine: { flex: 1, backgroundColor: '#F2F6F0' },
  contenu: { padding: 16 },
  centre: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F2F6F0', gap: 10, padding: 24 },
  chargement: { fontSize: 14, color: '#4A5B53' },

  carteEntete: {
    backgroundColor: '#fff', borderRadius: Radius.lg, padding: 16,
    shadowColor: '#0B2019', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.06, shadowRadius: 14, elevation: 2,
  },
  enteteHaut: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  magasin: { fontSize: 17, fontWeight: '800', color: '#0B2019' },
  dateTexte: { fontSize: 12.5, color: '#8A9A92', marginTop: 3 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 5, borderRadius: Radius.pill, paddingHorizontal: 10, paddingVertical: 4 },
  badgeTexte: { fontSize: 11.5, fontWeight: '700' },
  separateur: { height: 1, backgroundColor: '#E2E9DF', marginVertical: 14 },
  totauxRangee: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  totalLabel: { fontSize: 11.5, color: '#8A9A92', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.3 },
  totalValeur: { fontSize: 26, fontWeight: '900', color: C.primary, marginTop: 4, letterSpacing: -0.5 },
  articlesNombre: { fontSize: 22, fontWeight: '800', color: '#0B2019', marginTop: 4 },
  confirme: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#EEF6F1', borderRadius: Radius.sm, padding: 9, marginTop: 12 },
  confirmeTexte: { fontSize: 12.5, color: '#0F4C3A', fontWeight: '600' },

  carteErreur: {
    flexDirection: 'row', gap: 9, alignItems: 'flex-start',
    backgroundColor: '#FBE9E6', borderRadius: Radius.md, padding: 12, marginTop: 12,
  },
  erreurTexte: { flex: 1, fontSize: 13, color: '#C1272D', lineHeight: 18 },

  sectionTitre: { fontSize: 15, fontWeight: '800', color: '#0B2019', marginTop: 20, marginBottom: 10 },
  carteArticles: {
    backgroundColor: '#fff', borderRadius: Radius.lg, padding: 4,
    shadowColor: '#0B2019', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.06, shadowRadius: 14, elevation: 2,
  },
  ligne: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12, paddingVertical: 11 },
  ligneNom: { fontSize: 14, fontWeight: '600', color: '#0B2019', lineHeight: 19 },
  ligneDetail: { fontSize: 12, color: '#8A9A92', marginTop: 2 },
  lignePrix: { fontSize: 15, fontWeight: '800', color: C.primary },
  sommeRangee: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 12, paddingBottom: 12 },
  sommeLabel: { fontSize: 13, color: '#4A5B53', fontWeight: '600' },
  sommeValeur: { fontSize: 15, fontWeight: '800', color: '#0B2019' },
  avertissement: { fontSize: 11.5, color: '#8A6410', backgroundColor: '#FDF3DE', borderRadius: Radius.sm, padding: 9, margin: 8, lineHeight: 16 },

  vide: { alignItems: 'center', backgroundColor: '#fff', borderRadius: Radius.lg, padding: 26, gap: 8 },
  videEmoji: { fontSize: 36 },
  videTitre: { fontSize: 15, fontWeight: '700', color: '#0B2019' },
  videTexte: { fontSize: 13, color: '#4A5B53', textAlign: 'center', lineHeight: 19 },

  basculeTexte: {
    flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'center',
    marginTop: 18, paddingVertical: 12,
    borderWidth: 1.5, borderColor: C.primary, borderRadius: Radius.md,
  },
  basculeTexteLabel: { flex: 1, fontSize: 13.5, fontWeight: '700', color: C.primary },
  carteTexte: { backgroundColor: '#fff', borderRadius: Radius.md, padding: 14, marginTop: 8 },
  texteBrut: { fontSize: 12, color: '#3C4F47', lineHeight: 18, fontFamily: 'monospace' },

  boutonReessayer: { borderWidth: 1.5, borderColor: C.primary, borderRadius: Radius.md, paddingHorizontal: 18, paddingVertical: 9, marginTop: 6 },
  boutonReessayerTexte: { color: C.primary, fontWeight: '700', fontSize: 13.5 },
});

export default DetailScanScreen;
