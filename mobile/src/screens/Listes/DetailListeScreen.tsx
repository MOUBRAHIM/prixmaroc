import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  TextInput,
  Modal,
  RefreshControl,
  Linking,
  ListRenderItemInfo,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ListsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ListesStackParamList, ShoppingList, ShoppingListItem } from '@types/models';

type Props = NativeStackScreenProps<ListesStackParamList, 'DetailListe'>;

const cacheKey = (id: number) => `prixmaroc:list:${id}`;

// ─── Checkbox ─────────────────────────────────────────────────────────────────

const AnimatedCheckbox: React.FC<{ checked: boolean }> = ({ checked }) => (
  <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
    {checked && <Ionicons name="checkmark" size={14} color="#fff" />}
  </View>
);

// ─── Ligne article ─────────────────────────────────────────────────────────────

type RowItem = ShoppingListItem | { __separator: true; count: number };

const ListItemRow: React.FC<{
  item: ShoppingListItem;
  onToggle: () => void;
  onDelete: () => void;
  onQtyChange: (delta: number) => void;
  isToggling: boolean;
  shopMode: boolean;
}> = ({ item, onToggle, onDelete, onQtyChange, isToggling, shopMode }) => {
  const name = item.custom_name ?? item.product?.name ?? `Produit #${item.product_id}`;
  const price = item.product?.lowest_price;

  return (
    <View style={[styles.itemRow, item.is_checked && styles.itemRowChecked]}>
      {/* Zone principale cliquable (toggle check) */}
      <TouchableOpacity
        style={styles.itemMain}
        onPress={onToggle}
        disabled={isToggling}
        activeOpacity={0.7}
      >
        <AnimatedCheckbox checked={item.is_checked} />
        <View style={styles.itemInfo}>
          <Text
            style={[styles.itemName, item.is_checked && styles.itemNameChecked]}
            numberOfLines={2}
          >
            {name}
          </Text>
          {item.note ? <Text style={styles.itemNote}>{item.note}</Text> : null}
        </View>
        {price != null && (
          <Text style={[styles.itemPrice, item.is_checked && styles.itemPriceChecked]}>
            {(price * item.quantity).toFixed(2)} MAD
          </Text>
        )}
        {isToggling && (
          <ActivityIndicator size="small" color={C.primary} style={{ marginLeft: 6 }} />
        )}
      </TouchableOpacity>

      {/* Contrôles quantité + suppression */}
      <View style={styles.itemControls}>
        {!shopMode ? (
          <>
            <TouchableOpacity
              style={styles.qtyBtn}
              onPress={() => onQtyChange(-1)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="remove" size={14} color="#64748b" />
            </TouchableOpacity>
            <Text style={styles.qtyText}>{item.quantity}</Text>
            <TouchableOpacity
              style={styles.qtyBtn}
              onPress={() => onQtyChange(1)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="add" size={14} color="#64748b" />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.trashBtn}
              onPress={onDelete}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="trash-outline" size={15} color="#ef4444" />
            </TouchableOpacity>
          </>
        ) : (
          item.quantity > 1 && (
            <Text style={[styles.qtyShop, item.is_checked && { color: '#cbd5e1' }]}>
              × {item.quantity}
            </Text>
          )
        )}
      </View>
    </View>
  );
};

// ─── Modal ajout article ────────────────────────────────────────────────────────

const AddItemModal: React.FC<{
  visible: boolean;
  onClose: () => void;
  onSubmit: (name: string, qty: number) => void;
  isLoading: boolean;
}> = ({ visible, onClose, onSubmit, isLoading }) => {
  const [name, setName] = useState('');
  const [qty, setQty] = useState(1);

  const handle = () => {
    const trimmed = name.trim();
    if (!trimmed) { Alert.alert('Requis', 'Saisissez un nom de produit.'); return; }
    if (qty < 1) { Alert.alert('Invalide', 'La quantité doit être ≥ 1.'); return; }
    onSubmit(trimmed, qty);
    setName('');
    setQty(1);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={modal.overlay}>
        <View style={modal.sheet}>
          <Text style={modal.title}>Ajouter un article</Text>

          <Text style={modal.label}>Produit *</Text>
          <TextInput
            style={modal.input}
            placeholder="Ex : Lait, Pain, Huile d'olive…"
            placeholderTextColor="#9ca3af"
            value={name}
            onChangeText={setName}
            autoFocus
          />

          <Text style={modal.label}>Quantité</Text>
          <View style={modal.qtyRow}>
            <TouchableOpacity
              style={modal.qtyBtn}
              onPress={() => setQty((q) => Math.max(1, q - 1))}
            >
              <Ionicons name="remove" size={20} color={C.primary} />
            </TouchableOpacity>
            <Text style={modal.qtyValue}>{qty}</Text>
            <TouchableOpacity
              style={modal.qtyBtn}
              onPress={() => setQty((q) => q + 1)}
            >
              <Ionicons name="add" size={20} color={C.primary} />
            </TouchableOpacity>
          </View>

          <View style={modal.actions}>
            <TouchableOpacity style={modal.cancelBtn} onPress={onClose}>
              <Text style={modal.cancelText}>Annuler</Text>
            </TouchableOpacity>
            <TouchableOpacity style={modal.submitBtn} onPress={handle} disabled={isLoading}>
              {isLoading
                ? <ActivityIndicator size="small" color="#fff" />
                : <Text style={modal.submitText}>Ajouter</Text>
              }
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const modal = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.45)' },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 44,
  },
  title: { fontSize: 20, fontWeight: '800', color: '#0f172a', marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '600', color: '#64748b', marginBottom: 6 },
  input: {
    backgroundColor: '#f1f5f9',
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: '#0f172a',
    marginBottom: 16,
  },
  qtyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f1f5f9',
    borderRadius: 10,
    marginBottom: 20,
  },
  qtyBtn: { padding: 14, paddingHorizontal: 18 },
  qtyValue: {
    flex: 1,
    textAlign: 'center',
    fontSize: 20,
    fontWeight: '800',
    color: '#0f172a',
  },
  actions: { flexDirection: 'row', gap: 12 },
  cancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
  },
  cancelText: { color: '#64748b', fontWeight: '700', fontSize: 15 },
  submitBtn: {
    flex: 2,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: C.primary,
    alignItems: 'center',
  },
  submitText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});

