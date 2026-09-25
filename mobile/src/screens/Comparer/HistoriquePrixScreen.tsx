import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { ProductsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ComparerStackParamList, PricePoint } from '@types/models';

type Props = NativeStackScreenProps<ComparerStackParamList, 'HistoriquePrix'>;

const PERIODS: { label: string; days: 30 | 90 }[] = [
  { label: '30 jours', days: 30 },
  { label: '90 jours', days: 90 },
];

// ── Mini graphique à barres ───────────────────────────────────────────────────

const MiniBarChart: React.FC<{ points: PricePoint[]; min: number; max: number }> = ({
  points, min, max,
}) => {
  const last20 = points.slice(-20);
  const range = max - min || 1;
  return (
    <View style={chart.container}>
      {last20.map((pt, i) => {
        const height = Math.max(4, ((pt.price - min) / range) * 60 + 4);
        return (
          <View key={i} style={chart.barWrap}>
            <View style={[chart.bar, { height, backgroundColor: pt.is_promo ? '#D0402F' : C.primary }]} />
          </View>
        );
      })}
    </View>
  );
};

const chart = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'flex-end', height: 72, paddingHorizontal: 4, gap: 3 },
  barWrap: { flex: 1, alignItems: 'center', justifyContent: 'flex-end' },
  bar: { width: '100%', borderRadius: 3, minHeight: 4 },
});

// ── Ligne prix ────────────────────────────────────────────────────────────────

const PriceRow: React.FC<{ point: PricePoint; isLast: boolean }> = ({ point, isLast }) => {
  const formatted = new Date(point.date).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' });
  return (
    <View style={[styles.priceRow, !isLast && styles.priceRowBorder]}>
      <Text style={styles.priceRowDate}>{formatted}</Text>
      <Text style={styles.priceRowStore} numberOfLines={1}>{point.store_name}</Text>
      <View style={styles.priceRowRight}>
        {point.is_promo && (
          <View style={styles.promoBadge}><Text style={styles.promoBadgeText}>PROMO</Text></View>
        )}
        <Text style={[styles.priceRowValue, point.is_promo && { color: '#D0402F' }]}>
          {point.price.toFixed(2)} MAD
        </Text>
      </View>
    </View>
  );
};

// ── Écran ─────────────────────────────────────────────────────────────────────

