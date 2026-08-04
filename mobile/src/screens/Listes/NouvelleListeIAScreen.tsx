import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  Alert,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { IAAPI, ListsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ListesStackParamList, ListType, GeneratedList, GeneratedListItem } from '@types/models';

type Props = NativeStackScreenProps<ListesStackParamList, 'NouvelleListeIA'>;

const LIST_TYPES: { value: ListType; label: string; icon: string; desc: string }[] = [
  { value: 'hebdo',      label: 'Hebdomadaire', icon: '📅', desc: 'Courses pour 1 semaine' },
  { value: 'bi-mensuel', label: 'Bi-mensuel',   icon: '🗓️', desc: 'Courses pour 2 semaines' },
  { value: 'mensuel',    label: 'Mensuel',       icon: '📆', desc: 'Courses pour 1 mois' },
];

// ── Helpers catégories ────────────────────────────────────────────────────────

/** Ordre d'affichage des catégories dans la liste */
const CATEGORY_ORDER = [
  '💧 Eau & Boissons',
  '🌾 Pain & Céréales',
  '🥚 Œufs',
  '🫘 Légumineuses',
  '🥦 Légumes & Herbes',
  '🍊 Fruits frais',
  '🐟 Poissons & Fruits de mer',
  '🍗 Volaille (halal)',
  '🥩 Viande rouge (halal)',
  '🥛 Produits laitiers',
  '🫒 Huiles & Corps gras',
  '🧂 Épices & Condiments',
  '🍵 Thé, Café & Sucre',
  '🍯 Petit-déjeuner marocain',
  '🧴 Hygiène & Entretien',
  '👶 Bébé',
  '🛒 Divers',
];

function groupByCategory(items: GeneratedListItem[]): Array<{ cat: string; items: GeneratedListItem[]; subtotal: number }> {
  const map = new Map<string, GeneratedListItem[]>();
  items.forEach((item) => {
    const cat = item.category || '🛒 Divers';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(item);
  });
  // Trier selon CATEGORY_ORDER, puis les inconnues à la fin
  const known = CATEGORY_ORDER.filter((c) => map.has(c));
  const unknown = [...map.keys()].filter((c) => !CATEGORY_ORDER.includes(c));
  return [...known, ...unknown].map((cat) => ({
    cat,
    items: map.get(cat)!,
    subtotal: map.get(cat)!.reduce((s, i) => s + i.estimated_price_total, 0),
  }));
}

// ── Carte article généré ──────────────────────────────────────────────────────

const GeneratedItemCard: React.FC<{ item: GeneratedListItem }> = ({ item }) => (
  <View style={styles.itemCard}>
    <View style={styles.itemLeft}>
      <Text style={styles.itemName} numberOfLines={2}>{item.product_name}</Text>
      {item.store_name && (
        <Text style={styles.itemStore}>
          <Ionicons name="storefront-outline" size={11} color="#94a3b8" /> {item.store_name}
        </Text>
      )}
      {item.is_promo && (
        <View style={styles.promoBadge}><Text style={styles.promoBadgeText}>PROMO</Text></View>
      )}
      {item.reasoning ? (
        <Text style={styles.itemReasoning} numberOfLines={2}>{item.reasoning}</Text>
      ) : null}
    </View>
    <View style={styles.itemRight}>
      <Text style={styles.itemQty}>× {item.quantity}{item.unit ? ` ${item.unit}` : ''}</Text>
      <Text style={styles.itemPrice}>{item.estimated_price_total.toFixed(2)} MAD</Text>
    </View>
  </View>
);

// ── Section catégorie ─────────────────────────────────────────────────────────

