/**
 * PromotionsScreen — PrixMaroc
 * Liste des promotions en cours, filtrées par ville.
 */
import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  StatusBar,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import { PricesAPI } from '@services/api';
import { Colors, C } from '@constants/colors';
import type { PromoItem } from '@types/models';

// ─── Constantes ───────────────────────────────────────────────────────────────

const CITIES: { label: string; value: string }[] = [
  { label: 'Toutes',      value: '' },
  { label: 'Casablanca',  value: 'casablanca' },
  { label: 'Rabat',       value: 'rabat' },
  { label: 'Marrakech',   value: 'marrakech' },
  { label: 'Fès',         value: 'fes' },
  { label: 'Agadir',      value: 'agadir' },
  { label: 'Tanger',      value: 'tanger' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function discountPercent(original: number, promo: number): number {
  if (!original || original <= 0) return 0;
  return Math.round(((original - promo) / original) * 100);
}

function savings(original: number, promo: number): string {
  const diff = original - promo;
  if (diff <= 0) return '0.00';
  return diff.toFixed(2);
}

function formatPrice(n: number | undefined | null): string {
  if (n == null) return '—';
  return Number(n).toFixed(2);
}

function maxDiscount(promotions: PromoItem[]): number {
  if (!promotions.length) return 0;
  return Math.max(
    ...promotions.map((p) =>
      discountPercent(Number(p.regular_price), Number(p.promo_price ?? p.regular_price)),
    ),
  );
}

// ─── City Picker ──────────────────────────────────────────────────────────────

interface CityPickerProps {
  selected: string;
  onSelect: (city: string) => void;
}

const CityPicker: React.FC<CityPickerProps> = ({ selected, onSelect }) => (
  <View style={styles.pickerRow}>
    {CITIES.map((c) => (
      <TouchableOpacity
        key={c.value === '' ? '__all__' : c.value}
        onPress={() => onSelect(c.value)}
        style={[
          styles.cityChip,
          selected === c.value && styles.cityChipActive,
        ]}
        activeOpacity={0.75}
      >
        <Text
          style={[
            styles.cityChipText,
            selected === c.value && styles.cityChipTextActive,
          ]}
        >
          {c.label}
        </Text>
      </TouchableOpacity>
    ))}
  </View>
);

// ─── Summary Bar ──────────────────────────────────────────────────────────────

interface SummaryBarProps {
  count: number;
  maxPct: number;
}

const SummaryBar: React.FC<SummaryBarProps> = ({ count, maxPct }) => (
  <View style={styles.summaryBar}>
    <Text style={styles.summaryText}>
      <Text style={styles.summaryCount}>{count}</Text>
      {count === 1 ? ' promotion disponible' : ' promotions disponibles'}
      {maxPct > 0 ? (
        <Text>
          {'  ·  '}
          <Text style={styles.summaryDiscount}>Jusqu&apos;à -{maxPct}%</Text>
        </Text>
      ) : null}
    </Text>
  </View>
);

// ─── Promo Card ───────────────────────────────────────────────────────────────

interface PromoCardProps {
  item: PromoItem;
}

const PromoCard: React.FC<PromoCardProps> = ({ item }) => {
  const originalPrice = Number(item.regular_price);
  const promoPrice    = Number(item.promo_price ?? item.regular_price);
  const pct           = discountPercent(originalPrice, promoPrice);
  const saved         = savings(originalPrice, promoPrice);
  const hasDiscount   = pct > 0 && Number(saved) > 0;

  return (
    <View style={styles.card}>
      {/* Top accent strip (simulates light green gradient) */}
      <View style={styles.cardAccentStrip} />

      {/* Discount badge top-right */}
      {hasDiscount && (
        <View style={styles.discountBadge}>
          <Text style={styles.discountBadgeText}>-{pct}%</Text>
        </View>
      )}

      <View style={styles.cardContent}>
        {/* Product name */}
        <Text style={styles.productName} numberOfLines={2}>
          {item.product_name}
        </Text>

        {/* Store */}
        <Text style={styles.storeName} numberOfLines={1}>
          {item.store_name}
          {item.store_city ? ` · ${item.store_city}` : ''}
        </Text>

        {/* Price comparison */}
        <View style={styles.priceRow}>
          {hasDiscount && (
            <Text style={styles.originalPrice}>
              {formatPrice(originalPrice)} MAD
            </Text>
          )}
          <Text style={styles.promoPrice}>
            {formatPrice(promoPrice)} MAD
          </Text>
        </View>

        {/* Economy badge */}
        {hasDiscount && (
          <View style={styles.savingsBadge}>
            <Text style={styles.savingsText}>
              Économisez {saved} MAD
            </Text>
          </View>
        )}
      </View>
    </View>
  );
};

// ─── Empty State ──────────────────────────────────────────────────────────────

const EmptyState: React.FC = () => (
  <View style={styles.emptyContainer}>
    <Text style={styles.emptyIcon}>🏷️</Text>
    <Text style={styles.emptyTitle}>Aucune promotion disponible</Text>
    <Text style={styles.emptySubtitle}>
      Aucune promotion disponible pour cette ville
    </Text>
  </View>
);

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function PromotionsScreen() {
  const [city, setCity] = useState<string>('');

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['promotions', city] as const,
    queryFn: () =>
      PricesAPI.getPromos({ city: city !== '' ? city : undefined, limit: 30 }),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });

  const promotions: PromoItem[] = data?.promotions ?? [];
  const count      = data?.count ?? promotions.length;
  const topDiscount = maxDiscount(promotions);

  const handleCitySelect = useCallback((c: string) => setCity(c), []);

  const renderItem = useCallback(
    ({ item }: { item: PromoItem }) => <PromoCard item={item} />,
    [],
  );

  const keyExtractor = useCallback(
    (item: PromoItem, index: number) =>
      `promo-${item.product_id}-${item.store_id}-${index}`,
    [],
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar
        barStyle="dark-content"
        backgroundColor={Colors.surface.white}
      />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🏷️ Promotions</Text>
      </View>

      {/* City picker */}
      <CityPicker selected={city} onSelect={handleCitySelect} />

      {/* Summary bar */}
      {!isLoading && !isError && (
        <SummaryBar count={count} maxPct={topDiscount} />
      )}

      {/* Body */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Chargement des promotions…</Text>
        </View>
      ) : isError ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>⚠️</Text>
          <Text style={styles.emptyTitle}>Erreur de chargement</Text>
          <Text style={styles.emptySubtitle}>
            Impossible de récupérer les promotions.
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={() => refetch()}
            activeOpacity={0.8}
          >
            <Text style={styles.retryButtonText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={promotions}
          keyExtractor={keyExtractor}
          renderItem={renderItem}
          contentContainerStyle={
            promotions.length === 0
              ? styles.flatListEmpty
              : styles.flatListContent
          }
          ListEmptyComponent={<EmptyState />}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={isFetching && !isLoading}
              onRefresh={refetch}
              tintColor={C.primary}
              colors={[C.primary]}
            />
          }
        />
      )}
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.surface.secondary,
  },

  // ── Header ─────────────────────────────────────────────────────────────────
  header: {
    backgroundColor: Colors.surface.white,
    paddingTop: Platform.OS === 'android' ? 8 : 4,
    paddingBottom: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border.light,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: Colors.text.primary,
    letterSpacing: -0.3,
  },

  // ── City picker ─────────────────────────────────────────────────────────────
  pickerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: Colors.surface.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border.light,
  },
  cityChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: Colors.surface.tertiary,
    borderWidth: 1,
    borderColor: Colors.border.light,
  },
  cityChipActive: {
    backgroundColor: Colors.primary[600],
    borderColor: Colors.primary[600],
  },
  cityChipText: {
    fontSize: 13,
    fontWeight: '500',
    color: Colors.text.secondary,
  },
  cityChipTextActive: {
    color: Colors.surface.white,
    fontWeight: '600',
  },

  // ── Summary bar ─────────────────────────────────────────────────────────────
  summaryBar: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    backgroundColor: Colors.primary[50],
    borderBottomWidth: 1,
    borderBottomColor: Colors.primary[100],
  },
  summaryText: {
    fontSize: 13,
    color: Colors.text.secondary,
  },
  summaryCount: {
    fontWeight: '700',
    color: Colors.text.primary,
  },
  summaryDiscount: {
    fontWeight: '700',
    color: Colors.promo,
  },

  // ── Loading ─────────────────────────────────────────────────────────────────
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
    color: Colors.text.tertiary,
  },

  // ── FlatList ────────────────────────────────────────────────────────────────
  flatListContent: {
    padding: 16,
    paddingBottom: 32,
  },
  flatListEmpty: {
    flex: 1,
  },

  // ── Empty / error state ─────────────────────────────────────────────────────
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 8,
  },
  emptyIcon: {
    fontSize: 52,
    marginBottom: 4,
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: Colors.text.primary,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 14,
    color: Colors.text.secondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  retryButton: {
    marginTop: 12,
    paddingHorizontal: 24,
    paddingVertical: 10,
    backgroundColor: C.primary,
    borderRadius: 10,
  },
  retryButtonText: {
    color: Colors.surface.white,
    fontWeight: '600',
    fontSize: 14,
  },

  // ── Promo Card ──────────────────────────────────────────────────────────────
  card: {
    backgroundColor: Colors.surface.white,
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 12,
    position: 'relative',
    // Shadow
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  // Top strip: light green → simulates gradient top edge
  cardAccentStrip: {
    height: 5,
    backgroundColor: Colors.primary[200],
  },
  cardContent: {
    padding: 16,
    paddingTop: 14,
  },

  // Discount badge (red circle, top-right)
  discountBadge: {
    position: 'absolute',
    top: 14,
    right: 14,
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: Colors.promo,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    shadowColor: Colors.promo,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 5,
  },
  discountBadgeText: {
    color: Colors.surface.white,
    fontWeight: '800',
    fontSize: 13,
    letterSpacing: -0.5,
  },

  // Product name & store
  productName: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.text.primary,
    marginBottom: 4,
    paddingRight: 64, // clear the badge
    lineHeight: 22,
  },
  storeName: {
    fontSize: 13,
    color: Colors.text.secondary,
    marginBottom: 12,
    paddingRight: 64,
  },

  // Price row
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  originalPrice: {
    fontSize: 14,
    color: Colors.text.tertiary,
    textDecorationLine: 'line-through',
    fontWeight: '500',
  },
  promoPrice: {
    fontSize: 24,
    fontWeight: '800',
    color: Colors.success,
    letterSpacing: -0.5,
  },

  // Savings badge
  savingsBadge: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.primary[50],
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Colors.primary[200],
  },
  savingsText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.primary[700],
  },
});
