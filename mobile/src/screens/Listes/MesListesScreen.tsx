import React, { useState } from 'react';
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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { ListsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ListesStackParamList, ShoppingList } from '@types/models';

type Props = NativeStackScreenProps<ListesStackParamList, 'MesListes'>;

// ── Types de listes ───────────────────────────────────────────────────────────

type ListType = 'toutes' | 'hebdo' | 'bimensuelle' | 'mensuelle';

const LIST_TABS: { key: ListType; label: string; icon: string }[] = [
  { key: 'toutes',      label: 'Toutes',       icon: '📋' },
  { key: 'hebdo',       label: 'Hebdo',        icon: '📅' },
  { key: 'bimensuelle', label: 'Bi-mensuelle', icon: '🗓️' },
  { key: 'mensuelle',   label: 'Mensuelle',    icon: '📆' },
];

const LIST_TYPE_PRESETS: Record<Exclude<ListType, 'toutes'>, { name: string; description: string }> = {
  hebdo:       { name: 'Courses hebdomadaires',    description: 'Liste pour la semaine' },
  bimensuelle: { name: 'Courses bi-mensuelles',    description: 'Liste pour 2 semaines' },
  mensuelle:   { name: 'Courses du mois',          description: 'Liste mensuelle complète' },
};

function listMatchesType(list: ShoppingList, type: ListType): boolean {
  if (type === 'toutes') return true;
  const name = list.name.toLowerCase();
  const desc = (list.description ?? '').toLowerCase();
  if (type === 'hebdo')
    return name.includes('hebdo') || name.includes('semaine') || desc.includes('hebdo') || desc.includes('semaine');
  if (type === 'bimensuelle')
    return name.includes('bi-') || name.includes('bimensuel') || name.includes('2 semaine') || desc.includes('bi');
  if (type === 'mensuelle')
    return name.includes('mensuel') || name.includes('mois') || desc.includes('mensuel');
  return true;
}

// ── Carte liste ───────────────────────────────────────────────────────────────

const ListCard: React.FC<{
  list: ShoppingList;
  onPress: () => void;
  onDelete: () => void;
}> = ({ list, onPress, onDelete }) => {
  const checkedCount = list.items.filter((i) => i.is_checked).length;
  const totalCount = list.items.length;
  const progress = totalCount > 0 ? checkedCount / totalCount : 0;
  const updatedAt = new Date(list.updated_at).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short' });

  // Estimation budget
  const estimatedTotal = list.items
    .filter((i) => i.product?.lowest_price != null)
    .reduce((s, i) => s + (i.product!.lowest_price! * i.quantity), 0);

  return (
    <TouchableOpacity style={styles.listCard} onPress={onPress} activeOpacity={0.75}>
      <View style={styles.listCardLeft}>
        <View style={styles.listIconWrap}>
          <Ionicons name="list" size={24} color={C.primary} />
        </View>
      </View>
      <View style={styles.listCardContent}>
        <Text style={styles.listName} numberOfLines={1}>{list.name}</Text>
        {list.description ? (
          <Text style={styles.listDesc} numberOfLines={1}>{list.description}</Text>
        ) : null}
        <View style={styles.listMeta}>
          <Text style={styles.listItemCount}>
            {checkedCount}/{totalCount} article{totalCount !== 1 ? 's' : ''}
          </Text>
          <Text style={styles.listDate}>· {updatedAt}</Text>
          {estimatedTotal > 0 && (
            <Text style={styles.listBudget}>· ~{estimatedTotal.toFixed(0)} MAD</Text>
          )}
        </View>
        {totalCount > 0 && (
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: `${progress * 100}%` as any }]} />
          </View>
        )}
      </View>
      <TouchableOpacity
        style={styles.deleteBtn}
        onPress={onDelete}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Ionicons name="trash-outline" size={18} color="#ef4444" />
      </TouchableOpacity>
    </TouchableOpacity>
  );
};

// ── Modal nouvelle liste ──────────────────────────────────────────────────────