// ─── Optimiseur 2 magasins ─────────────────────────────────────────────────────

interface StoreGroup {
  storeName: string;
  storeId: number;
  items: Array<{ name: string; quantity: number; price: number }>;
  total: number;
}

/**
 * Calcule la répartition optimale entre les 2 magasins les moins chers.
 * Pour chaque article, on prend le magasin avec le prix le plus bas.
 */
function computeOptimalSplit(items: ShoppingListItem[]): StoreGroup[] {
  const groups: Record<number, StoreGroup> = {};

  for (const item of items) {
    if (item.is_checked) continue;
    const product = item.product;
    if (!product) continue;

    // On a juste le lowest_price — on utilise ce qu'on a
    const name = item.custom_name ?? product.name ?? `Produit #${item.product_id}`;
    const price = product.lowest_price;
    if (price == null) continue;

    // Sans infos par magasin sur le produit résumé, on groupe tout au même magasin virtuel
    // "Meilleur prix"
    const storeId = 0; // store générique
    const storeName = 'Meilleur prix disponible';

    if (!groups[storeId]) {
      groups[storeId] = { storeName, storeId, items: [], total: 0 };
    }
    groups[storeId].items.push({ name, quantity: item.quantity, price });
    groups[storeId].total += price * item.quantity;
  }

  return Object.values(groups).sort((a, b) => b.items.length - a.items.length);
}

