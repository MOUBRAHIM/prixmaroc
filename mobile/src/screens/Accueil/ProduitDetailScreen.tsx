import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  Image,
  RefreshControl,
  Alert,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Polyline, Circle, Line, Text as SvgText } from 'react-native-svg';
import { ProductsAPI, AlertsAPI } from '@services/api';
import ProductVisual from '@components/ui/ProductVisual';
import { C } from '@constants/colors';
import type { PriceInStore } from '@types/models';

// ProduitDetailScreen est utilisé dans AccueilStack ET ComparerStack
type Props = {
  route: { params: { productId: number; productName: string } };
  navigation: { navigate: (screen: string, params?: object) => void; goBack: () => void };
};

// ── Nutriscore badge ──────────────────────────────────────────────────────────

const NUTRISCORE_COLORS: Record<string, string> = {
  A: '#038141',
  B: '#85BB2F',
  C: '#FECB02',
  D: '#EE8100',
  E: '#E63312',
};

const NutriScoreBadge: React.FC<{ score: string }> = ({ score }) => {
  const grades = ['A', 'B', 'C', 'D', 'E'];
  return (
    <View style={nutri.row}>
      <Text style={nutri.label}>Nutri-Score</Text>
      <View style={nutri.badges}>
        {grades.map((g) => {
          const active = g === score.toUpperCase();
          const color = NUTRISCORE_COLORS[g] ?? '#94a3b8';
          return (
            <View
              key={g}
              style={[
                nutri.badge,
                { backgroundColor: active ? color : '#e2e8f0' },
                active && nutri.badgeActive,
              ]}
            >
              <Text style={[nutri.badgeText, { color: active ? '#fff' : '#94a3b8' }]}>{g}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
};

// ── Barre nutritionnelle ──────────────────────────────────────────────────────

const NutriBar: React.FC<{
  label: string;
  value: number;
  unit: string;
  max: number;
  color: string;
}> = ({ label, value, unit, max, color }) => {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <View style={nutri.barRow}>
      <Text style={nutri.barLabel}>{label}</Text>
      <View style={nutri.barTrack}>
        <View style={[nutri.barFill, { width: `${pct}%` as any, backgroundColor: color }]} />
      </View>
      <Text style={nutri.barValue}>
        {value.toFixed(1)} {unit}
      </Text>
    </View>
  );
};

// ── Section nutrition expansible ──────────────────────────────────────────────

type NutritionSectionProps = {
  calories?: number | null;
  proteins?: number | null;
  lipids?: number | null;
  carbs?: number | null;
  fibers?: number | null;
  nutriscore?: string | null;
};

const NutritionSection: React.FC<NutritionSectionProps> = ({
  calories, proteins, lipids, carbs, fibers, nutriscore,
}) => {
  const [expanded, setExpanded] = useState(false);

  const hasData = calories != null || proteins != null || lipids != null || carbs != null;
  if (!hasData && !nutriscore) return null;

  return (
    <View style={nutri.container}>
      <TouchableOpacity style={nutri.header} onPress={() => setExpanded((v) => !v)} activeOpacity={0.7}>
        <View style={nutri.headerLeft}>
          <Ionicons name="nutrition-outline" size={20} color={C.primary} />
          <Text style={nutri.headerTitle}>Infos nutritionnelles</Text>
          {nutriscore && (
            <View style={[nutri.miniScore, { backgroundColor: NUTRISCORE_COLORS[nutriscore.toUpperCase()] ?? '#94a3b8' }]}>
              <Text style={nutri.miniScoreText}>{nutriscore.toUpperCase()}</Text>
            </View>
          )}
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={18}
          color="#94a3b8"
        />
      </TouchableOpacity>

      {expanded && (
        <View style={nutri.body}>
          {nutriscore && <NutriScoreBadge score={nutriscore} />}

          <Text style={nutri.per100g}>Pour 100g / 100ml</Text>

          {calories != null && (
            <View style={nutri.caloriesRow}>
              <Text style={nutri.caloriesLabel}>Énergie</Text>
              <Text style={nutri.caloriesValue}>{calories.toFixed(0)} kcal</Text>
            </View>
          )}

          {proteins != null && (
            <NutriBar label="Protéines" value={proteins} unit="g" max={30} color="#3b82f6" />
          )}
          {lipids != null && (
            <NutriBar label="Lipides" value={lipids} unit="g" max={40} color="#f59e0b" />
          )}
          {carbs != null && (
            <NutriBar label="Glucides" value={carbs} unit="g" max={80} color="#8b5cf6" />
          )}
          {fibers != null && (
            <NutriBar label="Fibres" value={fibers} unit="g" max={15} color="#22c55e" />
          )}
        </View>
      )}
    </View>
  );
};

const nutri = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 15, fontWeight: '700', color: '#0f172a' },
  miniScore: {
    width: 22,
    height: 22,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  miniScoreText: { fontSize: 12, fontWeight: '900', color: '#fff' },
  body: { paddingHorizontal: 14, paddingBottom: 14, gap: 10 },
  per100g: { fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  caloriesRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    padding: 10,
  },
  caloriesLabel: { fontSize: 14, fontWeight: '600', color: '#374151' },
  caloriesValue: { fontSize: 18, fontWeight: '800', color: '#dc2626' },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barLabel: { width: 72, fontSize: 12, fontWeight: '600', color: '#475569' },
  barTrack: { flex: 1, height: 8, backgroundColor: '#f1f5f9', borderRadius: 4, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4 },
  barValue: { width: 48, fontSize: 12, fontWeight: '700', color: '#374151', textAlign: 'right' },
  label: { fontSize: 13, fontWeight: '700', color: '#374151', marginBottom: 8 },
  row: { gap: 8 },
  badges: { flexDirection: 'row', gap: 4 },
  badge: { width: 32, height: 32, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  badgeActive: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
    elevation: 3,
  },
  badgeText: { fontSize: 14, fontWeight: '900' },
});

// ── Sparkline 30 jours ────────────────────────────────────────────────────────

const SCREEN_WIDTH = Dimensions.get('window').width;
const SPARK_W = SCREEN_WIDTH - 32;   // marges 16 de chaque côté
const SPARK_H = 90;
const SPARK_PAD_X = 8;
const SPARK_PAD_Y = 14;

type SparklineChartProps = {
  points: Array<{ date: string; price: number; is_promo: boolean }>;
  minPrice: number;
  maxPrice: number;
};

function SparklineChart({ points, minPrice, maxPrice }: SparklineChartProps) {
  if (!points || points.length < 2) return null;

  const priceRange = maxPrice - minPrice || 1;
  const innerW = SPARK_W - SPARK_PAD_X * 2;
  const innerH = SPARK_H - SPARK_PAD_Y * 2;

  // Coordonnées de chaque point
  const coords = points.map((p, i) => {
    const x = SPARK_PAD_X + (i / (points.length - 1)) * innerW;
    const y = SPARK_PAD_Y + (1 - (p.price - minPrice) / priceRange) * innerH;
    return { x, y, price: p.price, is_promo: p.is_promo };
  });

  const polylinePoints = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const lastPt = coords[coords.length - 1];
  const firstDate = points[0].date.slice(5);   // MM-DD
  const lastDate = points[points.length - 1].date.slice(5);

  // Ligne de prix moyen
  const avgPrice = points.reduce((s, p) => s + p.price, 0) / points.length;
  const avgY = SPARK_PAD_Y + (1 - (avgPrice - minPrice) / priceRange) * innerH;

  return (
    <Svg width={SPARK_W} height={SPARK_H}>
      {/* Ligne de moyenne */}
      <Line
        x1={SPARK_PAD_X}
        y1={avgY}
        x2={SPARK_W - SPARK_PAD_X}
        y2={avgY}
        stroke="#e2e8f0"
        strokeWidth="1"
        strokeDasharray="4,3"
      />
      {/* Courbe principale */}
      <Polyline
        points={polylinePoints}
        fill="none"
        stroke={C.primary}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Points promo en rouge */}
      {coords.filter((c) => c.is_promo).map((c, i) => (
        <Circle key={i} cx={c.x} cy={c.y} r={3} fill="#ef4444" />
      ))}
      {/* Dernier point mis en avant */}
      <Circle cx={lastPt.x} cy={lastPt.y} r={4} fill={C.primary} stroke="#fff" strokeWidth="1.5" />
      {/* Labels dates */}
      <SvgText x={SPARK_PAD_X} y={SPARK_H - 2} fontSize={9} fill="#94a3b8">{firstDate}</SvgText>
      <SvgText x={SPARK_W - SPARK_PAD_X} y={SPARK_H - 2} fontSize={9} fill="#94a3b8" textAnchor="end">{lastDate}</SvgText>
      {/* Label dernier prix */}
      <SvgText
        x={Math.min(lastPt.x + 6, SPARK_W - 36)}
        y={Math.max(lastPt.y - 4, 10)}
        fontSize={10}
        fontWeight="700"
        fill={C.primary}
      >
        {lastPt.price.toFixed(2)}
      </SvgText>
    </Svg>
  );
}

type PriceSparklineProps = { productId: number };

const PriceSparklineSection: React.FC<PriceSparklineProps> = ({ productId }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['price-history', productId, 30],
    queryFn: () => ProductsAPI.getPriceHistory(productId, 30),
    staleTime: 1000 * 60 * 10,
  });

  if (isLoading) {
    return (
      <View style={spark.container}>
        <View style={spark.header}>
          <Ionicons name="trending-up-outline" size={16} color={C.primary} />
          <Text style={spark.title}>Évolution 30 jours</Text>
        </View>
        <ActivityIndicator size="small" color={C.primary} style={{ marginVertical: 24 }} />
      </View>
    );
  }

  if (!data || !data.points || data.points.length < 2) return null;

  const minP = data.min_price ?? 0;
  const maxP = data.max_price ?? 0;
  const variation = minP > 0 ? ((maxP - minP) / minP) * 100 : 0;

  return (
    <View style={spark.container}>
      <View style={spark.header}>
        <Ionicons name="trending-up-outline" size={16} color={C.primary} />
        <Text style={spark.title}>Évolution 30 jours</Text>
        <View style={[spark.variationBadge, { backgroundColor: variation > 5 ? '#fef2f2' : '#f0fdf4' }]}>
          <Text style={[spark.variationText, { color: variation > 5 ? '#dc2626' : '#16a34a' }]}>
            {variation > 0 ? '+' : ''}{variation.toFixed(1)}%
          </Text>
        </View>
      </View>

      <View style={spark.chartWrap}>
        <SparklineChart
          points={data.points}
          minPrice={minP}
          maxPrice={maxP}
        />
      </View>

      {/* Mini légende */}
      <View style={spark.legend}>
        <View style={spark.legendItem}>
          <View style={[spark.legendDot, { backgroundColor: C.primary }]} />
          <Text style={spark.legendLabel}>Dernier prix</Text>
        </View>
        <View style={spark.legendItem}>
          <View style={[spark.legendDot, { backgroundColor: '#ef4444' }]} />
          <Text style={spark.legendLabel}>Promotion</Text>
        </View>
        <View style={spark.legendItem}>
          <View style={[spark.legendDash]} />
          <Text style={spark.legendLabel}>Moyenne</Text>
        </View>
        <Text style={spark.minMax}>
          {minP.toFixed(2)} → {maxP.toFixed(2)} MAD
        </Text>
      </View>
    </View>
  );
};