const HistoriquePrixScreen: React.FC<Props> = ({ route }) => {
  const { productId } = route.params;
  const [days, setDays] = useState<30 | 90>(30);

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['price-history', productId, days],
    queryFn: () => ProductsAPI.getPriceHistory(productId, days),
  });

  const sorted = [...(data?.points ?? [])].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <View style={styles.periodBar}>
        {PERIODS.map((p) => (
          <TouchableOpacity
            key={p.days}
            style={[styles.periodBtn, days === p.days && styles.periodBtnActive]}
            onPress={() => setDays(p.days)}
          >
            <Text style={[styles.periodBtnText, days === p.days && styles.periodBtnTextActive]}>
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />}
        contentContainerStyle={styles.content}
      >
        {isLoading && (
          <View style={styles.centered}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Chargement…</Text>
          </View>
        )}

        {isError && (
          <View style={styles.centered}>
            <Ionicons name="alert-circle-outline" size={44} color="#D0402F" />
            <Text style={styles.errorText}>Impossible de charger l'historique</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
              <Text style={styles.retryBtnText}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        )}

        {data && (
          <>
            {/* Stats résumé */}
            <View style={styles.statsCard}>
              <View style={styles.statItem}>
                <Ionicons name="trending-down" size={20} color={C.primary} />
                <Text style={styles.statLabel}>Minimum</Text>
                <Text style={[styles.statValue, { color: C.primary }]}>
                  {data.min_price?.toFixed(2) ?? '—'} MAD
                </Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Ionicons name="stats-chart" size={20} color="#5A6A61" />
                <Text style={styles.statLabel}>Moyen</Text>
                <Text style={styles.statValue}>{data.avg_price?.toFixed(2) ?? '—'} MAD</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Ionicons name="trending-up" size={20} color="#D0402F" />
                <Text style={styles.statLabel}>Maximum</Text>
                <Text style={[styles.statValue, { color: '#D0402F' }]}>
                  {data.max_price?.toFixed(2) ?? '—'} MAD
                </Text>
              </View>
            </View>

            {/* Graphique */}
            {data.points.length > 0 && data.min_price != null && data.max_price != null && (
              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>Évolution — {days} derniers jours</Text>
                <MiniBarChart points={data.points} min={data.min_price} max={data.max_price} />
                <View style={styles.chartLegend}>
                  <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: C.primary }]} />
                    <Text style={styles.legendText}>Prix normal</Text>
                  </View>
                  <View style={styles.legendItem}>
                    <View style={[styles.legendDot, { backgroundColor: '#D0402F' }]} />
                    <Text style={styles.legendText}>Promotion</Text>
                  </View>
                </View>
              </View>
            )}

            {/* Vide */}
            {data.points.length === 0 && (
              <View style={styles.emptyState}>
                <Ionicons name="analytics-outline" size={64} color="#CFC4B3" />
                <Text style={styles.emptyTitle}>Aucun historique</Text>
                <Text style={styles.emptySubtitle}>Pas de données sur les {days} derniers jours.</Text>
              </View>
            )}

            {/* Liste des relevés */}
            {sorted.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>{sorted.length} relevé{sorted.length > 1 ? 's' : ''}</Text>
                <View style={styles.priceList}>
                  <View style={[styles.priceRow, styles.priceRowHeader]}>
                    <Text style={[styles.priceRowDate, styles.headerText]}>Date</Text>
                    <Text style={[styles.priceRowStore, styles.headerText]}>Magasin</Text>
                    <Text style={[styles.priceRowValue, styles.headerText]}>Prix</Text>
                  </View>
                  {sorted.map((pt, i) => (
                    <PriceRow key={i} point={pt} isLast={i === sorted.length - 1} />
                  ))}
                </View>
              </>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#FBF7F1' },
  content: { padding: 16, paddingBottom: 32 },
  periodBar: {
    flexDirection: 'row', backgroundColor: '#fff', padding: 12, gap: 8,
    borderBottomWidth: 1, borderBottomColor: '#EBE3D7',
  },
  periodBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8, backgroundColor: '#F3EDE3' },
  periodBtnActive: { backgroundColor: C.primary },
  periodBtnText: { fontSize: 14, fontWeight: '600', color: '#5A6A61' },
  periodBtnTextActive: { color: '#fff' },
  centered: { alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#5A6A61', fontSize: 15 },
  errorText: { color: '#D0402F', fontSize: 15, fontWeight: '600' },
  retryBtn: { backgroundColor: C.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 10 },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  statsCard: {
    flexDirection: 'row', backgroundColor: '#fff', borderRadius: 16, padding: 16, marginBottom: 12,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 3,
  },
  statItem: { flex: 1, alignItems: 'center', gap: 6 },
  statLabel: { fontSize: 12, color: '#93A09A', textTransform: 'uppercase', letterSpacing: 0.5 },
  statValue: { fontSize: 15, fontWeight: '800', color: '#14211B' },
  statDivider: { width: 1, backgroundColor: '#EBE3D7', marginVertical: 4 },
  chartCard: {
    backgroundColor: '#fff', borderRadius: 16, padding: 16, marginBottom: 12,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 3,
  },
  chartTitle: { fontSize: 13, fontWeight: '600', color: '#5A6A61', marginBottom: 12 },
  chartLegend: { flexDirection: 'row', gap: 16, marginTop: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: 12, color: '#5A6A61' },
  emptyState: { alignItems: 'center', paddingVertical: 48, gap: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: '#47564F' },
  emptySubtitle: { fontSize: 14, color: '#93A09A', textAlign: 'center' },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#14211B', marginBottom: 8 },
  priceList: {
    backgroundColor: '#fff', borderRadius: 14, overflow: 'hidden',
    borderWidth: 1, borderColor: '#EBE3D7',
  },
  priceRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 11 },
  priceRowBorder: { borderBottomWidth: 1, borderBottomColor: '#F3EDE3' },
  priceRowHeader: { backgroundColor: '#FBF7F1', paddingVertical: 9 },
  headerText: { fontSize: 11, fontWeight: '700', color: '#93A09A', textTransform: 'uppercase' },
  priceRowDate: { fontSize: 12, color: '#5A6A61', width: 60 },
  priceRowStore: { flex: 1, fontSize: 13, color: '#14211B', paddingHorizontal: 6 },
  priceRowRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  promoBadge: {
    backgroundColor: '#FCEDE9', borderRadius: 4, paddingHorizontal: 5, paddingVertical: 1,
    borderWidth: 1, borderColor: '#F3C9C6',
  },
  promoBadgeText: { color: '#D0402F', fontSize: 9, fontWeight: '700' },
  priceRowValue: { fontSize: 14, fontWeight: '700', color: '#14211B', minWidth: 80, textAlign: 'right' },
});

export default HistoriquePrixScreen;
