import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  Keyboard,
  Modal,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { ProductsAPI } from '@services/api';
import ProductVisual from '@components/ui/ProductVisual';
import { C } from '@constants/colors';
import type { ComparerStackParamList, ProductSummary } from '@types/models';

type Props = NativeStackScreenProps<ComparerStackParamList, 'Recherche'>;

// ── Filtres ───────────────────────────────────────────────────────────────────

const BUDGET_OPTIONS = [
  { label: 'Tous', value: 0 },
  { label: '< 10 MAD', value: 10 },
  { label: '< 20 MAD', value: 20 },
  { label: '< 50 MAD', value: 50 },
  { label: '< 100 MAD', value: 100 },
];

interface Filters {
  brand: string;
  budgetMax: number;
  promoOnly: boolean;
}

const DEFAULT_FILTERS: Filters = { brand: '', budgetMax: 0, promoOnly: false };

const FilterModal: React.FC<{
  visible: boolean;
  filters: Filters;
  onChange: (f: Filters) => void;
  onClose: () => void;
}> = ({ visible, filters, onChange, onClose }) => {
  const [local, setLocal] = useState<Filters>(filters);

  const applyAndClose = () => {
    onChange(local);
    onClose();
  };

  const reset = () => {
    setLocal(DEFAULT_FILTERS);
    onChange(DEFAULT_FILTERS);
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={fm.overlay}>
        <View style={fm.sheet}>
          <View style={fm.sheetHeader}>
            <Text style={fm.sheetTitle}>Filtres</Text>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={24} color="#374151" />
            </TouchableOpacity>
          </View>

          {/* Marque */}
          <Text style={fm.label}>Marque</Text>
          <TextInput
            style={fm.input}
            placeholder="Ex : Danone, Nestlé, Lesieur…"
            placeholderTextColor="#9ca3af"
            value={local.brand}
            onChangeText={(v) => setLocal((f) => ({ ...f, brand: v }))}
            autoCorrect={false}
          />

          {/* Budget max */}
          <Text style={fm.label}>Budget maximum</Text>
          <View style={fm.budgetRow}>
            {BUDGET_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                style={[fm.budgetBtn, local.budgetMax === opt.value && fm.budgetBtnActive]}
                onPress={() => setLocal((f) => ({ ...f, budgetMax: opt.value }))}
              >
                <Text style={[fm.budgetText, local.budgetMax === opt.value && fm.budgetTextActive]}>
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Promos seulement */}
          <TouchableOpacity
            style={[fm.promoToggle, local.promoOnly && fm.promoToggleActive]}
            onPress={() => setLocal((f) => ({ ...f, promoOnly: !f.promoOnly }))}
          >
            <Ionicons
              name={local.promoOnly ? 'checkmark-circle' : 'ellipse-outline'}
              size={22}
              color={local.promoOnly ? C.primary : '#94a3b8'}
            />
            <Text style={[fm.promoToggleText, local.promoOnly && { color: C.primary }]}>
              Promotions uniquement
            </Text>
          </TouchableOpacity>

          {/* Boutons */}
          <View style={fm.actions}>
            <TouchableOpacity style={fm.resetBtn} onPress={reset}>
              <Text style={fm.resetText}>Réinitialiser</Text>
            </TouchableOpacity>
            <TouchableOpacity style={fm.applyBtn} onPress={applyAndClose}>
              <Text style={fm.applyText}>Appliquer</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const fm = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.45)' },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 44,
    gap: 12,
  },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  sheetTitle: { fontSize: 20, fontWeight: '800', color: '#0f172a' },
  label: { fontSize: 13, fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 },
  input: {
    backgroundColor: '#f1f5f9', borderRadius: 10, padding: 12,
    fontSize: 15, color: '#0f172a',
  },
  budgetRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  budgetBtn: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10,
    borderWidth: 1.5, borderColor: '#e2e8f0', backgroundColor: '#f8fafc',
  },
  budgetBtnActive: { borderColor: C.primary, backgroundColor: '#f0fdf4' },
  budgetText: { fontSize: 13, fontWeight: '600', color: '#64748b' },
  budgetTextActive: { color: C.primary },
  promoToggle: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    padding: 12, borderRadius: 10, borderWidth: 1.5, borderColor: '#e2e8f0',
  },
  promoToggleActive: { borderColor: C.primary, backgroundColor: '#f0fdf4' },
  promoToggleText: { fontSize: 14, fontWeight: '600', color: '#64748b' },
  actions: { flexDirection: 'row', gap: 12, marginTop: 8 },
  resetBtn: {
    flex: 1, paddingVertical: 14, borderRadius: 12,
    backgroundColor: '#f1f5f9', alignItems: 'center',
  },
  resetText: { color: '#64748b', fontWeight: '700', fontSize: 15 },
  applyBtn: {
    flex: 2, paddingVertical: 14, borderRadius: 12,
    backgroundColor: C.primary, alignItems: 'center',
  },
  applyText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});