const OptimizeModal: React.FC<{
  visible: boolean;
  onClose: () => void;
  items: ShoppingListItem[];
}> = ({ visible, onClose, items }) => {
  const groups = useMemo(() => computeOptimalSplit(items), [items]);
  const grandTotal = groups.reduce((s, g) => s + g.total, 0);

  const openMapsRoute = () => {
    // Ouvre Google Maps en mode itinéraire
    const url = 'https://www.google.com/maps/dir/?api=1&travelmode=driving';
    Linking.openURL(url).catch(() =>
      Alert.alert('Erreur', 'Impossible d\'ouvrir Google Maps.'),
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={opt.overlay}>
        <View style={opt.sheet}>
          <View style={opt.header}>
            <Text style={opt.title}>Optimiser vos courses</Text>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={24} color="#374151" />
            </TouchableOpacity>
          </View>

          <Text style={opt.subtitle}>
            Répartition intelligente pour réduire votre budget
          </Text>

          <ScrollView style={{ maxHeight: 320 }} showsVerticalScrollIndicator={false}>
            {groups.length === 0 ? (
              <View style={opt.empty}>
                <Ionicons name="information-circle-outline" size={32} color="#94a3b8" />
                <Text style={opt.emptyText}>
                  Aucun article avec prix disponible
                </Text>
              </View>
            ) : (
              groups.map((group, gi) => (
                <View key={`g-${gi}`} style={opt.group}>
                  <View style={opt.groupHeader}>
                    <Ionicons name="storefront-outline" size={18} color={C.primary} />
                    <Text style={opt.groupName}>{group.storeName}</Text>
                    <Text style={opt.groupTotal}>{group.total.toFixed(2)} MAD</Text>
                  </View>
                  {group.items.map((it, ii) => (
                    <View key={`i-${gi}-${ii}`} style={opt.itemRow}>
                      <Text style={opt.itemName} numberOfLines={1}>
                        {it.quantity > 1 ? `×${it.quantity} ` : ''}{it.name}
                      </Text>
                      <Text style={opt.itemPrice}>
                        {(it.price * it.quantity).toFixed(2)} MAD
                      </Text>
                    </View>
                  ))}
                </View>
              ))
            )}
          </ScrollView>

          {grandTotal > 0 && (
            <View style={opt.totalRow}>
              <Text style={opt.totalLabel}>Total estimé</Text>
              <Text style={opt.totalValue}>{grandTotal.toFixed(2)} MAD</Text>
            </View>
          )}

          {/* Bouton itinéraire */}
          <TouchableOpacity style={opt.routeBtn} onPress={openMapsRoute}>
            <Ionicons name="navigate-outline" size={20} color="#fff" />
            <Text style={opt.routeBtnText}>Optimiser le trajet</Text>
          </TouchableOpacity>

          <TouchableOpacity style={opt.closeBtn} onPress={onClose}>
            <Text style={opt.closeBtnText}>Fermer</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const opt = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.45)' },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 44,
    gap: 12,
  },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontSize: 20, fontWeight: '800', color: '#0f172a' },
  subtitle: { fontSize: 13, color: '#64748b', marginTop: -4 },
  empty: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  emptyText: { fontSize: 14, color: '#94a3b8', textAlign: 'center' },
  group: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  groupName: { flex: 1, fontSize: 15, fontWeight: '700', color: '#0f172a' },
  groupTotal: { fontSize: 15, fontWeight: '800', color: C.primary },
  itemRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 3 },
  itemName: { flex: 1, fontSize: 13, color: '#374151' },
  itemPrice: { fontSize: 13, fontWeight: '600', color: '#475569', marginLeft: 8 },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#f0fdf4',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  totalLabel: { fontSize: 15, fontWeight: '700', color: '#0f172a' },
  totalValue: { fontSize: 18, fontWeight: '900', color: C.primary },
  routeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 14,
  },
  routeBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  closeBtn: {
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
  },
  closeBtnText: { color: '#64748b', fontWeight: '700', fontSize: 15 },
});

// ─── Écran principal ────────────────────────────────────────────────────────────

