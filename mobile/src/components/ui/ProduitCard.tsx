/**
 * ProduitCard — Composant réutilisable
 *
 * Variantes :
 *   variant="list"    → carte horizontale compacte (dans FlashList)
 *   variant="grid"    → carte verticale (grille 2 colonnes)
 *   variant="detail"  → carte enrichie avec infos prix et magasins
 *
 * Props optionnelles :
 *   onCompare        → affiche le bouton "Comparer" (icône scales)
 *   onAlert          → affiche le bouton "Alerte" (icône bell)
 *   isInCompare      → met en évidence si produit sélectionné pour comparer
 */
import React, { memo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, C } from '@constants/colors';
import ProductVisual from './ProductVisual';
import type { ProductSummary } from '@types/models';

// ── Props ─────────────────────────────────────────────────────────────────────

interface ProduitCardProps {
  product: ProductSummary;
  variant?: 'list' | 'grid' | 'detail';
  onPress?: () => void;
  onCompare?: () => void;
  onAlert?: () => void;
  isInCompare?: boolean;
}

// ── Utilitaires ───────────────────────────────────────────────────────────────

const formatPrice = (price: number | null | undefined): string => {
  if (price == null) return '—';
  return `${price.toFixed(2)} DH`;
};

const discountPct = (regular: number, lowest: number): number =>
  Math.round(((regular - lowest) / regular) * 100);

// ── Badge Promo ───────────────────────────────────────────────────────────────

const PromoBadge = memo(({ pct }: { pct: number }) => (
  <View style={styles.promoBadge}>
    <Text style={styles.promoBadgeText}>-{pct}%</Text>
  </View>
));

// ── Variante LIST ─────────────────────────────────────────────────────────────

const CardList = memo(({ product, onPress, onCompare, onAlert, isInCompare }: ProduitCardProps) => {
  const showDiscount =
    product.has_promo &&
    product.highest_price != null &&
    product.lowest_price != null &&
    product.highest_price > product.lowest_price;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={[styles.listCard, isInCompare && styles.listCardSelected]}
    >
      {/* Image */}
      <View style={styles.listImageWrap}>
        <ProductVisual name={product.name} imageUrl={product.image_url} size={72} radius={10} />
        {product.has_promo && showDiscount && (
          <PromoBadge pct={discountPct(product.highest_price!, product.lowest_price!)} />
        )}
      </View>

      {/* Contenu */}
      <View style={styles.listContent}>
        {product.brand ? (
          <Text style={styles.brand} numberOfLines={1}>{product.brand}</Text>
        ) : null}
        <Text style={styles.listName} numberOfLines={2}>{product.name}</Text>

        <View style={styles.listMeta}>
          {product.category && (
            <Text style={styles.category}>{product.category.name}</Text>
          )}
          {product.unit_size && (
            <Text style={styles.unitSize}>{product.unit_size}</Text>
          )}
        </View>

        {/* Prix */}
        <View style={styles.listPriceRow}>
          {product.lowest_price != null ? (
            <>
              <Text style={styles.priceMin}>{formatPrice(product.lowest_price)}</Text>
              {product.store_count > 1 && (
                <Text style={styles.storeCount}>
                  {product.store_count} magasins
                </Text>
              )}
            </>
          ) : (
            <Text style={styles.noPrice}>Prix indisponible</Text>
          )}
        </View>
      </View>

      {/* Actions */}
      <View style={styles.listActions}>
        {onAlert && (
          <TouchableOpacity onPress={onAlert} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} style={styles.actionBtn}>
            <Ionicons name="notifications-outline" size={20} color={Colors.text.secondary} />
          </TouchableOpacity>
        )}
        {onCompare && (
          <TouchableOpacity onPress={onCompare} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} style={styles.actionBtn}>
            <Ionicons
              name={isInCompare ? 'git-compare' : 'git-compare-outline'}
              size={20}
              color={isInCompare ? C.primary : Colors.text.secondary}
            />
          </TouchableOpacity>
        )}
        <Ionicons name="chevron-forward" size={18} color={Colors.text.tertiary} />
      </View>
    </TouchableOpacity>
  );
});

// ── Variante GRID ─────────────────────────────────────────────────────────────

