/**
 * SoukPricesScreen — Prix communautaires du souk
 * Légumes · Fruits · Viande · Poisson proposés et notés par les citoyens.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Alert, KeyboardAvoidingView, Platform, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { SoukAPI } from '@services/api';
import { C } from '@constants/colors';
import type { SoukCategory, SoukPrice, SoukPriceCreate } from '@types/models';

const CATS: { value: SoukCategory | 'all'; label: string; icon: string }[] = [
  { value: 'all',     label: 'Tous',     icon: '🧺' },
  { value: 'legumes', label: 'Légumes',  icon: '🥦' },
  { value: 'fruits',  label: 'Fruits',   icon: '🍊' },
  { value: 'viande',  label: 'Viande',   icon: '🥩' },
  { value: 'poisson', label: 'Poisson',  icon: '🐟' },
];

const UNITS = ['kg', 'botte', 'pièce', 'caisse'];

function catIcon(c: SoukCategory): string {
  return CATS.find((x) => x.value === c)?.icon ?? '🧺';
}
function timeAgo(iso: string): string {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 3600) return `il y a ${Math.max(1, Math.round(d / 60))} min`;
  if (d < 86400) return `il y a ${Math.round(d / 3600)} h`;
  return `il y a ${Math.round(d / 86400)} j`;
}

// ── Carte médiane ───────────────────────────────────────────────────────────────
const MedianCard: React.FC<{ item: { item_name: string; category: SoukCategory; unit: string; median_price: number; min_price: number; max_price: number; sample_count: number } }> = ({ item }) => (
  <View style={styles.medCard}>
    <Text style={styles.medIcon}>{catIcon(item.category)}</Text>
    <Text style={styles.medName} numberOfLines={1}>{item.item_name}</Text>
    <Text style={styles.medPrice}>{item.median_price.toFixed(2)}<Text style={styles.medUnit}> MAD/{item.unit}</Text></Text>
    <Text style={styles.medRange}>{item.min_price.toFixed(0)}–{item.max_price.toFixed(0)} · {item.sample_count} relevé{item.sample_count > 1 ? 's' : ''}</Text>
  </View>
);

// ── Ligne relevé + votes ─────────────────────────────────────────────────────────
const PriceRow: React.FC<{ p: SoukPrice; onVote: (id: number, v: 1 | -1) => void; voting: boolean }> = ({ p, onVote, voting }) => (
  <View style={styles.row}>
    <Text style={styles.rowIcon}>{catIcon(p.category)}</Text>
    <View style={{ flex: 1 }}>
      <Text style={styles.rowName}>{p.item_name}</Text>
      <Text style={styles.rowMeta} numberOfLines={1}>
        {p.neighborhood ? `${p.neighborhood} · ` : ''}{p.contributor ?? 'anonyme'} · {timeAgo(p.created_at)}
      </Text>
      {p.status === 'pending' && (
        <View style={styles.pendingTag}><Text style={styles.pendingText}>⏳ En vérification</Text></View>
      )}
    </View>
    <View style={styles.rowRight}>
      <Text style={styles.rowPrice}>{p.price.toFixed(2)}</Text>
      <Text style={styles.rowUnit}>MAD/{p.unit}</Text>
    </View>
    <View style={styles.votes}>
      <TouchableOpacity disabled={voting} onPress={() => onVote(p.id, 1)} style={styles.voteBtn} hitSlop={8}>
        <Ionicons name={p.my_vote === 1 ? 'thumbs-up' : 'thumbs-up-outline'} size={18} color={p.my_vote === 1 ? C.primary : '#8A9A92'} />
        <Text style={[styles.voteNum, p.my_vote === 1 && { color: C.primary }]}>{p.upvotes}</Text>
      </TouchableOpacity>
      <TouchableOpacity disabled={voting} onPress={() => onVote(p.id, -1)} style={styles.voteBtn} hitSlop={8}>
        <Ionicons name={p.my_vote === -1 ? 'thumbs-down' : 'thumbs-down-outline'} size={18} color={p.my_vote === -1 ? '#ef4444' : '#8A9A92'} />
        <Text style={[styles.voteNum, p.my_vote === -1 && { color: '#ef4444' }]}>{p.downvotes}</Text>
      </TouchableOpacity>
    </View>
  </View>
);

// ── Écran ─────────────────────────────────────────────────────────────────────
const SoukPricesScreen: React.FC = () => {
  const qc = useQueryClient();
  const [city, setCity] = useState('Casablanca');
  const [cat, setCat] = useState<SoukCategory | 'all'>('all');
  const [modal, setModal] = useState(false);

  const catParam = cat === 'all' ? undefined : cat;

  const medianQ = useQuery({
    queryKey: ['souk-median', city, catParam],
    queryFn: () => SoukAPI.median(city, catParam),
    enabled: city.trim().length >= 2,
  });
  const listQ = useQuery({
    queryKey: ['souk-list', city, catParam],
    queryFn: () => SoukAPI.list({ city, category: catParam, limit: 100 }),
    enabled: city.trim().length >= 2,
  });

  const voteMut = useMutation({
    mutationFn: ({ id, v }: { id: number; v: 1 | -1 }) => SoukAPI.vote(id, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['souk-list'] });
    },
    onError: () => Alert.alert('Erreur', 'Vote impossible. Réessayez.'),
  });

  const refreshing = medianQ.isFetching || listQ.isFetching;
  const onRefresh = () => { medianQ.refetch(); listQ.refetch(); };

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[C.primary]} />}
      >
        {/* Intro */}
        <View style={styles.intro}>
          <Text style={styles.introTitle}>🧺 Prix du souk</Text>
          <Text style={styles.introText}>
            Les prix des produits frais du souk, proposés et vérifiés par les citoyens. Aide la communauté en partageant ce que tu paies.
          </Text>
        </View>

        {/* Ville */}
        <View style={styles.cityBox}>
          <Ionicons name="location-outline" size={18} color={C.primary} />
          <TextInput
            style={styles.cityInput}
            value={city}
            onChangeText={setCity}
            placeholder="Ville (ex : Casablanca)"
            placeholderTextColor="#8A9A92"
          />
        </View>

        {/* Filtres catégorie */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.catRow}>
          {CATS.map((c) => (
            <TouchableOpacity
              key={c.value}
              style={[styles.catChip, cat === c.value && styles.catChipActive]}
              onPress={() => setCat(c.value)}
            >
              <Text style={styles.catChipIcon}>{c.icon}</Text>
              <Text style={[styles.catChipLabel, cat === c.value && { color: '#fff' }]}>{c.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Médianes */}
        {medianQ.data && medianQ.data.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Prix médians · {city}</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingRight: 16 }}>
              {medianQ.data.map((m, i) => <MedianCard key={`${m.item_name}-${i}`} item={m} />)}
            </ScrollView>
          </>
        )}

        {/* Relevés récents */}
        <Text style={styles.sectionTitle}>Relevés récents</Text>
        {listQ.isLoading ? (
          <ActivityIndicator color={C.primary} style={{ marginTop: 24 }} />
        ) : listQ.data && listQ.data.length > 0 ? (
          listQ.data.map((p) => (
            <PriceRow key={p.id} p={p} voting={voteMut.isPending} onVote={(id, v) => voteMut.mutate({ id, v })} />
          ))
        ) : (
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>🥬</Text>
            <Text style={styles.emptyText}>Aucun prix pour {city} pour l'instant.{'\n'}Sois le premier à en proposer un !</Text>
          </View>
        )}

        <View style={{ height: 90 }} />
      </ScrollView>

      {/* FAB */}
      <TouchableOpacity style={styles.fab} activeOpacity={0.9} onPress={() => setModal(true)}>
        <Ionicons name="add" size={24} color="#fff" />
        <Text style={styles.fabText}>Proposer un prix</Text>
      </TouchableOpacity>

      <SubmitModal
        visible={modal}
        defaultCity={city}
        onClose={() => setModal(false)}
        onSubmitted={() => { setModal(false); onRefresh(); }}
      />
    </View>
  );
};