const spark = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 14,
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  title: { flex: 1, fontSize: 14, fontWeight: '700', color: '#0f172a' },
  variationBadge: {
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  variationText: { fontSize: 11, fontWeight: '700' },
  chartWrap: { alignItems: 'flex-start' },
  legend: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendDash: { width: 16, height: 2, backgroundColor: '#e2e8f0' },
  legendLabel: { fontSize: 11, color: '#64748b' },
  minMax: { fontSize: 11, color: '#94a3b8', marginLeft: 'auto' as any },
});

// ── Carte magasin / prix ──────────────────────────────────────────────────────

const StoreCard: React.FC<{ price: PriceInStore; isFirst: boolean }> = ({ price, isFirst }) => {
  const effectivePrice = price.promo_price ?? price.price;
  return (
    <View style={[styles.storeCard, isFirst && styles.storeCardBest]}>
      {isFirst && (
        <View style={styles.bestBadge}>
          <Ionicons name="trophy" size={12} color="#ffffff" />
          <Text style={styles.bestBadgeText}>Meilleur prix</Text>
        </View>
      )}
      <View style={styles.storeCardRow}>
        <View style={styles.storeInfo}>
          <Text style={styles.storeName}>{price.store_name}</Text>
          {price.store_city ? <Text style={styles.storeCity}>{price.store_city}</Text> : null}
          <Text style={styles.storeSource}>Via {price.source}</Text>
        </View>
        <View style={styles.priceBox}>
          {price.is_promo && price.promo_price != null ? (
            <>
              <Text style={styles.promoPrice}>{price.promo_price.toFixed(2)} MAD</Text>
              <Text style={styles.regularPriceStrike}>{price.price.toFixed(2)} MAD</Text>
              <View style={styles.promoBadge}>
                <Text style={styles.promoBadgeText}>
                  -{Math.round((1 - price.promo_price / price.price) * 100)}%
                </Text>
              </View>
            </>
          ) : (
            <Text style={[styles.regularPrice, isFirst && styles.bestPrice]}>
              {effectivePrice.toFixed(2)} MAD
            </Text>
          )}
        </View>
      </View>
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const ProduitDetailScreen: React.FC<Props> = ({ route, navigation }) => {
  const { productId, productName } = route.params;
  const queryClient = useQueryClient();
  const [alertTarget, setAlertTarget] = useState('');

  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ['product-detail', productId],
    queryFn: () => ProductsAPI.getDetail(productId),
  });

  const alertMutation = useMutation({
    mutationFn: (target: number) =>
      AlertsAPI.create({ product_id: productId, target_price: target }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['price-alerts'] });
      Alert.alert('Alerte créée !', `Vous serez notifié quand le prix descend sous ${alertTarget} MAD.`);
      setAlertTarget('');
    },
    onError: () => Alert.alert('Erreur', "Impossible de créer l'alerte."),
  });

  const handleCreateAlert = () => {
    if (!data) return;
    const cheapest = data.lowest_price ?? 0;
    Alert.prompt(
      'Créer une alerte prix',
      `Prix actuel le plus bas : ${cheapest.toFixed(2)} MAD\nSaisissez votre prix cible (MAD) :`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Créer',
          onPress: (value?: string) => {
            const n = parseFloat(value ?? '');
            if (isNaN(n) || n <= 0) {
              Alert.alert('Erreur', 'Veuillez saisir un prix valide.');
              return;
            }
            alertMutation.mutate(n);
          },
        },
      ],
      'plain-text',
      cheapest ? String(cheapest.toFixed(2)) : '',
    );
  };

  const sortedPrices = [...(data?.prices ?? [])].sort(
    (a, b) => (a.promo_price ?? a.price) - (b.promo_price ?? b.price),
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />
        }
      >
        {/* Chargement */}
        {isLoading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Chargement…</Text>
          </View>
        )}

        {/* Erreur */}
        {isError && (
          <View style={styles.errorContainer}>
            <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
            <Text style={styles.errorTitle}>Impossible de charger le produit</Text>
            <Text style={styles.errorMsg}>{(error as Error)?.message}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
              <Text style={styles.retryBtnText}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Contenu */}
        {data && (
          <>
            {/* Header produit */}
            <View style={styles.productHeader}>
              <ProductVisual
                name={data.name}
                imageUrl={data.image_url}
                size={110}
                radius={16}
              />
              <View style={styles.productMeta}>
                <Text style={styles.productName}>{data.name}</Text>
                {data.brand ? <Text style={styles.productBrand}>{data.brand}</Text> : null}
                {data.unit_size ? <Text style={styles.productUnit}>{data.unit_size}</Text> : null}
                {data.category ? (
                  <View style={styles.categoryBadge}>
                    <Text style={styles.categoryText}>{data.category.name}</Text>
                  </View>
                ) : null}
              </View>
            </View>

            {/* Résumé prix */}
            <View style={styles.pricesSummary}>
              <View style={styles.priceStat}>
                <Text style={styles.priceStatLabel}>Min</Text>
                <Text style={[styles.priceStatValue, { color: C.primary }]}>
                  {data.lowest_price?.toFixed(2) ?? '—'} MAD
                </Text>
              </View>
              <View style={styles.priceDivider} />
              <View style={styles.priceStat}>
                <Text style={styles.priceStatLabel}>Moyen</Text>
                <Text style={styles.priceStatValue}>
                  {data.avg_price?.toFixed(2) ?? '—'} MAD
                </Text>
              </View>
              <View style={styles.priceDivider} />
              <View style={styles.priceStat}>
                <Text style={styles.priceStatLabel}>Max</Text>
                <Text style={[styles.priceStatValue, { color: '#ef4444' }]}>
                  {data.highest_price?.toFixed(2) ?? '—'} MAD
                </Text>
              </View>
            </View>

            {/* Sparkline évolution 30 jours */}
            <Text style={styles.sectionTitle}>Historique des prix</Text>
            <PriceSparklineSection productId={productId} />

            {/* Boutons actions */}
            <View style={styles.actionsRow}>
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={handleCreateAlert}
              >
                <Ionicons name="notifications-outline" size={18} color={C.primary} />
                <Text style={styles.actionBtnText}>Alerte prix</Text>
              </TouchableOpacity>
            </View>

            {/* Infos nutritionnelles (expansible) */}
            <Text style={styles.sectionTitle}>Nutrition</Text>
            <NutritionSection
              calories={data.calories}
              proteins={data.proteins}
              lipids={data.lipids}
              carbs={data.carbs}
              fibers={data.fibers}
              nutriscore={data.nutriscore}
            />

            {/* Prix par magasin */}
            <Text style={styles.sectionTitle}>
              Prix dans {sortedPrices.length} magasin{sortedPrices.length > 1 ? 's' : ''}
            </Text>

            {sortedPrices.length === 0 ? (
              <View style={styles.noPricesContainer}>
                <Ionicons name="storefront-outline" size={40} color="#d1d5db" />
                <Text style={styles.noPricesText}>Aucun prix disponible pour le moment</Text>
              </View>
            ) : (
              sortedPrices.map((price, i) => (
                <StoreCard key={`${price.store_id}-${i}`} price={price} isFirst={i === 0} />
              ))
            )}

            {/* Description */}
            {data.description ? (
              <>
                <Text style={styles.sectionTitle}>Description</Text>
                <View style={styles.descriptionCard}>
                  <Text style={styles.descriptionText}>{data.description}</Text>
                </View>
              </>
            ) : null}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 32 },
  loadingContainer: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#64748b', fontSize: 15 },
  errorContainer: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12, paddingHorizontal: 32 },
  errorTitle: { fontSize: 16, fontWeight: '700', color: '#ef4444' },
  errorMsg: { fontSize: 13, color: '#64748b', textAlign: 'center' },
  retryBtn: {
    backgroundColor: C.primary,
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 10,
    marginTop: 8,
  },
  retryBtnText: { color: '#ffffff', fontWeight: '700', fontSize: 14 },
  productHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#ffffff',
    padding: 20,
    paddingBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    gap: 16,
  },
  productImage: {
    width: 96,
    height: 96,
    borderRadius: 16,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  productImagePlaceholder: {
    width: 96,
    height: 96,
    borderRadius: 16,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  productMeta: { flex: 1 },
  productName: { fontSize: 18, fontWeight: '800', color: '#0f172a', marginBottom: 4, lineHeight: 24 },
  productBrand: { fontSize: 14, color: '#64748b', marginBottom: 2, fontWeight: '500' },
  productUnit: { fontSize: 12, color: '#94a3b8', marginBottom: 8 },
  categoryBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#f0fdf4',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  categoryText: { fontSize: 11, color: '#16a34a', fontWeight: '700', letterSpacing: 0.2 },
  pricesSummary: {
    flexDirection: 'row',
    backgroundColor: '#ffffff',
    paddingVertical: 0,
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 4,
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  priceStat: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  priceStatLabel: { fontSize: 11, color: '#94a3b8', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.7, fontWeight: '600' },
  priceStatValue: { fontSize: 15, fontWeight: '800', color: '#0f172a' },
  priceDivider: { width: 1, backgroundColor: '#e2e8f0', marginVertical: 12 },
  actionsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 10,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#f0fdf4',
    borderWidth: 1.5,
    borderColor: '#bbf7d0',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  actionBtnText: { color: C.primary, fontWeight: '700', fontSize: 14 },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#64748b',
    marginHorizontal: 16,
    marginTop: 16,
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  storeCard: {
    marginHorizontal: 16,
    marginBottom: 10,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  storeCardBest: {
    borderColor: C.primary,
    borderWidth: 2,
    backgroundColor: '#f0fdf4',
    shadowColor: '#16a34a',
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 5,
  },
  bestBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: C.primary,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 10,
    gap: 4,
  },
  bestBadgeText: { color: '#ffffff', fontSize: 11, fontWeight: '700', letterSpacing: 0.3 },
  storeCardRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  storeInfo: { flex: 1 },
  storeName: { fontSize: 15, fontWeight: '700', color: '#0f172a' },
  storeCity: { fontSize: 12, color: '#64748b', marginTop: 3 },
  storeSource: { fontSize: 11, color: '#94a3b8', marginTop: 2, textTransform: 'capitalize' },
  priceBox: { alignItems: 'flex-end' },
  regularPrice: { fontSize: 20, fontWeight: '800', color: '#0f172a' },
  bestPrice: { color: C.primary },
  promoPrice: { fontSize: 20, fontWeight: '800', color: '#dc2626' },
  regularPriceStrike: { fontSize: 13, color: '#94a3b8', textDecorationLine: 'line-through' },
  promoBadge: {
    backgroundColor: '#fef2f2',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 4,
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  promoBadgeText: { color: '#dc2626', fontSize: 11, fontWeight: '700' },
  noPricesContainer: { alignItems: 'center', paddingVertical: 40, gap: 12 },
  noPricesText: { color: '#94a3b8', fontSize: 14 },
  descriptionCard: {
    marginHorizontal: 16,
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  descriptionText: { fontSize: 14, color: '#475569', lineHeight: 22 },
});

export default ProduitDetailScreen;