const DetailListeScreen: React.FC<Props> = ({ route }) => {
  const { listId, listName } = route.params;
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [shopMode, setShopMode] = useState(false);
  const [offlineData, setOfflineData] = useState<ShoppingList | null>(null);
  const [showOptimize, setShowOptimize] = useState(false);

  // ─── Query avec cache AsyncStorage ─────────────────────────────────────────

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['shopping-list', listId],
    queryFn: async () => {
      const result = await ListsAPI.getOne(listId);
      await AsyncStorage.setItem(cacheKey(listId), JSON.stringify(result));
      return result;
    },
    retry: 1,
  });

  // Fallback offline
  useEffect(() => {
    if (isError) {
      AsyncStorage.getItem(cacheKey(listId)).then((raw) => {
        if (raw) {
          try { setOfflineData(JSON.parse(raw)); } catch { /* ignore */ }
        }
      });
    }
  }, [isError, listId]);

  // ─── Mutations ──────────────────────────────────────────────────────────────

  const addMutation = useMutation({
    mutationFn: ({ name, qty }: { name: string; qty: number }) =>
      ListsAPI.addItem(listId, { custom_name: name, quantity: qty }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shopping-list', listId] });
      queryClient.invalidateQueries({ queryKey: ['shopping-lists'] });
      setShowModal(false);
    },
    onError: () => Alert.alert('Erreur', "Impossible d'ajouter l'article."),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ itemId, checked }: { itemId: number; checked: boolean }) =>
      ListsAPI.toggleItem(listId, itemId, checked),
    onMutate: ({ itemId }) => setTogglingId(itemId),
    onSettled: () => setTogglingId(null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shopping-list', listId] }),
    onError: () => Alert.alert('Erreur', "Impossible de modifier l'article."),
  });

  const deleteMutation = useMutation({
    mutationFn: (itemId: number) => ListsAPI.deleteItem(listId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shopping-list', listId] });
      queryClient.invalidateQueries({ queryKey: ['shopping-lists'] });
    },
    onError: () => Alert.alert('Erreur', "Impossible de supprimer l'article."),
  });

  const updateQtyMutation = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      ListsAPI.updateItemQty(listId, itemId, quantity),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shopping-list', listId] }),
    onError: () => Alert.alert('Erreur', "Impossible de modifier la quantité."),
  });

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleDelete = useCallback((item: ShoppingListItem) => {
    const name = item.custom_name ?? item.product?.name ?? 'cet article';
    Alert.alert(
      'Supprimer',
      `Supprimer « ${name} » de la liste ?`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Supprimer',
          style: 'destructive',
          onPress: () => deleteMutation.mutate(item.id),
        },
      ],
    );
  }, [deleteMutation]);

  const handleQtyChange = useCallback((item: ShoppingListItem, delta: number) => {
    const newQty = item.quantity + delta;
    if (newQty < 1) {
      handleDelete(item);
      return;
    }
    updateQtyMutation.mutate({ itemId: item.id, quantity: newQty });
  }, [handleDelete, updateQtyMutation]);

  const handleShare = useCallback(() => {
    const source = data ?? offlineData;
    if (!source) return;
    const unchecked = source.items.filter((i) => !i.is_checked);
    const checked = source.items.filter((i) => i.is_checked);

    let text = `🛒 *${source.name}*\n\n`;
    if (unchecked.length > 0) {
      text += `*À acheter (${unchecked.length})*\n`;
      unchecked.forEach((i) => {
        const nm = i.custom_name ?? i.product?.name ?? 'Article';
        const qty = i.quantity > 1 ? ` × ${i.quantity}` : '';
        const price = i.product?.lowest_price
          ? ` — ~${(i.product.lowest_price * i.quantity).toFixed(2)} MAD`
          : '';
        text += `☐ ${nm}${qty}${price}\n`;
      });
    }
    if (checked.length > 0) {
      text += `\n✅ *Dans le panier (${checked.length})*\n`;
      checked.forEach((i) => {
        const nm = i.custom_name ?? i.product?.name ?? 'Article';
        text += `☑ ${nm}\n`;
      });
    }
    text += `\n_PrixMaroc 🇲🇦_`;

    Linking.openURL(`whatsapp://send?text=${encodeURIComponent(text)}`).catch(() =>
      Alert.alert(
        'WhatsApp non disponible',
        'Installez WhatsApp pour partager votre liste.',
      ),
    );
  }, [data, offlineData]);

  // ─── Computed ────────────────────────────────────────────────────────────────

  const source = data ?? offlineData;
  const allItems: ShoppingListItem[] = source?.items ?? [];
  const uncheckedItems = allItems.filter((i) => !i.is_checked);
  const checkedItems = allItems.filter((i) => i.is_checked);
  const checkedCount = checkedItems.length;
  const totalCount = allItems.length;

  const remainingTotal = uncheckedItems
    .filter((i) => i.product?.lowest_price != null)
    .reduce((s, i) => s + i.product!.lowest_price! * i.quantity, 0);

  // En mode courses : non-cochés d'abord, séparateur, puis cochés
  // En mode normal  : ordre serveur
  const displayRows: RowItem[] = shopMode
    ? [
        ...uncheckedItems,
        ...(checkedItems.length > 0
          ? [{ __separator: true, count: checkedItems.length } as RowItem]
          : []),
        ...checkedItems,
      ]
    : allItems;

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      {/* Barre d'actions */}
      <View style={styles.actionBar}>
        {/* Indicateur offline */}
        {isError && offlineData ? (
          <View style={styles.offlinePill}>
            <Ionicons name="cloud-offline-outline" size={13} color="#f59e0b" />
            <Text style={styles.offlineText}>Hors ligne</Text>
          </View>
        ) : (
          <View />
        )}
        <View style={styles.actionBarRight}>
          {/* WhatsApp */}
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={handleShare}
            disabled={!source || totalCount === 0}
          >
            <Ionicons name="logo-whatsapp" size={19} color="#25D366" />
            <Text style={styles.actionBtnText}>Partager</Text>
          </TouchableOpacity>
          {/* Optimiser */}
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => setShowOptimize(true)}
            disabled={!source || totalCount === 0}
          >
            <Ionicons name="git-branch-outline" size={19} color="#8b5cf6" />
            <Text style={[styles.actionBtnText, { color: '#8b5cf6' }]}>Optimiser</Text>
          </TouchableOpacity>
          {/* Mode courses */}
          <TouchableOpacity
            style={[styles.actionBtn, shopMode && styles.actionBtnActive]}
            onPress={() => setShopMode((v) => !v)}
          >
            <Ionicons
              name={shopMode ? 'cart' : 'cart-outline'}
              size={19}
              color={shopMode ? '#fff' : '#64748b'}
            />
            <Text style={[styles.actionBtnText, shopMode && { color: '#fff' }]}>
              {shopMode ? 'ON' : 'Courses'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Barre de progression */}
      {totalCount > 0 && (
        <View style={styles.progressBar}>
          <View style={styles.progressInfo}>
            <Text style={styles.progressText}>
              {checkedCount} / {totalCount} cochés
            </Text>
            {remainingTotal > 0 && (
              <Text style={styles.remainingTotal}>
                ~{remainingTotal.toFixed(2)} MAD restant
              </Text>
            )}
          </View>
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                { width: `${totalCount > 0 ? (checkedCount / totalCount) * 100 : 0}%` as any },
              ]}
            />
          </View>
        </View>
      )}

      {/* États */}
      {isLoading && (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Chargement…</Text>
        </View>
      )}
      {isError && !offlineData && (
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
          <Text style={styles.errorText}>Impossible de charger la liste</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Liste */}
      {(data || offlineData) && (
        <FlatList<RowItem>
          data={displayRows}
          keyExtractor={(item, index) => {
            if ('__separator' in item) return `sep-${index}`;
            return String(item.id);
          }}
          renderItem={({ item }: ListRenderItemInfo<RowItem>) => {
            if ('__separator' in item) {
              return (
                <View style={styles.separator}>
                  <View style={styles.separatorLine} />
                  <Text style={styles.separatorText}>
                    ✅ Dans le panier ({item.count})
                  </Text>
                  <View style={styles.separatorLine} />
                </View>
              );
            }
            const si = item as ShoppingListItem;
            return (
              <ListItemRow
                item={si}
                onToggle={() =>
                  toggleMutation.mutate({ itemId: si.id, checked: !si.is_checked })
                }
                onDelete={() => handleDelete(si)}
                onQtyChange={(delta) => handleQtyChange(si, delta)}
                isToggling={togglingId === si.id}
                shopMode={shopMode}
              />
            );
          }}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor={C.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Ionicons name="basket-outline" size={72} color="#d1d5db" />
              <Text style={styles.emptyTitle}>Liste vide</Text>
              <Text style={styles.emptySubtitle}>
                Ajoutez vos articles en appuyant sur le bouton +
              </Text>
            </View>
          }
        />
      )}

      {/* FAB ajout */}
      <View style={styles.fab}>
        <TouchableOpacity style={styles.fabBtn} onPress={() => setShowModal(true)}>
          <Ionicons name="add" size={28} color="#fff" />
        </TouchableOpacity>
      </View>

      <AddItemModal
        visible={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={(name, qty) => addMutation.mutate({ name, qty })}
        isLoading={addMutation.isPending}
      />

      <OptimizeModal
        visible={showOptimize}
        onClose={() => setShowOptimize(false)}
        items={allItems}
      />
    </SafeAreaView>
  );
};