const CardGrid = memo(({ product, onPress, onCompare, isInCompare }: ProduitCardProps) => {
  const showDiscount =
    product.has_promo &&
    product.highest_price != null &&
    product.lowest_price != null &&
    product.highest_price > product.lowest_price;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={[styles.gridCard, isInCompare && styles.gridCardSelected]}
    >
      {/* Image */}
      <View style={styles.gridImageWrap}>
        <ProductVisual name={product.name} imageUrl={product.image_url} size={96} radius={14} />
        {product.has_promo && showDiscount && (
          <PromoBadge pct={discountPct(product.highest_price!, product.lowest_price!)} />
        )}
      </View>

      {/* Contenu */}
      <View style={styles.gridContent}>
        {product.brand ? (
          <Text style={styles.brand} numberOfLines={1}>{product.brand}</Text>
        ) : null}
        <Text style={styles.gridName} numberOfLines={2}>{product.name}</Text>

        <View style={styles.gridBottom}>
          {product.lowest_price != null ? (
            <Text style={styles.gridPrice}>{formatPrice(product.lowest_price)}</Text>
          ) : (
            <Text style={styles.noPrice}>—</Text>
          )}

          {onCompare && (
            <TouchableOpacity onPress={onCompare} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <Ionicons
                name={isInCompare ? 'git-compare' : 'git-compare-outline'}
                size={18}
                color={isInCompare ? C.primary : Colors.text.tertiary}
              />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
});

// ── Variante DETAIL ───────────────────────────────────────────────────────────

const CardDetail = memo(({ product, onPress, onCompare, onAlert, isInCompare }: ProduitCardProps) => {
  const spread = product.highest_price != null && product.lowest_price != null
    ? product.highest_price - product.lowest_price
    : null;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.78}
      style={[styles.detailCard, isInCompare && styles.detailCardSelected]}
    >
      {/* En-tête */}
      <View style={styles.detailHeader}>
        <ProductVisual name={product.name} imageUrl={product.image_url} size={80} radius={12} />
        <View style={styles.detailHeaderText}>
          {product.brand && <Text style={styles.brand}>{product.brand}</Text>}
          <Text style={styles.detailName} numberOfLines={3}>{product.name}</Text>
          {product.unit_size && (
            <Text style={styles.unitSize}>{product.unit_size}</Text>
          )}
          {product.category && (
            <View style={styles.categoryPill}>
              <Text style={styles.categoryPillText}>{product.category.name}</Text>
            </View>
          )}
        </View>
      </View>

      {/* Bloc prix */}
      <View style={styles.detailPriceBlock}>
        <View style={styles.detailPriceCol}>
          <Text style={styles.detailPriceLabel}>Moins cher</Text>
          <Text style={[styles.detailPriceValue, { color: Colors.success }]}>
            {formatPrice(product.lowest_price)}
          </Text>
        </View>
        <View style={[styles.detailPriceCol, styles.detailPriceBorder]}>
          <Text style={styles.detailPriceLabel}>Plus cher</Text>
          <Text style={[styles.detailPriceValue, { color: Colors.error }]}>
            {formatPrice(product.highest_price)}
          </Text>
        </View>
        <View style={styles.detailPriceCol}>
          <Text style={styles.detailPriceLabel}>Économie max</Text>
          <Text style={[styles.detailPriceValue, { color: C.gold }]}>
            {spread != null ? formatPrice(spread) : '—'}
          </Text>
        </View>
      </View>

      {/* Footer */}
      <View style={styles.detailFooter}>
        <Text style={styles.storeCount}>
          <Ionicons name="storefront-outline" size={13} color={Colors.text.tertiary} />
          {' '}{product.store_count} magasin{product.store_count > 1 ? 's' : ''}
        </Text>
        {product.has_promo && (
          <View style={styles.promoTag}>
            <Text style={styles.promoTagText}>🔥 Promo disponible</Text>
          </View>
        )}
        <View style={styles.detailActions}>
          {onAlert && (
            <TouchableOpacity onPress={onAlert} style={styles.detailActionBtn}>
              <Ionicons name="notifications-outline" size={18} color={C.primary} />
            </TouchableOpacity>
          )}
          {onCompare && (
            <TouchableOpacity onPress={onCompare} style={styles.detailActionBtn}>
              <Ionicons
                name={isInCompare ? 'git-compare' : 'git-compare-outline'}
                size={18}
                color={isInCompare ? C.primary : Colors.text.secondary}
              />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
});

// ── Composant principal ───────────────────────────────────────────────────────

const ProduitCard = memo(function ProduitCard(props: ProduitCardProps) {
  const { variant = 'list' } = props;
  if (variant === 'grid')   return <CardGrid {...props} />;
  if (variant === 'detail') return <CardDetail {...props} />;
  return <CardList {...props} />;
});

export default ProduitCard;

// ── Styles ────────────────────────────────────────────────────────────────────

const SHADOW = Platform.select({
  ios: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 6,
  },
  android: { elevation: 3 },
});

const styles = StyleSheet.create({
  // ── Shared ────────────────────────────────────────────────────────────────
  brand: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.text.tertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  category: {
    fontSize: 11,
    color: Colors.text.tertiary,
  },
  unitSize: {
    fontSize: 11,
    color: Colors.text.tertiary,
    marginLeft: 6,
  },
  storeCount: {
    fontSize: 12,
    color: Colors.text.tertiary,
  },
  noPrice: {
    fontSize: 13,
    color: Colors.text.tertiary,
    fontStyle: 'italic',
  },
  promoBadge: {
    position: 'absolute',
    top: 4,
    right: 4,
    backgroundColor: Colors.promo,
    borderRadius: 6,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  promoBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  actionBtn: {
    padding: 4,
    marginBottom: 4,
  },

  // ── LIST ──────────────────────────────────────────────────────────────────
  listCard: {
    flexDirection: 'row',
    backgroundColor: Colors.surface.card,
    marginHorizontal: 16,
    marginVertical: 5,
    borderRadius: 14,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: 'transparent',
    ...SHADOW,
  },
  listCardSelected: {
    borderColor: C.primary,
    backgroundColor: Colors.primary[50],
  },
  listImageWrap: {
    width: 72,
    height: 72,
    borderRadius: 10,
    backgroundColor: Colors.surface.tertiary,
    overflow: 'visible',
    marginRight: 12,
    position: 'relative',
  },
  listImage: {
    width: 72,
    height: 72,
    borderRadius: 10,
  },
  listContent: {
    flex: 1,
    minWidth: 0,
  },
  listName: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.text.primary,
    lineHeight: 19,
  },
  listMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 3,
  },
  listPriceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 8,
  },
  priceMin: {
    fontSize: 16,
    fontWeight: '800',
    color: Colors.success,
  },
  listActions: {
    alignItems: 'center',
    marginLeft: 8,
  },

  // ── GRID ──────────────────────────────────────────────────────────────────
  gridCard: {
    flex: 1,
    backgroundColor: Colors.surface.card,
    margin: 5,
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 1.5,
    borderColor: 'transparent',
    ...SHADOW,
  },
  gridCardSelected: {
    borderColor: C.primary,
    backgroundColor: Colors.primary[50],
  },
  gridImageWrap: {
    backgroundColor: Colors.surface.tertiary,
    height: 120,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  gridImage: {
    width: 100,
    height: 100,
  },
  gridContent: {
    padding: 10,
  },
  gridName: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.text.primary,
    lineHeight: 17,
    marginTop: 2,
    marginBottom: 8,
  },
  gridBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  gridPrice: {
    fontSize: 15,
    fontWeight: '800',
    color: Colors.success,
  },

  // ── DETAIL ────────────────────────────────────────────────────────────────
  detailCard: {
    backgroundColor: Colors.surface.card,
    marginHorizontal: 16,
    marginVertical: 6,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: 'transparent',
    overflow: 'hidden',
    ...SHADOW,
  },
  detailCardSelected: {
    borderColor: C.primary,
  },
  detailHeader: {
    flexDirection: 'row',
    padding: 14,
    gap: 12,
  },
  detailImage: {
    width: 80,
    height: 80,
    borderRadius: 10,
    backgroundColor: Colors.surface.tertiary,
  },
  detailHeaderText: {
    flex: 1,
  },
  detailName: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.text.primary,
    lineHeight: 20,
    marginBottom: 4,
  },
  categoryPill: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.primary[100],
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 4,
  },
  categoryPillText: {
    fontSize: 11,
    color: C.primaryDark,
    fontWeight: '600',
  },
  detailPriceBlock: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: Colors.border.light,
  },
  detailPriceCol: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
  },
  detailPriceBorder: {
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: Colors.border.light,
  },
  detailPriceLabel: {
    fontSize: 10,
    color: Colors.text.tertiary,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  detailPriceValue: {
    fontSize: 15,
    fontWeight: '800',
  },
  detailFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: Colors.border.light,
    gap: 8,
  },
  promoTag: {
    backgroundColor: '#fef2f2',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 20,
  },
  promoTagText: {
    fontSize: 11,
    color: Colors.promo,
    fontWeight: '600',
  },
  detailActions: {
    flexDirection: 'row',
    marginLeft: 'auto',
    gap: 4,
  },
  detailActionBtn: {
    padding: 8,
    backgroundColor: Colors.surface.secondary,
    borderRadius: 20,
  },
});