// ── Image avec fallback si URL cassée ────────────────────────────────────────

const ImageWithFallback: React.FC<{ uri: string }> = ({ uri }) => {
  const [errored, setErrored] = useState(false);
  if (errored) {
    return (
      <View style={styles.productImagePlaceholder}>
        <Ionicons name="image-outline" size={22} color="#cbd5e1" />
        <Text style={styles.productImagePlaceholderText}>Photo{'\n'}à venir</Text>
      </View>
    );
  }
  return (
    <Image
      source={{ uri }}
      style={styles.productImage}
      resizeMode="contain"
      onError={() => setErrored(true)}
    />
  );
};

// ── Carte produit ─────────────────────────────────────────────────────────────

const ProductCard: React.FC<{
  item: ProductSummary;
  onPress: () => void;
  onHistorique: () => void;
}> = ({ item, onPress, onHistorique }) => (
  <TouchableOpacity style={styles.productCard} onPress={onPress} activeOpacity={0.75}>
    <View style={styles.productImageWrap}>
      <ProductVisual name={item.name} imageUrl={item.image_url} size={64} radius={10} />
      {item.has_promo && (
        <View style={styles.promoBadge}>
          <Text style={styles.promoBadgeText}>PROMO</Text>
        </View>
      )}
    </View>

    <View style={styles.productInfo}>
      <Text style={styles.productName} numberOfLines={2}>{item.name}</Text>
      {item.brand ? <Text style={styles.productBrand}>{item.brand}</Text> : null}
      {item.unit_size ? <Text style={styles.productUnit}>{item.unit_size}</Text> : null}

      <View style={styles.priceRow}>
        {item.lowest_price != null ? (
          <Text style={styles.priceFrom}>
            Dès{' '}
            <Text style={styles.priceValue}>{item.lowest_price.toFixed(2)} MAD</Text>
          </Text>
        ) : (
          <Text style={styles.priceUnavailable}>Prix non disponible</Text>
        )}
        {item.store_count > 0 && (
          <Text style={styles.storeCount}>
            {item.store_count} magasin{item.store_count > 1 ? 's' : ''}
          </Text>
        )}
      </View>
    </View>

    <View style={styles.productActions}>
      <Ionicons name="chevron-forward" size={20} color="#d1d5db" />
      <TouchableOpacity
        style={styles.historiqueBtn}
        onPress={(e) => { e.stopPropagation(); onHistorique(); }}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="trending-up-outline" size={18} color={C.primary} />
      </TouchableOpacity>
    </View>
  </TouchableOpacity>
);

// ── Écran principal ───────────────────────────────────────────────────────────