const NewListModal: React.FC<{
  visible: boolean;
  onClose: () => void;
  onSubmit: (name: string, desc: string) => void;
  isLoading: boolean;
  presetType?: Exclude<ListType, 'toutes'> | null;
}> = ({ visible, onClose, onSubmit, isLoading, presetType }) => {
  const preset = presetType ? LIST_TYPE_PRESETS[presetType] : null;
  const [name, setName] = useState(preset?.name ?? '');
  const [desc, setDesc] = useState(preset?.description ?? '');

  React.useEffect(() => {
    if (preset) { setName(preset.name); setDesc(preset.description); }
    else { setName(''); setDesc(''); }
  }, [presetType, visible]);

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) { Alert.alert('Nom requis', 'Saisissez un nom pour la liste.'); return; }
    onSubmit(trimmed, desc.trim());
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={modal.overlay}>
        <View style={modal.sheet}>
          <Text style={modal.title}>Nouvelle liste</Text>
          <Text style={modal.label}>Nom *</Text>
          <TextInput
            style={modal.input}
            placeholder="Ex : Courses semaine"
            placeholderTextColor="#8A9A92"
            value={name}
            onChangeText={setName}
            autoFocus
          />
          <Text style={modal.label}>Description (optionnel)</Text>
          <TextInput
            style={[modal.input, { height: 72, textAlignVertical: 'top' }]}
            placeholder="Courses pour la semaine du…"
            placeholderTextColor="#8A9A92"
            value={desc}
            onChangeText={setDesc}
            multiline
          />
          <View style={modal.actions}>
            <TouchableOpacity style={modal.cancelBtn} onPress={onClose}>
              <Text style={modal.cancelText}>Annuler</Text>
            </TouchableOpacity>
            <TouchableOpacity style={modal.submitBtn} onPress={handleSubmit} disabled={isLoading}>
              {isLoading ? <ActivityIndicator size="small" color="#ffffff" /> : <Text style={modal.submitText}>Créer</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const modal = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.4)' },
  sheet: { backgroundColor: '#ffffff', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, paddingBottom: 40 },
  title: { fontSize: 20, fontWeight: '800', color: '#0B2019', marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '600', color: '#4A5B53', marginBottom: 6 },
  input: { backgroundColor: '#E9F0E6', borderRadius: 10, padding: 12, fontSize: 15, color: '#0B2019', marginBottom: 14 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 8 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#E9F0E6', alignItems: 'center' },
  cancelText: { color: '#4A5B53', fontWeight: '700', fontSize: 15 },
  submitBtn: { flex: 2, paddingVertical: 12, borderRadius: 10, backgroundColor: C.primary, alignItems: 'center' },
  submitText: { color: '#ffffff', fontWeight: '700', fontSize: 15 },
});

// ── Écran principal ───────────────────────────────────────────────────────────