const CategorySection: React.FC<{
  cat: string;
  items: GeneratedListItem[];
  subtotal: number;
}> = ({ cat, items, subtotal }) => {
  const [open, setOpen] = useState(true);
  return (
    <View style={styles.catSection}>
      <TouchableOpacity style={styles.catHeader} onPress={() => setOpen((v) => !v)} activeOpacity={0.7}>
        <Text style={styles.catTitle}>{cat}</Text>
        <View style={styles.catHeaderRight}>
          <Text style={styles.catSubtotal}>{subtotal.toFixed(2)} MAD</Text>
          <Text style={styles.catCount}>{items.length} art.</Text>
          <Ionicons
            name={open ? 'chevron-up' : 'chevron-down'}
            size={16}
            color="#64748b"
          />
        </View>
      </TouchableOpacity>
      {open && items.map((item, i) => <GeneratedItemCard key={i} item={item} />)}
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const HOUSEHOLD_OPTIONS = [1, 2, 3, 4, 5, 6];

const NouvelleListeIAScreen: React.FC<Props> = ({ navigation }) => {
  const queryClient = useQueryClient();
  const [listType, setListType] = useState<ListType>('hebdo');
  const [budgetText, setBudgetText] = useState('');
  const [householdSize, setHouseholdSize] = useState(1);
  const [generatedList, setGeneratedList] = useState<GeneratedList | null>(null);
  const [saving, setSaving] = useState(false);

  const generateMutation = useMutation({
    mutationFn: () =>
      IAAPI.generateList({
        list_type: listType,
        budget_max: budgetText ? parseFloat(budgetText) : undefined,
        household_size: householdSize,
      }),
    onSuccess: (data) => setGeneratedList(data),
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Impossible de générer la liste. Réessayez.';
      Alert.alert('Erreur IA', msg);
    },
  });

  const handleSave = async () => {
    if (!generatedList) return;
    setSaving(true);
    try {
      const typeLabel = LIST_TYPES.find((t) => t.value === listType)?.label ?? listType;
      const date = new Date().toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' });
      const list = await ListsAPI.create({
        name: `Liste ${typeLabel} — ${date}`,
        description: generatedList.global_reasoning?.slice(0, 120),
      });
      // Ajoute les articles
      await Promise.all(
        generatedList.items.map((item) =>
          ListsAPI.addItem(list.id, {
            custom_name: item.product_name,
            quantity: item.quantity,
            product_id: item.product_id ?? undefined,
          }),
        ),
      );
      queryClient.invalidateQueries({ queryKey: ['shopping-lists'] });
      Alert.alert(
        'Liste sauvegardée !',
        `"${list.name}" a été ajoutée à vos listes.`,
        [{ text: 'Voir mes listes', onPress: () => navigation.navigate('MesListes') }],
      );
    } catch {
      Alert.alert('Erreur', 'Impossible de sauvegarder la liste.');
    } finally {
      setSaving(false);
    }
  };

  const handleShareWhatsApp = () => {
    if (!generatedList) return;
    const typeLabel = LIST_TYPES.find((t) => t.value === listType)?.label ?? listType;
    const date = new Date().toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' });

    let text = `🛒 *Liste ${typeLabel} — ${date}*\n`;
    text += `👥 ${householdSize} personne${householdSize > 1 ? 's' : ''}\n\n`;

    // Grouper par catégorie
    const grouped = groupByCategory(generatedList.items);
    grouped.forEach(({ cat, items: catItems, subtotal }) => {
      text += `*${cat}*\n`;
      catItems.forEach((i) => {
        const qty = i.quantity > 1 ? ` × ${i.quantity}${i.unit ? ` ${i.unit}` : ''}` : '';
        const promo = i.is_promo ? ' 🏷️' : '';
        text += `  • ${i.product_name}${qty} — ${i.estimated_price_total.toFixed(2)} MAD${promo}\n`;
      });
      text += `  _Sous-total : ${subtotal.toFixed(2)} MAD_\n\n`;
    });

    text += `💰 *Total estimé : ${generatedList.total_estimated.toFixed(2)} MAD*\n`;
    if (generatedList.recommended_stores.length > 0) {
      text += `🏪 Conseillé : ${generatedList.recommended_stores.join(', ')}\n`;
    }
    text += `\n_Généré par PrixMaroc IA 🇲🇦_`;

    Linking.openURL(`whatsapp://send?text=${encodeURIComponent(text)}`).catch(() =>
      Alert.alert('WhatsApp non disponible', "Installez WhatsApp pour partager votre liste."),
    );
  };

  const budgetStatus = generatedList?.budget_status;
  const budgetColor =
    budgetStatus === 'dans_budget' ? C.primary :
    budgetStatus === 'dépasse_budget' ? '#ef4444' : '#94a3b8';

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {/* Header IA */}
        <View style={styles.iaHeader}>
          <View style={styles.iaIconWrap}>
            <Ionicons name="sparkles" size={32} color={C.primary} />
          </View>
          <Text style={styles.iaTitle}>Liste générée par IA</Text>
          <Text style={styles.iaSubtitle}>
            L'IA analyse vos habitudes d'achat et propose une liste optimisée selon votre budget.
          </Text>
        </View>

        {/* Sélection du type */}
        <Text style={styles.sectionTitle}>Type de liste</Text>
        <View style={styles.typeGrid}>
          {LIST_TYPES.map((t) => (
            <TouchableOpacity
              key={t.value}
              style={[styles.typeCard, listType === t.value && styles.typeCardActive]}
              onPress={() => setListType(t.value)}
            >
              <Text style={styles.typeIcon}>{t.icon}</Text>
              <Text style={[styles.typeLabel, listType === t.value && { color: C.primary }]}>
                {t.label}
              </Text>
              <Text style={styles.typeDesc}>{t.desc}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Effectif du foyer */}
        <Text style={styles.sectionTitle}>Effectif du foyer</Text>
        <View style={styles.householdRow}>
          {HOUSEHOLD_OPTIONS.map((n) => (
            <TouchableOpacity
              key={n}
              style={[styles.householdBtn, householdSize === n && styles.householdBtnActive]}
              onPress={() => setHouseholdSize(n)}
            >
              <Text style={[styles.householdNum, householdSize === n && { color: C.primary }]}>
                {n}
              </Text>
              <Text style={[styles.householdLabel, householdSize === n && { color: C.primary }]}>
                {n === 1 ? 'pers.' : 'pers.'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Budget optionnel */}
        <Text style={styles.sectionTitle}>Budget maximum (optionnel)</Text>
        <View style={styles.budgetInput}>
          <TextInput
            style={styles.budgetField}
            placeholder="Ex : 500"
            placeholderTextColor="#9ca3af"
            value={budgetText}
            onChangeText={setBudgetText}
            keyboardType="decimal-pad"
          />
          <Text style={styles.budgetCurrency}>MAD</Text>
        </View>

        {/* Bouton générer */}
        {!generatedList && (
          <TouchableOpacity
            style={[styles.generateBtn, generateMutation.isPending && styles.generateBtnDisabled]}
            onPress={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? (
              <View style={styles.generateBtnInner}>
                <ActivityIndicator color="#fff" size="small" />
                <Text style={styles.generateBtnText}>Génération en cours…</Text>
              </View>
            ) : (
              <View style={styles.generateBtnInner}>
                <Ionicons name="sparkles" size={20} color="#fff" />
                <Text style={styles.generateBtnText}>Générer ma liste</Text>
              </View>
            )}
          </TouchableOpacity>
        )}

        {/* Résultats */}
        {generatedList && (
          <>
            {/* Résumé */}
            <View style={styles.resultSummary}>
              <View style={styles.resultSummaryLeft}>
                <Text style={styles.resultSummaryLabel}>Total estimé</Text>
                <Text style={styles.resultSummaryValue}>
                  {generatedList.total_estimated.toFixed(2)} MAD
                </Text>
              </View>
              <View style={styles.resultSummaryRight}>
                <View style={[styles.budgetBadge, { backgroundColor: `${budgetColor}18` }]}>
                  <Text style={[styles.budgetBadgeText, { color: budgetColor }]}>
                    {budgetStatus === 'dans_budget' ? '✓ Dans le budget' :
                     budgetStatus === 'dépasse_budget' ? '⚠ Budget dépassé' : 'Sans budget'}
                  </Text>
                </View>
                <Text style={styles.resultItemCount}>
                  {generatedList.items.length} article{generatedList.items.length > 1 ? 's' : ''}
                </Text>
              </View>
            </View>

            {/* Magasins conseillés */}
            {generatedList.recommended_stores.length > 0 && (
              <View style={styles.storesRow}>
                <Ionicons name="storefront-outline" size={14} color="#64748b" />
                <Text style={styles.storesLabel}>Conseillé : </Text>
                <Text style={styles.storesValue}>
                  {generatedList.recommended_stores.join(', ')}
                </Text>
              </View>
            )}

            {/* Raisonnement global */}
            {generatedList.global_reasoning && (
              <View style={styles.reasoningCard}>
                <Ionicons name="information-circle-outline" size={16} color="#64748b" />
                <Text style={styles.reasoningText}>{generatedList.global_reasoning}</Text>
              </View>
            )}

            {/* Articles regroupés par catégorie */}
            <Text style={styles.sectionTitle}>
              Articles ({generatedList.items.length})
            </Text>
            {groupByCategory(generatedList.items).map(({ cat, items: catItems, subtotal }) => (
              <CategorySection key={cat} cat={cat} items={catItems} subtotal={subtotal} />
            ))}

            {/* Actions */}
            <View style={styles.resultActions}>
              <TouchableOpacity
                style={[styles.regenerateBtn, generateMutation.isPending && { opacity: 0.65 }]}
                onPress={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                {generateMutation.isPending
                  ? <ActivityIndicator size="small" color={C.primary} />
                  : <Ionicons name="refresh" size={18} color={C.primary} />
                }
                <Text style={styles.regenerateBtnText}>
                  {generateMutation.isPending ? 'Génération…' : 'Régénérer'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.whatsappBtn} onPress={handleShareWhatsApp}>
                <Ionicons name="logo-whatsapp" size={18} color="#25D366" />
                <Text style={styles.whatsappBtnText}>Partager</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
                {saving
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <>
                      <Ionicons name="save-outline" size={18} color="#fff" />
                      <Text style={styles.saveBtnText}>Sauvegarder</Text>
                    </>
                }
              </TouchableOpacity>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 20, paddingBottom: 40 },
  iaHeader: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  iaIconWrap: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: '#f0fdf4',
    alignItems: 'center', justifyContent: 'center', marginBottom: 4,
  },
  iaTitle: { fontSize: 22, fontWeight: '800', color: '#0f172a' },
  iaSubtitle: { fontSize: 14, color: '#64748b', textAlign: 'center', lineHeight: 20, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#0f172a', marginBottom: 10, marginTop: 8 },
  typeGrid: { flexDirection: 'row', gap: 8, marginBottom: 20 },
  typeCard: {
    flex: 1, backgroundColor: '#fff', borderRadius: 14, padding: 12, alignItems: 'center',
    borderWidth: 2, borderColor: '#e2e8f0', gap: 4,
  },
  typeCardActive: { borderColor: C.primary, backgroundColor: '#f0fdf4' },
  typeIcon: { fontSize: 22 },
  typeLabel: { fontSize: 12, fontWeight: '700', color: '#475569', textAlign: 'center' },
  typeDesc: { fontSize: 10, color: '#94a3b8', textAlign: 'center' },
  householdRow: {
    flexDirection: 'row', gap: 8, marginBottom: 20,
  },
  householdBtn: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#fff', borderRadius: 12, paddingVertical: 10,
    borderWidth: 2, borderColor: '#e2e8f0',
  },
  householdBtnActive: { borderColor: C.primary, backgroundColor: '#f0fdf4' },
  householdNum: { fontSize: 18, fontWeight: '800', color: '#475569' },
  householdLabel: { fontSize: 9, color: '#94a3b8', marginTop: 1 },
  budgetInput: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', borderRadius: 12, borderWidth: 1, borderColor: '#e2e8f0',
    paddingHorizontal: 14, marginBottom: 20,
  },
  budgetField: { flex: 1, fontSize: 16, color: '#0f172a', paddingVertical: 14 },
  budgetCurrency: { fontSize: 15, fontWeight: '700', color: '#64748b' },
  generateBtn: {
    backgroundColor: C.primary, borderRadius: 14, paddingVertical: 16,
    marginBottom: 8,
    shadowColor: C.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 6,
  },
  generateBtnDisabled: { backgroundColor: '#94a3b8' },
  generateBtnInner: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  generateBtnText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  resultSummary: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#fff', borderRadius: 16, padding: 16, marginBottom: 8,
    borderWidth: 1, borderColor: '#e2e8f0',
  },
  resultSummaryLeft: {},
  resultSummaryLabel: { fontSize: 13, color: '#64748b', marginBottom: 4 },
  resultSummaryValue: { fontSize: 26, fontWeight: '900', color: '#0f172a' },
  resultSummaryRight: { alignItems: 'flex-end', gap: 6 },
  budgetBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  budgetBadgeText: { fontSize: 12, fontWeight: '700' },
  resultItemCount: { fontSize: 13, color: '#94a3b8' },
  storesRow: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#fff', borderRadius: 10, padding: 10, marginBottom: 8,
    borderWidth: 1, borderColor: '#e2e8f0',
  },
  storesLabel: { fontSize: 13, color: '#64748b' },
  storesValue: { fontSize: 13, fontWeight: '600', color: '#0f172a', flex: 1 },
  reasoningCard: {
    flexDirection: 'row', gap: 8, backgroundColor: '#f0f9ff',
    borderRadius: 12, padding: 12, marginBottom: 12,
    borderWidth: 1, borderColor: '#bae6fd',
  },
  reasoningText: { flex: 1, fontSize: 13, color: '#0369a1', lineHeight: 18 },
  catSection: {
    marginBottom: 6,
  },
  catHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#f1f5f9', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10,
    marginBottom: 4,
  },
  catTitle: {
    fontSize: 14, fontWeight: '700', color: '#0f172a', flex: 1,
  },
  catHeaderRight: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
  },
  catSubtotal: {
    fontSize: 13, fontWeight: '800', color: C.primary,
  },
  catCount: {
    fontSize: 11, color: '#94a3b8', fontWeight: '600',
  },
  itemCard: {
    flexDirection: 'row', backgroundColor: '#fff', borderRadius: 12, padding: 12, marginBottom: 4,
    marginLeft: 4,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 3, elevation: 1,
  },
  itemLeft: { flex: 1 },
  itemName: { fontSize: 14, fontWeight: '700', color: '#0f172a', marginBottom: 3 },
  itemStore: { fontSize: 12, color: '#94a3b8', marginBottom: 3 },
  promoBadge: {
    alignSelf: 'flex-start', backgroundColor: '#fef2f2', borderRadius: 4,
    paddingHorizontal: 5, paddingVertical: 1, marginBottom: 3,
    borderWidth: 1, borderColor: '#fecaca',
  },
  promoBadgeText: { color: '#dc2626', fontSize: 9, fontWeight: '700' },
  itemReasoning: { fontSize: 11, color: '#94a3b8', fontStyle: 'italic', lineHeight: 16 },
  itemRight: { alignItems: 'flex-end', gap: 4, marginLeft: 12 },
  itemQty: { fontSize: 12, color: '#64748b', fontWeight: '600' },
  itemPrice: { fontSize: 15, fontWeight: '800', color: C.primary },
  resultActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  regenerateBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, borderWidth: 1.5, borderColor: C.primary, borderRadius: 12, paddingVertical: 14,
  },
  regenerateBtnText: { color: C.primary, fontWeight: '700', fontSize: 13 },
  whatsappBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, borderWidth: 1.5, borderColor: '#25D366', borderRadius: 12, paddingVertical: 14,
    backgroundColor: '#f0fdf4',
  },
  whatsappBtnText: { color: '#16a34a', fontWeight: '700', fontSize: 13 },
  saveBtn: {
    flex: 1.5, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14,
  },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
});

export default NouvelleListeIAScreen;