const RechercheScreen: React.FC<Props> = ({ navigation }) => {
  const [query, setQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Live search : déclenche la recherche 350ms après la dernière frappe
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    if (trimmed.length >= 2) {
      debounceRef.current = setTimeout(() => {
        setSearchTerm(trimmed);
      }, 350);
    } else {
      setSearchTerm('');
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const hasActiveFilters = filters.brand !== '' || filters.budgetMax > 0 || filters.promoOnly;
  const activeCount = [
    filters.brand !== '',
    filters.budgetMax > 0,
    filters.promoOnly,
  ].filter(Boolean).length;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['products-search', searchTerm, filters],
    queryFn: () =>
      ProductsAPI.search({
        q: searchTerm,
        limit: 40,
        ...(filters.brand ? { brand: filters.brand } : {}),
      }),
    enabled: searchTerm.length >= 2,
  });

  // Filtrage côté client (budget max + promoOnly)
  const rawResults = data?.data ?? [];
  const filteredResults = rawResults.filter((p) => {
    if (filters.budgetMax > 0 && (p.lowest_price == null || p.lowest_price > filters.budgetMax))
      return false;
    if (filters.promoOnly && !p.has_promo) return false;
    return true;
  });

  const handleSearch = useCallback(() => {
    Keyboard.dismiss();
    const t = query.trim();
    if (t.length >= 2) setSearchTerm(t);
  }, [query]);

  const clearSearch = () => {
    setQuery('');
    setSearchTerm('');
  };

  const goToDetail = (item: ProductSummary) =>
    navigation.navigate('ProduitDetail', { productId: item.id, productName: item.name });

  const goToHistorique = (item: ProductSummary) =>
    navigation.navigate('HistoriquePrix', { productId: item.id, productName: item.name });

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      {/* Barre de recherche */}
      <View style={styles.searchBar}>
        <View style={styles.searchInputWrap}>
          {isLoading ? (
            <ActivityIndicator size="small" color={C.primary} style={{ marginRight: 8 }} />
          ) : (
            <Ionicons name="search-outline" size={18} color="#9ca3af" style={{ marginRight: 8 }} />
          )}
          <TextInput
            style={styles.searchInput}
            placeholder="Tapez un produit ou une marque…"
            placeholderTextColor="#9ca3af"
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
            autoCorrect={false}
            autoFocus={false}
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={clearSearch} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close-circle" size={18} color="#9ca3af" />
            </TouchableOpacity>
          )}
        </View>
        {/* Bouton filtres */}
        <TouchableOpacity
          style={[styles.filterBtn, hasActiveFilters && styles.filterBtnActive]}
          onPress={() => setShowFilters(true)}
        >
          <Ionicons
            name="options-outline"
            size={20}
            color={hasActiveFilters ? '#15803d' : 'rgba(255,255,255,0.9)'}
          />
          {activeCount > 0 && (
            <View style={styles.filterBadge}>
              <Text style={styles.filterBadgeText}>{activeCount}</Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      {/* Chips filtres actifs */}
      {hasActiveFilters && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
        >
          {filters.brand !== '' && (
            <TouchableOpacity
              style={styles.chip}
              onPress={() => setFilters((f) => ({ ...f, brand: '' }))}
            >
              <Text style={styles.chipText}>Marque : {filters.brand}</Text>
              <Ionicons name="close" size={14} color={C.primary} />
            </TouchableOpacity>
          )}
          {filters.budgetMax > 0 && (
            <TouchableOpacity
              style={styles.chip}
              onPress={() => setFilters((f) => ({ ...f, budgetMax: 0 }))}
            >
              <Text style={styles.chipText}>{'< '}{filters.budgetMax} MAD</Text>
              <Ionicons name="close" size={14} color={C.primary} />
            </TouchableOpacity>
          )}
          {filters.promoOnly && (
            <TouchableOpacity
              style={styles.chip}
              onPress={() => setFilters((f) => ({ ...f, promoOnly: false }))}
            >
              <Text style={styles.chipText}>Promos seulement</Text>
              <Ionicons name="close" size={14} color={C.primary} />
            </TouchableOpacity>
          )}
        </ScrollView>
      )}

      {/* État vide (avant recherche) */}
      {searchTerm.length < 2 && query.length < 2 && !isLoading && (
        <View style={styles.emptyState}>
          <Ionicons name="search-circle-outline" size={72} color="#d1d5db" />
          <Text style={styles.emptyTitle}>Comparez les prix</Text>
          <Text style={styles.emptySubtitle}>
            Les résultats apparaissent au fur et à mesure que vous tapez.{'\n'}
            Saisissez au moins 2 caractères.
          </Text>
        </View>
      )}

      {/* Erreur */}
      {isError && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
          <Text style={styles.errorText}>Erreur lors de la recherche</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Résultats */}
      {data && (
        <FlatList
          data={filteredResults}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <ProductCard
              item={item}
              onPress={() => goToDetail(item)}
              onHistorique={() => goToHistorique(item)}
            />
          )}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          ListHeaderComponent={
            filteredResults.length > 0 ? (
              <Text style={styles.resultsHeader}>
                {filteredResults.length} résultat{filteredResults.length > 1 ? 's' : ''}
                {hasActiveFilters ? ' (filtrés)' : ''} pour «{searchTerm}»
              </Text>
            ) : null
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Ionicons name="cube-outline" size={64} color="#d1d5db" />
              <Text style={styles.emptyTitle}>Aucun résultat</Text>
              <Text style={styles.emptySubtitle}>
                {hasActiveFilters
                  ? 'Essayez de modifier vos filtres'
                  : 'Essayez un autre terme de recherche'}
              </Text>
              {hasActiveFilters && (
                <TouchableOpacity
                  style={styles.resetFiltersBtn}
                  onPress={() => setFilters(DEFAULT_FILTERS)}
                >
                  <Text style={styles.resetFiltersBtnText}>Effacer les filtres</Text>
                </TouchableOpacity>
              )}
            </View>
          }
        />
      )}

      {/* Modal filtres */}
      <FilterModal
        visible={showFilters}
        filters={filters}
        onChange={setFilters}
        onClose={() => setShowFilters(false)}
      />
    </SafeAreaView>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f1f5f9' },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 14,
    backgroundColor: '#15803d',
    gap: 8,
  },
  searchInputWrap: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 9,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  searchInput: { flex: 1, fontSize: 15, color: '#0f172a' },
  filterBtn: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  filterBtnActive: { backgroundColor: 'rgba(255,255,255,0.95)' },
  filterBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#dc2626',
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterBadgeText: { color: '#fff', fontSize: 10, fontWeight: '700' },
  chipsRow: { paddingHorizontal: 16, paddingVertical: 8, gap: 8 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#f0fdf4',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  chipText: { fontSize: 12, fontWeight: '600', color: C.primary },
  listContent: { paddingVertical: 10, paddingHorizontal: 14 },
  resultsHeader: {
    fontSize: 13,
    color: '#64748b',
    marginBottom: 10,
    marginTop: 2,
    fontWeight: '500',
  },
  productCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  },
  productImageWrap: {
    width: 68,
    height: 68,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#f1f5f9',
    marginRight: 14,
    position: 'relative',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  productImage: { width: 68, height: 68 },
  productImagePlaceholder: {
    width: 68,
    height: 68,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f8fafc',
    gap: 2,
  },
  productImagePlaceholderText: {
    fontSize: 9,
    color: '#cbd5e1',
    textAlign: 'center',
    lineHeight: 12,
    fontWeight: '500',
  },
  promoBadge: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: '#dc2626',
    paddingVertical: 2,
    alignItems: 'center',
  },
  promoBadgeText: { color: '#ffffff', fontSize: 9, fontWeight: '700', letterSpacing: 0.3 },
  productInfo: { flex: 1 },
  productName: { fontSize: 14, fontWeight: '700', color: '#0f172a', marginBottom: 3, lineHeight: 19 },
  productBrand: { fontSize: 12, color: '#64748b', marginBottom: 2 },
  productUnit: { fontSize: 11, color: '#94a3b8', marginBottom: 6 },
  priceRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
  priceFrom: { fontSize: 13, color: '#475569' },
  priceValue: { fontWeight: '800', color: C.primary, fontSize: 15 },
  priceUnavailable: { fontSize: 12, color: '#94a3b8', fontStyle: 'italic' },
  storeCount: {
    fontSize: 11, color: '#64748b', fontWeight: '600',
    backgroundColor: '#f1f5f9', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2,
  },
  productActions: { alignItems: 'center', gap: 10, marginLeft: 6 },
  historiqueBtn: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: '#f0fdf4',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
    paddingTop: 60,
    gap: 12,
  },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#374151', marginTop: 16, marginBottom: 6 },
  emptySubtitle: { fontSize: 14, color: '#9ca3af', textAlign: 'center', lineHeight: 22 },
  resetFiltersBtn: {
    backgroundColor: C.primary,
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
    marginTop: 8,
  },
  resetFiltersBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  loadingContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingText: { color: '#64748b', fontSize: 15 },
  errorContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: {
    backgroundColor: C.primary,
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
    marginTop: 8,
  },
  retryBtnText: { color: '#ffffff', fontWeight: '700', fontSize: 14 },
});

export default RechercheScreen;