const MesListesScreen: React.FC<Props> = ({ navigation }) => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<ListType>('toutes');
  const [showModal, setShowModal] = useState(false);
  const [presetType, setPresetType] = useState<Exclude<ListType, 'toutes'> | null>(null);

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['shopping-lists'],
    queryFn: ListsAPI.getAll,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      ListsAPI.create({ name, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shopping-lists'] });
      setShowModal(false);
      setPresetType(null);
    },
    onError: () => Alert.alert('Erreur', "Impossible de créer la liste."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => ListsAPI.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shopping-lists'] }),
    onError: () => Alert.alert('Erreur', "Impossible de supprimer la liste."),
  });

  const handleDelete = (id: number, name: string) => {
    Alert.alert('Supprimer la liste', `Voulez-vous supprimer « ${name} » ?`, [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Supprimer', style: 'destructive', onPress: () => deleteMutation.mutate(id) },
    ]);
  };

  const openNewList = (type?: Exclude<ListType, 'toutes'>) => {
    setPresetType(type ?? null);
    setShowModal(true);
  };

  // Filtrer les listes selon l'onglet actif
  const filteredData = (data ?? []).filter((l) => listMatchesType(l, activeTab));

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Mes listes</Text>
          {data && <Text style={styles.headerSub}>{data.length} liste{data.length !== 1 ? 's' : ''}</Text>}
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity style={styles.iaBtn} onPress={() => navigation.navigate('NouvelleListeIA')}>
            <Ionicons name="sparkles" size={16} color={C.primary} />
            <Text style={styles.iaBtnText}>IA</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.newBtn} onPress={() => openNewList()}>
            <Ionicons name="add" size={20} color="#ffffff" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Onglets Hebdo / Bi-mensuelle / Mensuelle */}
      <View style={styles.tabBar}>
        {LIST_TABS.map((tab) => {
          const count = (data ?? []).filter((l) => listMatchesType(l, tab.key)).length;
          return (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, activeTab === tab.key && styles.tabActive]}
              onPress={() => setActiveTab(tab.key)}
            >
              <Text style={styles.tabIcon}>{tab.icon}</Text>
              <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>
                {tab.label}
              </Text>
              {tab.key !== 'toutes' && count === 0 && (
                <TouchableOpacity
                  style={styles.tabAddBtn}
                  onPress={() => openNewList(tab.key as Exclude<ListType, 'toutes'>)}
                  hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                >
                  <Ionicons name="add" size={12} color={C.primary} />
                </TouchableOpacity>
              )}
              {count > 0 && (
                <View style={[styles.tabBadge, activeTab === tab.key && styles.tabBadgeActive]}>
                  <Text style={[styles.tabBadgeText, activeTab === tab.key && { color: '#fff' }]}>{count}</Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Raccourcis création rapide (si onglet vide) */}
      {activeTab !== 'toutes' && !isLoading && filteredData.length === 0 && (
        <TouchableOpacity
          style={styles.quickCreate}
          onPress={() => openNewList(activeTab as Exclude<ListType, 'toutes'>)}
        >
          <Ionicons name="add-circle-outline" size={20} color={C.primary} />
          <Text style={styles.quickCreateText}>
            Créer ma liste {LIST_TABS.find((t) => t.key === activeTab)?.label.toLowerCase()}
          </Text>
        </TouchableOpacity>
      )}

      {/* États */}
      {isLoading && (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Chargement…</Text>
        </View>
      )}
      {isError && (
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
          <Text style={styles.errorText}>Impossible de charger les listes</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Liste filtrée */}
      {data && (
        <FlatList
          data={filteredData}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <ListCard
              list={item}
              onPress={() => navigation.navigate('DetailListe', { listId: item.id, listName: item.name })}
              onDelete={() => handleDelete(item.id, item.name)}
            />
          )}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />}
          ListEmptyComponent={
            activeTab === 'toutes' ? (
              <View style={styles.emptyState}>
                <Ionicons name="list-outline" size={72} color="#d1d5db" />
                <Text style={styles.emptyTitle}>Aucune liste</Text>
                <Text style={styles.emptySubtitle}>
                  Créez votre première liste ou laissez l'IA en générer une.
                </Text>
                {/* Raccourcis rapides par type */}
                <View style={styles.quickButtons}>
                  {(Object.keys(LIST_TYPE_PRESETS) as Exclude<ListType, 'toutes'>[]).map((t) => (
                    <TouchableOpacity key={t} style={styles.quickBtn} onPress={() => openNewList(t)}>
                      <Text style={styles.quickBtnText}>{LIST_TABS.find((x) => x.key === t)?.icon} {LIST_TABS.find((x) => x.key === t)?.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            ) : null
          }
        />
      )}

      <NewListModal
        visible={showModal}
        onClose={() => { setShowModal(false); setPresetType(null); }}
        onSubmit={(name, desc) => createMutation.mutate({ name, description: desc || undefined })}
        isLoading={createMutation.isPending}
        presetType={presetType}
      />
    </SafeAreaView>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#E9F0E6' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#0C3F30', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 18,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#ffffff' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  headerActions: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  iaBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.5)',
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  iaBtnText: { color: '#ffffff', fontWeight: '700', fontSize: 13 },
  newBtn: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.5)',
    borderRadius: 10, width: 36, height: 36, alignItems: 'center', justifyContent: 'center',
  },

  // Onglets
  tabBar: {
    flexDirection: 'row', backgroundColor: '#fff',
    borderBottomWidth: 1, borderBottomColor: '#E2E9DF',
    paddingHorizontal: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 4, paddingVertical: 12, borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: '#0C3F30' },
  tabIcon: { fontSize: 13 },
  tabLabel: { fontSize: 12, fontWeight: '600', color: '#8A9A92' },
  tabLabelActive: { color: '#0C3F30' },
  tabBadge: {
    width: 16, height: 16, borderRadius: 8,
    backgroundColor: '#E9F0E6', alignItems: 'center', justifyContent: 'center',
  },
  tabBadgeActive: { backgroundColor: '#0C3F30' },
  tabBadgeText: { fontSize: 10, fontWeight: '700', color: '#4A5B53' },
  tabAddBtn: {
    width: 16, height: 16, borderRadius: 8,
    backgroundColor: '#EEF6F1', borderWidth: 1, borderColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },

  quickCreate: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    margin: 16, padding: 14, backgroundColor: '#EEF6F1',
    borderRadius: 14, borderWidth: 1.5, borderColor: '#A7D1BA', borderStyle: 'dashed',
  },
  quickCreateText: { color: C.primary, fontWeight: '600', fontSize: 14 },

  listContent: { padding: 14 },
  listCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#ffffff', borderRadius: 16, padding: 14, marginBottom: 10,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.07, shadowRadius: 8, elevation: 3,
  },
  listCardLeft: { marginRight: 14 },
  listIconWrap: {
    width: 50, height: 50, borderRadius: 14, backgroundColor: '#EEF6F1',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#D3E8DC',
  },
  listCardContent: { flex: 1 },
  listName: { fontSize: 16, fontWeight: '700', color: '#0B2019', marginBottom: 3 },
  listDesc: { fontSize: 13, color: '#4A5B53', marginBottom: 4 },
  listMeta: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 7 },
  listItemCount: { fontSize: 12, color: '#8A9A92' },
  listDate: { fontSize: 12, color: '#8A9A92' },
  listBudget: { fontSize: 12, color: '#0C3F30', fontWeight: '700' },
  progressBar: { height: 5, backgroundColor: '#E2E9DF', borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 5, backgroundColor: '#0F4C3A', borderRadius: 3 },
  deleteBtn: { padding: 8 },

  centered: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#4A5B53', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: { backgroundColor: C.primary, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 12 },
  retryBtnText: { color: '#ffffff', fontWeight: '700', fontSize: 14 },

  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 40, gap: 12 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#374151' },
  emptySubtitle: { fontSize: 14, color: '#8A9A92', textAlign: 'center', lineHeight: 20 },
  quickButtons: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 8 },
  quickBtn: {
    paddingHorizontal: 14, paddingVertical: 9, backgroundColor: '#EEF6F1',
    borderRadius: 20, borderWidth: 1.5, borderColor: '#A7D1BA',
  },
  quickBtnText: { color: C.primary, fontWeight: '600', fontSize: 13 },
});

export default MesListesScreen;
