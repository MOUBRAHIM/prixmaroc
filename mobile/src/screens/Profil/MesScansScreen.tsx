import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { OcrAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ProfilStackParamList, OcrScan } from '@types/models';

type Props = NativeStackScreenProps<ProfilStackParamList, 'MesScans'>;

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ComponentProps<typeof Ionicons>['name'] }> = {
  done:       { label: 'Traité',          color: C.primary,  icon: 'checkmark-circle' },
  pending:    { label: 'En attente',       color: '#E8A020',  icon: 'hourglass' },
  processing: { label: 'En cours',         color: '#3b82f6',  icon: 'sync' },
  failed:     { label: 'Échec',            color: '#ef4444',  icon: 'close-circle' },
};

// ── Carte scan ────────────────────────────────────────────────────────────────

const ScanCard: React.FC<{ scan: OcrScan }> = ({ scan }) => {
  const config = STATUS_CONFIG[scan.status] ?? STATUS_CONFIG.pending;
  const date = new Date(scan.created_at).toLocaleDateString('fr-MA', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
  const time = new Date(scan.created_at).toLocaleTimeString('fr-MA', {
    hour: '2-digit', minute: '2-digit',
  });
  const storeName = scan.parsed_data?.store?.name ?? scan.parsed_data?.store?.chain;
  const total = scan.parsed_data?.total;
  const itemCount = scan.parsed_data?.items?.length ?? 0;

  return (
    <View style={styles.scanCard}>
      <View style={styles.scanLeft}>
        <View style={[styles.scanIcon, { backgroundColor: `${config.color}15` }]}>
          <Ionicons name={config.icon} size={22} color={config.color} />
        </View>
      </View>
      <View style={styles.scanContent}>
        <View style={styles.scanHeader}>
          <Text style={styles.scanDate}>{date} à {time}</Text>
          <View style={[styles.statusBadge, { backgroundColor: `${config.color}18` }]}>
            <Text style={[styles.statusText, { color: config.color }]}>{config.label}</Text>
          </View>
        </View>

        {storeName && (
          <Text style={styles.scanStore}>
            <Ionicons name="storefront-outline" size={12} color="#8A9A92" /> {storeName}
          </Text>
        )}

        <View style={styles.scanStats}>
          {total != null && (
            <View style={styles.scanStat}>
              <Ionicons name="receipt-outline" size={13} color={C.primary} />
              <Text style={styles.scanStatValue}>{total.toFixed(2)} MAD</Text>
            </View>
          )}
          {itemCount > 0 && (
            <View style={styles.scanStat}>
              <Ionicons name="list-outline" size={13} color="#4A5B53" />
              <Text style={styles.scanStatText}>{itemCount} article{itemCount > 1 ? 's' : ''}</Text>
            </View>
          )}
        </View>

        {scan.status === 'failed' && scan.error_message && (
          <Text style={styles.errorMsg} numberOfLines={1}>{scan.error_message}</Text>
        )}
      </View>
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const MesScansScreen: React.FC<Props> = () => {
  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['ocr-scans'],
    queryFn: OcrAPI.getScans,
  });

  const sorted = [...(data ?? [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      {isLoading && (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Chargement…</Text>
        </View>
      )}

      {isError && (
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={44} color="#ef4444" />
          <Text style={styles.errorText}>Impossible de charger les scans</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {data && (
        <FlatList
          data={sorted}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => <ScanCard scan={item} />}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />
          }
          ListHeaderComponent={
            sorted.length > 0 ? (
              <Text style={styles.listHeader}>
                {sorted.length} ticket{sorted.length > 1 ? 's' : ''} scanné{sorted.length > 1 ? 's' : ''}
              </Text>
            ) : null
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Ionicons name="scan-outline" size={72} color="#d1d5db" />
              <Text style={styles.emptyTitle}>Aucun scan</Text>
              <Text style={styles.emptySubtitle}>
                Scannez vos tickets de caisse depuis l'onglet Scanner pour les retrouver ici.
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F2F6F0' },
  centered: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#4A5B53', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: { backgroundColor: C.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 10 },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  listContent: { padding: 16, paddingBottom: 32 },
  listHeader: {
    fontSize: 13, color: '#8A9A92', fontStyle: 'italic', marginBottom: 10,
  },
  scanCard: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
  },
  scanLeft: { marginRight: 12 },
  scanIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  scanContent: { flex: 1 },
  scanHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  scanDate: { fontSize: 13, fontWeight: '600', color: '#0B2019' },
  statusBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  statusText: { fontSize: 11, fontWeight: '700' },
  scanStore: { fontSize: 12, color: '#8A9A92', marginBottom: 6 },
  scanStats: { flexDirection: 'row', gap: 12 },
  scanStat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  scanStatValue: { fontSize: 14, fontWeight: '800', color: C.primary },
  scanStatText: { fontSize: 13, color: '#4A5B53' },
  errorMsg: { fontSize: 12, color: '#ef4444', marginTop: 4, fontStyle: 'italic' },
  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 40, gap: 12 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#374151' },
  emptySubtitle: { fontSize: 14, color: '#8A9A92', textAlign: 'center', lineHeight: 20 },
});

export default MesScansScreen;
