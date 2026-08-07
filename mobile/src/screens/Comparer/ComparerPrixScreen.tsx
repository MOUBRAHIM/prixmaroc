import React from 'react';
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
import { useQueries } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { ProductsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ComparerStackParamList, ProductDetail } from '@types/models';

type Props = NativeStackScreenProps<ComparerStackParamList, 'ComparerPrix'>;

// ── Ligne produit dans le tableau ─────────────────────────────────────────────

const ProductRow: React.FC<{
  product: ProductDetail;
  storeName: string;
  rank: number;
}> = ({ product, storeName, rank }) => {
  const best = product.prices.sort(
    (a, b) => (a.promo_price ?? a.price) - (b.promo_price ?? b.price),
  )[0];
  const effectivePrice = best ? (best.promo_price ?? best.price) : null;
  const isFirst = rank === 0;

  return (
    <View style={[styles.productRow, isFirst && styles.productRowBest]}>
      <View style={styles.rankBadge}>
        <Text style={[styles.rankText, isFirst && styles.rankTextBest]}>{rank + 1}</Text>
      </View>
      <View style={styles.productRowInfo}>
        <Text style={styles.productRowName} numberOfLines={2}>{product.name}</Text>
        {product.brand ? <Text style={styles.productRowBrand}>{product.brand}</Text> : null}
        <Text style={styles.productRowStore}>{storeName}</Text>
      </View>
      <View style={styles.productRowPrice}>
        {effectivePrice != null ? (
          <>
            {best?.is_promo && best.promo_price != null && (
              <Text style={styles.originalPrice}>{best.price.toFixed(2)}</Text>
            )}
            <Text style={[styles.effectivePrice, isFirst && { color: C.primary }]}>
              {effectivePrice.toFixed(2)} MAD
            </Text>
            {best?.is_promo && (
              <View style={styles.promoBadge}>
                <Text style={styles.promoBadgeText}>
                  -{Math.round((1 - (best.promo_price ?? best.price) / best.price) * 100)}%
                </Text>
              </View>
            )}
          </>
        ) : (
          <Text style={styles.naPrice}>—</Text>
        )}
      </View>
    </View>
  );
};

// ── Carte comparaison par magasin ─────────────────────────────────────────────

