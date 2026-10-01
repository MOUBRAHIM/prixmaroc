/**
 * DerniersRelevesScreen — ce que la collecte a rapporté cette semaine.
 *
 * La collecte tourne chaque lundi et relève des centaines de prix, qui
 * n'apparaissaient nulle part : il fallait connaître le nom d'un produit pour
 * tomber dessus. Cet écran les montre tels qu'ils arrivent, enseigne par
 * enseigne — on prépare ses courses en voyant ce qui a bougé chez BIM avant
 * d'y aller.
 *
 * Aucun compte n'est demandé : de vrais prix récents sont le meilleur
 * argument pour en créer un.
 */
import React, { useMemo } from 'react';
import {
  View,
  Text,
  SectionList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { PricesAPI } from '@services/api';
import ProductVisual from '@components/ui/ProductVisual';
import BasculeComparer from '@components/BasculeComparer';
import EtatErreur from '@components/EtatErreur';
import { C, Radius } from '@constants/colors';
import { libelleFraicheur } from '@utils/fraicheur';
import type { ComparerStackParamList, ReleveRecent } from '@types/models';

type Props = NativeStackScreenProps<ComparerStackParamList, 'DerniersReleves'>;

const JOURS = 7;

interface Section {
  title: string;
  ville: string | null;
  total: number;
  data: ReleveRecent[];
}

// ── Ligne produit ─────────────────────────────────────────────────────────────

const LigneReleve: React.FC<{
  item: ReleveRecent;
  onPress: () => void;
}> = ({ item, onPress }) => {
  const enPromo = item.promo_price != null;
  const aPayer = enPromo ? item.promo_price! : item.price;

  return (
    <TouchableOpacity style={styles.ligne} onPress={onPress} activeOpacity={0.75}>
      <ProductVisual name={item.product_name} imageUrl={item.product_image} size={52} radius={10} />

      <View style={styles.ligneInfo}>
        <Text style={styles.nom} numberOfLines={2}>{item.product_name}</Text>
        <Text style={styles.detail} numberOfLines={1}>
          {[item.brand, item.unit_size].filter(Boolean).join(' · ') || libelleFraicheur(item.recorded_at)}
        </Text>
      </View>

      <View style={styles.ligneePrix}>
        {enPromo && <Text style={styles.prixBarre}>{item.price.toFixed(2)}</Text>}
        <Text style={[styles.prix, enPromo && { color: C.terre }]}>
          {aPayer.toFixed(2)} MAD
        </Text>
        {enPromo && item.discount_pct != null && (
          <View style={styles.badgePromo}>
            <Text style={styles.badgePromoTexte}>-{Math.round(item.discount_pct)}%</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
};

// ── Écran ─────────────────────────────────────────────────────────────────────

const DerniersRelevesScreen: React.FC<Props> = ({ navigation }) => {
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ['releves-recents', JOURS],
    queryFn: () => PricesAPI.getReleveRecents({ jours: JOURS }),
  });

  const sections: Section[] = useMemo(
    () =>
      (data?.enseignes ?? []).map((e) => ({
        title: e.store_name,
        ville: e.store_city,
        total: e.count,
        data: e.produits,
      })),
    [data],
  );

  const resume = data
    ? `${data.count} relevé${data.count > 1 ? 's' : ''} · ${data.enseignes.length} enseigne${
        data.enseignes.length > 1 ? 's' : ''
      }${data.dernier_releve ? ` · ${libelleFraicheur(data.dernier_releve)}` : ''}`
    : '';

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <BasculeComparer actif="DerniersReleves" />
        <View style={styles.centre}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.chargement}>Chargement des relevés…</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <BasculeComparer actif="DerniersReleves" />
        <EtatErreur
          titre="Impossible de charger les relevés"
          error={error}
          onRetry={() => refetch()}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <BasculeComparer actif="DerniersReleves" />

      <SectionList
        sections={sections}
        keyExtractor={(item) => `${item.product_id}-${item.recorded_at}`}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={styles.contenu}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />
        }
        ListHeaderComponent={
          resume ? (
            <View style={styles.resumeBloc}>
              <Text style={styles.resumeTitre}>Relevés des {JOURS} derniers jours</Text>
              <Text style={styles.resumeTexte}>{resume}</Text>
            </View>
          ) : null
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.enteteEnseigne}>
            <Ionicons name="storefront" size={16} color={C.primary} />
            <Text style={styles.enseigneNom}>{section.title}</Text>
            {section.ville ? <Text style={styles.enseigneVille}>{section.ville}</Text> : null}
            <View style={styles.compteur}>
              <Text style={styles.compteurTexte}>{section.total}</Text>
            </View>
          </View>
        )}
        renderSectionFooter={({ section }) =>
          // Le compteur dit le total de l'enseigne ; la liste peut être tronquée.
          section.total > section.data.length ? (
            <Text style={styles.reste}>
              + {section.total - section.data.length} autres relevés chez {section.title}
            </Text>
          ) : null
        }
        renderItem={({ item }) => (
          <LigneReleve
            item={item}
            onPress={() =>
              navigation.navigate('ProduitDetail', {
                productId: item.product_id,
                productName: item.product_name,
              })
            }
          />
        )}
        ListEmptyComponent={
          <View style={styles.vide}>
            <Ionicons name="time-outline" size={46} color={C.textMuted} />
            <Text style={styles.videTitre}>Aucun relevé cette semaine</Text>
            <Text style={styles.videTexte}>
              La collecte tourne chaque lundi. Les prix des derniers {JOURS} jours
              apparaîtront ici dès le prochain passage.
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: C.bg },
  centre: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  chargement: { color: C.textSub, fontSize: 15 },
  contenu: { paddingBottom: 32 },

  resumeBloc: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 12, gap: 2 },
  resumeTitre: { fontSize: 19, fontWeight: '800', color: C.text },
  resumeTexte: { fontSize: 13, color: C.textSub },

  enteteEnseigne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 8,
  },
  enseigneNom: { fontSize: 16, fontWeight: '800', color: C.text },
  enseigneVille: { fontSize: 12, color: C.textMuted, flex: 1 },
  compteur: {
    minWidth: 26,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: Radius.pill,
    backgroundColor: C.primaryLight,
    alignItems: 'center',
  },
  compteurTexte: { fontSize: 12, fontWeight: '700', color: C.primary },

  ligne: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    backgroundColor: C.card,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: C.border,
  },
  ligneInfo: { flex: 1, gap: 3 },
  nom: { fontSize: 14, fontWeight: '600', color: C.text, lineHeight: 19 },
  detail: { fontSize: 12, color: C.textMuted },

  ligneePrix: { alignItems: 'flex-end', gap: 2 },
  prixBarre: {
    fontSize: 12,
    color: C.textMuted,
    textDecorationLine: 'line-through',
  },
  prix: { fontSize: 15, fontWeight: '800', color: C.primary },
  badgePromo: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: Radius.sm,
    backgroundColor: '#FCEDE9',
  },
  badgePromoTexte: { fontSize: 11, fontWeight: '800', color: C.terre },

  reste: {
    marginHorizontal: 16,
    marginTop: 2,
    fontSize: 12,
    color: C.textMuted,
    fontStyle: 'italic',
  },

  vide: { alignItems: 'center', paddingTop: 70, paddingHorizontal: 36, gap: 10 },
  videTitre: { fontSize: 17, fontWeight: '800', color: C.text },
  videTexte: { fontSize: 14, color: C.textSub, textAlign: 'center', lineHeight: 20 },
});

export default DerniersRelevesScreen;