// ── Modal de soumission ─────────────────────────────────────────────────────────
const SubmitModal: React.FC<{ visible: boolean; defaultCity: string; onClose: () => void; onSubmitted: () => void }> = ({ visible, defaultCity, onClose, onSubmitted }) => {
  const [category, setCategory] = useState<SoukCategory>('legumes');
  const [itemName, setItemName] = useState('');
  const [price, setPrice] = useState('');
  const [unit, setUnit] = useState('kg');
  const [neighborhood, setNeighborhood] = useState('');
  const [note, setNote] = useState('');

  const catInfoQ = useQuery({ queryKey: ['souk-cats'], queryFn: SoukAPI.getCategories });
  const suggestions = catInfoQ.data?.find((c) => c.value === category)?.suggestions ?? [];

  const reset = () => { setItemName(''); setPrice(''); setUnit('kg'); setNeighborhood(''); setNote(''); };

  const mut = useMutation({
    mutationFn: (payload: SoukPriceCreate) => SoukAPI.submit(payload),
    onSuccess: (data) => {
      reset();
      if (data.status === 'approved') {
        Alert.alert('Merci ! 🎉', 'Ton prix a été publié et aidera la communauté.');
      } else {
        Alert.alert('Reçu, en vérification ⏳', data.moderation_reason ?? 'Ce prix sera vérifié avant publication.');
      }
      onSubmitted();
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      Alert.alert('Erreur', typeof msg === 'string' ? msg : 'Soumission impossible. Vérifie les champs.');
    },
  });

  const submit = () => {
    const p = parseFloat(price.replace(',', '.'));
    if (itemName.trim().length < 2) return Alert.alert('Produit manquant', 'Indique le nom du produit.');
    if (!p || p <= 0) return Alert.alert('Prix invalide', 'Indique un prix en MAD.');
    if (defaultCity.trim().length < 2) return Alert.alert('Ville manquante', 'Indique la ville en haut de l\'écran.');
    mut.mutate({
      item_name: itemName.trim(), category, price: p, unit,
      city: defaultCity.trim(),
      neighborhood: neighborhood.trim() || undefined,
      note: note.trim() || undefined,
    });
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.modalWrap}>
        <View style={styles.sheet}>
          <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>Proposer un prix</Text>
            <TouchableOpacity onPress={onClose} hitSlop={8}><Ionicons name="close" size={24} color="#4A5B53" /></TouchableOpacity>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 20 }}>
            {/* Catégorie */}
            <Text style={styles.label}>Catégorie</Text>
            <View style={styles.segRow}>
              {CATS.filter((c) => c.value !== 'all').map((c) => (
                <TouchableOpacity key={c.value} style={[styles.seg, category === c.value && styles.segActive]}
                  onPress={() => setCategory(c.value as SoukCategory)}>
                  <Text style={styles.segIcon}>{c.icon}</Text>
                  <Text style={[styles.segLabel, category === c.value && { color: C.primary }]}>{c.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Produit + suggestions */}
            <Text style={styles.label}>Produit</Text>
            <TextInput style={styles.input} value={itemName} onChangeText={setItemName}
              placeholder="Ex : Tomates, Sardines…" placeholderTextColor="#8A9A92" />
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sugRow}>
              {suggestions.map((s) => (
                <TouchableOpacity key={s} style={styles.sugChip} onPress={() => setItemName(s)}>
                  <Text style={styles.sugText}>{s}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Prix + unité */}
            <Text style={styles.label}>Prix</Text>
            <View style={styles.priceRow}>
              <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]} value={price} onChangeText={setPrice}
                placeholder="0" placeholderTextColor="#8A9A92" keyboardType="decimal-pad" />
              <Text style={styles.madLabel}>MAD /</Text>
              <View style={styles.unitRow}>
                {UNITS.map((u) => (
                  <TouchableOpacity key={u} style={[styles.unitChip, unit === u && styles.unitChipActive]} onPress={() => setUnit(u)}>
                    <Text style={[styles.unitChipText, unit === u && { color: '#fff' }]}>{u}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Quartier / souk */}
            <Text style={styles.label}>Quartier / souk <Text style={styles.optional}>(optionnel)</Text></Text>
            <TextInput style={styles.input} value={neighborhood} onChangeText={setNeighborhood}
              placeholder="Ex : Souk Derb Ghallef" placeholderTextColor="#8A9A92" />

            <Text style={styles.label}>Note <Text style={styles.optional}>(optionnel)</Text></Text>
            <TextInput style={[styles.input, { height: 64 }]} value={note} onChangeText={setNote}
              placeholder="Qualité, marchand…" placeholderTextColor="#8A9A92" multiline />

            <TouchableOpacity style={[styles.submitBtn, mut.isPending && { opacity: 0.6 }]} onPress={submit} disabled={mut.isPending}>
              {mut.isPending ? <ActivityIndicator color="#fff" /> : (
                <><Ionicons name="paper-plane" size={18} color="#fff" /><Text style={styles.submitText}>Publier le prix</Text></>
              )}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#E9F0E6' },
  content: { padding: 16 },
  intro: { backgroundColor: '#EEF6F1', borderRadius: 14, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#A7D1BA' },
  introTitle: { fontSize: 17, fontWeight: '800', color: '#0B2019', marginBottom: 4 },
  introText: { fontSize: 13, color: '#093126', lineHeight: 18 },
  cityBox: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#fff', borderRadius: 12, borderWidth: 1, borderColor: '#E2E9DF', paddingHorizontal: 12, marginBottom: 12 },
  cityInput: { flex: 1, paddingVertical: 12, fontSize: 15, color: '#0B2019' },
  catRow: { gap: 8, paddingBottom: 4, paddingRight: 8 },
  catChip: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#fff', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: '#E2E9DF' },
  catChipActive: { backgroundColor: C.primary, borderColor: C.primary },
  catChipIcon: { fontSize: 14 },
  catChipLabel: { fontSize: 13, fontWeight: '700', color: '#3C4F47' },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0B2019', marginTop: 18, marginBottom: 10 },
  medCard: { width: 130, backgroundColor: '#fff', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#E2E9DF' },
  medIcon: { fontSize: 20 },
  medName: { fontSize: 13, fontWeight: '700', color: '#0B2019', marginTop: 4 },
  medPrice: { fontSize: 18, fontWeight: '900', color: C.primary, marginTop: 4 },
  medUnit: { fontSize: 11, fontWeight: '600', color: '#8A9A92' },
  medRange: { fontSize: 10, color: '#8A9A92', marginTop: 2 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EAF0E7' },
  rowIcon: { fontSize: 22 },
  rowName: { fontSize: 14, fontWeight: '700', color: '#0B2019' },
  rowMeta: { fontSize: 11, color: '#8A9A92', marginTop: 2 },
  pendingTag: { alignSelf: 'flex-start', backgroundColor: '#FDF3DE', borderRadius: 5, paddingHorizontal: 6, paddingVertical: 1, marginTop: 4 },
  pendingText: { fontSize: 10, color: '#8A6410', fontWeight: '700' },
  rowRight: { alignItems: 'flex-end' },
  rowPrice: { fontSize: 16, fontWeight: '900', color: '#0B2019' },
  rowUnit: { fontSize: 10, color: '#8A9A92' },
  votes: { alignItems: 'center', gap: 2, marginLeft: 4 },
  voteBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingVertical: 2 },
  voteNum: { fontSize: 12, fontWeight: '700', color: '#8A9A92' },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyIcon: { fontSize: 40 },
  emptyText: { fontSize: 13, color: '#8A9A92', textAlign: 'center', lineHeight: 19 },
  fab: { position: 'absolute', bottom: 20, alignSelf: 'center', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: C.primary, paddingHorizontal: 22, paddingVertical: 14, borderRadius: 28, shadowColor: C.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.35, shadowRadius: 10, elevation: 8 },
  fabText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  // modal
  modalWrap: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.45)' },
  sheet: { backgroundColor: '#fff', borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 18, maxHeight: '92%' },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  sheetTitle: { fontSize: 18, fontWeight: '800', color: '#0B2019' },
  label: { fontSize: 13, fontWeight: '700', color: '#2E4139', marginTop: 12, marginBottom: 6 },
  optional: { fontWeight: '400', color: '#8A9A92' },
  input: { backgroundColor: '#F2F6F0', borderRadius: 10, borderWidth: 1, borderColor: '#E2E9DF', paddingHorizontal: 12, paddingVertical: 11, fontSize: 15, color: '#0B2019', marginBottom: 2 },
  segRow: { flexDirection: 'row', gap: 6 },
  seg: { flex: 1, alignItems: 'center', backgroundColor: '#F2F6F0', borderRadius: 10, paddingVertical: 10, borderWidth: 2, borderColor: '#E2E9DF', gap: 2 },
  segActive: { borderColor: C.primary, backgroundColor: '#EEF6F1' },
  segIcon: { fontSize: 18 },
  segLabel: { fontSize: 11, fontWeight: '700', color: '#4A5B53' },
  sugRow: { gap: 6, paddingVertical: 8 },
  sugChip: { backgroundColor: '#EEF6F1', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6, borderWidth: 1, borderColor: '#A7D1BA' },
  sugText: { fontSize: 12, color: C.primary, fontWeight: '600' },
  priceRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  madLabel: { fontSize: 13, fontWeight: '700', color: '#4A5B53' },
  unitRow: { flexDirection: 'row', gap: 4 },
  unitChip: { backgroundColor: '#E9F0E6', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8 },
  unitChipActive: { backgroundColor: C.primary },
  unitChipText: { fontSize: 12, fontWeight: '700', color: '#3C4F47' },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: C.primary, borderRadius: 14, paddingVertical: 15, marginTop: 20 },
  submitText: { color: '#fff', fontWeight: '800', fontSize: 16 },
});

export default SoukPricesScreen;