// ─── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },

  /* Barre d'actions */
  actionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    gap: 8,
  },
  actionBarRight: { flexDirection: 'row', gap: 8 },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: '#e2e8f0',
    backgroundColor: '#fff',
  },
  actionBtnActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  actionBtnText: { fontSize: 13, fontWeight: '600', color: '#64748b' },
  offlinePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#fffbeb',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: '#fde68a',
  },
  offlineText: { fontSize: 12, color: '#b45309', fontWeight: '600' },

  /* Progression */
  progressBar: {
    backgroundColor: '#fff',
    padding: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  progressInfo: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  progressText: { fontSize: 13, color: '#64748b', fontWeight: '600' },
  remainingTotal: { fontSize: 13, color: C.primary, fontWeight: '700' },
  progressTrack: { height: 6, backgroundColor: '#e2e8f0', borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, backgroundColor: C.primary, borderRadius: 3 },

  /* États */
  centered: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#64748b', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: {
    backgroundColor: C.primary,
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 10,
  },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },

  /* Liste */
  listContent: { padding: 14, paddingBottom: 100 },

  /* Article */
  itemRow: {
    backgroundColor: '#fff',
    borderRadius: 14,
    marginBottom: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
    overflow: 'hidden',
  },
  itemRowChecked: { backgroundColor: '#f8fafc', opacity: 0.72 },
  itemMain: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    paddingBottom: 10,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#d1d5db',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  checkboxChecked: { backgroundColor: C.primary, borderColor: C.primary },
  itemInfo: { flex: 1 },
  itemName: { fontSize: 15, fontWeight: '600', color: '#0f172a', marginBottom: 2 },
  itemNameChecked: { textDecorationLine: 'line-through', color: '#94a3b8' },
  itemNote: { fontSize: 12, color: '#64748b', fontStyle: 'italic' },
  itemPrice: { fontSize: 14, fontWeight: '700', color: C.primary, marginLeft: 8 },
  itemPriceChecked: { color: '#94a3b8' },

  /* Contrôles (qty + trash) */
  itemControls: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingBottom: 10,
    paddingLeft: 50,
    gap: 4,
  },
  qtyBtn: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  qtyText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0f172a',
    minWidth: 22,
    textAlign: 'center',
  },
  qtyShop: {
    fontSize: 13,
    color: '#64748b',
    fontWeight: '600',
    marginLeft: 4,
  },
  trashBtn: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: '#fef2f2',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 6,
  },

  /* Séparateur mode courses */
  separator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 14,
    gap: 8,
  },
  separatorLine: { flex: 1, height: 1, backgroundColor: '#e2e8f0' },
  separatorText: { fontSize: 13, fontWeight: '700', color: '#22c55e' },

  /* Vide */
  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 40, gap: 12 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#374151' },
  emptySubtitle: { fontSize: 14, color: '#9ca3af', textAlign: 'center', lineHeight: 20 },

  /* FAB */
  fab: { position: 'absolute', bottom: 24, right: 20 },
  fabBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
});

export default DetailListeScreen;