const StoreComparisonCard: React.FC<{
  storeName: string;
  products: ProductDetail[];
  totalMin: number;
}> = ({ storeName, products, totalMin }) => {
  let total = 0;
  let allAvailable = true;
  products.forEach((p) => {
    const best = p.prices
      .filter((pr) => pr.store_name === storeName)
      .sort((a, b) => (a.promo_price ?? a.price) - (b.promo_price ?? b.price))[0];
    if (best) {
      total += best.promo_price ?? best.price;
    } else {
      allAvailable = false;
    }
  });

  const saving = allAvailable ? total - totalMin : null;

  return (
    <View style={[styles.storeCard, !allAvailable && styles.storeCardDisabled, saving === 0 && styles.storeCardBest]}>
      <View style={styles.storeCardHeader}>
        <Ionicons name="storefront" size={18} color={allAvailable ? C.primary : '#8A9A92'} />
        <Text style={[styles.storeName, !allAvailable && { color: '#8A9A92' }]}>{storeName}</Text>
        {saving !== null && (
          <View style={[
            styles.savingBadge,
            saving > 0 ? styles.savingBadgeNeg : styles.savingBadgeBest,
          ]}>
            {saving === 0 ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
                <Ionicons name="trophy" size={11} color="#0C3F30" />
                <Text style={[styles.savingText, styles.savingTextBest]}>MEILLEUR PRIX</Text>
              </View>
            ) : (
              <Text style={[styles.savingText, styles.savingTextNeg]}>+{saving.toFixed(2)} MAD</Text>
            )}
          </View>
        )}
      </View>
      <Text style={[styles.storeTotal, !allAvailable && { color: '#8A9A92' }]}>
        {allAvailable ? `Total : ${total.toFixed(2)} MAD` : 'Produits non disponibles'}
      </Text>
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const ComparerPrixScreen: React.FC<Props> = ({ route, navigation }) => {
  const { productIds } = route.params;

  const results = useQueries({
    queries: productIds.map((id) => ({
      queryKey: ['product-detail', id],
      queryFn: () => ProductsAPI.getDetail(id),
    })),
  });

  const isLoading = results.some((r) => r.isLoading);
  const isError = results.some((r) => r.isError);
  const products = results.map((r) => r.data).filter(Boolean) as ProductDetail[];

  // Récupère tous les magasins uniques
  const allStores = Array.from(
    new Set(products.flatMap((p) => p.prices.map((pr) => pr.store_name))),
  ).sort();

  // Calcule le total minimum (panier le moins cher)
  let totalMin = 0;
  products.forEach((p) => {
    const cheapest = p.prices.sort(
      (a, b) => (a.promo_price ?? a.price) - (b.promo_price ?? b.price),
    )[0];
    if (cheapest) totalMin += cheapest.promo_price ?? cheapest.price;
  });

  // Tri des produits par prix effectif
  const sortedProducts = [...products].sort((a, b) => {
    const pa = a.prices[0] ? (a.prices[0].promo_price ?? a.prices[0].price) : Infinity;
    const pb = b.prices[0] ? (b.prices[0].promo_price ?? b.prices[0].price) : Infinity;
    return pa - pb;
  });

  const refetchAll = () => results.forEach((r) => r.refetch());

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={results.some((r) => r.isRefetching)}
            onRefresh={refetchAll}
            tintColor={C.primary}
          />
        }
      >
        {isLoading && (
          <View style={styles.centered}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Chargement de la comparaison…</Text>
          </View>
        )}

        {isError && (
          <View style={styles.centered}>
            <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
            <Text style={styles.errorText}>Erreur lors de la comparaison</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={refetchAll}>
              <Text style={styles.retryBtnText}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        )}

        {products.length > 0 && (
          <>
            {/* Résumé panier */}
            <View style={styles.summaryCard}>
              <View style={styles.summaryLeft}>
                <Text style={styles.summaryLabel}>Panier le moins cher</Text>
                <Text style={styles.summaryValue}>{totalMin.toFixed(2)} MAD</Text>
              </View>
              <View style={styles.summaryRight}>
                <Text style={styles.summarySubLabel}>{products.length} produit{products.length > 1 ? 's' : ''}</Text>
                <Text style={styles.summarySubLabel}>{allStores.length} magasin{allStores.length > 1 ? 's' : ''}</Text>
              </View>
            </View>

            {/* Produits par prix */}
            <Text style={styles.sectionTitle}>Produits comparés</Text>
            {sortedProducts.map((p, i) => {
              const bestStore = p.prices.sort(
                (a, b) => (a.promo_price ?? a.price) - (b.promo_price ?? b.price),
              )[0]?.store_name ?? '—';
              return (
                <TouchableOpacity
                  key={p.id}
                  onPress={() => navigation.navigate('ProduitDetail', { productId: p.id, productName: p.name })}
                >
                  <ProductRow product={p} storeName={bestStore} rank={i} />
                </TouchableOpacity>
              );
            })}

            {/* Comparaison par magasin */}
            {allStores.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Panier par magasin</Text>
                {allStores.map((store) => (
                  <StoreComparisonCard
                    key={store}
                    storeName={store}
                    products={products}
                    totalMin={totalMin}
                  />
                ))}
              </>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F2F6F0' },
  content: { padding: 16, paddingBottom: 32 },
  centered: { alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#4A5B53', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: { backgroundColor: C.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 10 },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  summaryCard: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#0C3F30', borderRadius: 20, padding: 22, marginBottom: 16,
    shadowColor: '#0C3F30',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 14,
    elevation: 8,
  },
  summaryLeft: {},
  summaryLabel: { fontSize: 13, color: 'rgba(255,255,255,0.75)', marginBottom: 6, fontWeight: '500', letterSpacing: 0.2 },
  summaryValue: { fontSize: 30, fontWeight: '900', color: '#fff', letterSpacing: -0.5 },
  summaryRight: { alignItems: 'flex-end', gap: 6 },
  summarySubLabel: {
    fontSize: 12, color: 'rgba(255,255,255,0.85)', fontWeight: '700',
    backgroundColor: 'rgba(255,255,255,0.18)', borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  sectionTitle: {
    fontSize: 12, fontWeight: '700', color: '#4A5B53',
    marginBottom: 10, marginTop: 4,
    textTransform: 'uppercase', letterSpacing: 0.8,
  },
  productRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', borderRadius: 16, padding: 14, marginBottom: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.07, shadowRadius: 8, elevation: 3,
    borderWidth: 1, borderColor: '#E2E9DF',
  },
  productRowBest: { borderColor: C.primary, borderWidth: 2, backgroundColor: '#EEF6F1', shadowColor: '#0F4C3A', shadowOpacity: 0.12 },
  rankBadge: {
    width: 34, height: 34, borderRadius: 17, backgroundColor: '#E9F0E6',
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  rankText: { fontSize: 14, fontWeight: '800', color: '#4A5B53' },
  rankTextBest: { color: C.primary },
  productRowInfo: { flex: 1 },
  productRowName: { fontSize: 14, fontWeight: '700', color: '#0B2019', marginBottom: 2 },
  productRowBrand: { fontSize: 12, color: '#4A5B53', marginBottom: 2 },
  productRowStore: { fontSize: 12, color: '#8A9A92' },
  productRowPrice: { alignItems: 'flex-end', gap: 2 },
  originalPrice: { fontSize: 12, color: '#8A9A92', textDecorationLine: 'line-through' },
  effectivePrice: { fontSize: 16, fontWeight: '800', color: '#0B2019' },
  naPrice: { fontSize: 16, color: '#8A9A92' },
  promoBadge: {
    backgroundColor: '#fef2f2', borderRadius: 4, paddingHorizontal: 5, paddingVertical: 1,
    borderWidth: 1, borderColor: '#fecaca',
  },
  promoBadgeText: { color: '#C1272D', fontSize: 9, fontWeight: '700' },
  storeCard: {
    backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#E2E9DF',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
  },
  storeCardDisabled: { backgroundColor: '#F2F6F0', opacity: 0.7 },
  storeCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  storeName: { flex: 1, fontSize: 15, fontWeight: '700', color: '#0B2019' },
  savingBadge: { backgroundColor: '#EEF6F1', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  savingBadgeNeg: { backgroundColor: '#FDF3DE' },
  savingBadgeBest: { backgroundColor: '#D3E8DC', borderWidth: 1, borderColor: '#6FB294' },
  savingText: { fontSize: 12, fontWeight: '700', color: C.primary },
  savingTextNeg: { color: '#92400e' },
  savingTextBest: { color: '#0C3F30', fontSize: 11, fontWeight: '800' },
  storeCardBest: { borderColor: '#0F4C3A', borderWidth: 2, backgroundColor: '#EEF6F1' },
  storeTotal: { fontSize: 13, color: '#4A5B53', marginLeft: 26 },
});

export default ComparerPrixScreen;
