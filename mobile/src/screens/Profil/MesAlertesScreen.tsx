import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { AlertsAPI } from '@services/api';
import { C } from '@constants/colors';
import type { ProfilStackParamList, PriceAlert } from '@types/models';

type Props = NativeStackScreenProps<ProfilStackParamList, 'MesAlertes'>;

// ── Carte alerte ──────────────────────────────────────────────────────────────

const AlertCard: React.FC<{
  alert: PriceAlert;
  onDelete: () => void;
}> = ({ alert, onDelete }) => {
  const productName = alert.product?.name ?? `Produit #${alert.product_id}`;
  const isTriggered = alert.is_triggered ?? (alert.triggered_at != null);
  const triggeredDate = alert.triggered_at
    ? new Date(alert.triggered_at).toLocaleDateString('fr-MA', { day: '2-digit', month: 'short', year: 'numeric' })
    : null;

  return (
    <View style={[styles.alertCard, isTriggered && styles.alertCardTriggered]}>
      <View style={styles.alertLeft}>
        <View style={[styles.alertIcon, isTriggered && styles.alertIconTriggered]}>
          <Ionicons
            name={isTriggered ? 'notifications' : 'notifications-outline'}
            size={20}
            color={isTriggered ? '#fff' : C.primary}
          />
        </View>
      </View>
      <View style={styles.alertContent}>
        <Text style={styles.alertProductName} numberOfLines={2}>{productName}</Text>

        {alert.store && (
          <View style={styles.alertStoreRow}>
            <Ionicons name="storefront-outline" size={12} color="#94a3b8" />
            <Text style={styles.alertStore}>{alert.store.name}</Text>
          </View>
        )}

        <View style={styles.alertPriceRow}>
          <View style={styles.alertPriceBadge}>
            <Text style={styles.alertPriceBadgeLabel}>Cible</Text>
            <Text style={styles.alertPriceBadgeValue}>{alert.target_price.toFixed(2)} MAD</Text>
          </View>
          {isTriggered && (
            <View style={[styles.alertPriceBadge, styles.alertTriggeredBadge]}>
              <Ionicons name="checkmark-circle" size={12} color={C.primary} />
              <Text style={[styles.alertPriceBadgeLabel, { color: C.primary }]}>
                Déclenchée{triggeredDate ? ` le ${triggeredDate}` : ''}
              </Text>
            </View>
          )}
        </View>

        {!isTriggered && (
          <Text style={styles.alertStatus}>En attente d'une baisse de prix…</Text>
        )}
      </View>

      <TouchableOpacity
        style={styles.deleteBtn}
        onPress={onDelete}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Ionicons name="trash-outline" size={18} color="#ef4444" />
      </TouchableOpacity>
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const MesAlertesScreen: React.FC<Props> = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['price-alerts'],
    queryFn: AlertsAPI.getAll,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => AlertsAPI.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['price-alerts'] }),
    onError: () => Alert.alert('Erreur', "Impossible de supprimer l'alerte."),
  });

  const handleDelete = (id: number, productName: string) => {
    Alert.alert(
      'Supprimer l\'alerte',
      `Supprimer l'alerte pour « ${productName} » ?`,
      [
        { text: 'Annuler', style: 'cancel' },
        { text: 'Supprimer', style: 'destructive', onPress: () => deleteMutation.mutate(id) },
      ],
    );
  };

  const active = (data ?? []).filter((a) => !a.is_triggered && a.triggered_at == null);
  const triggered = (data ?? []).filter((a) => a.is_triggered || a.triggered_at != null);

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
          <Text style={styles.errorText}>Impossible de charger les alertes</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {data && (
        <FlatList
          data={[
            ...(active.length > 0 ? [{ type: 'header', label: `Actives (${active.length})`, id: 'h1' }] : []),
            ...active.map((a) => ({ type: 'alert', data: a, id: `a${a.id}` })),
            ...(triggered.length > 0 ? [{ type: 'header', label: `Déclenchées (${triggered.length})`, id: 'h2' }] : []),
            ...triggered.map((a) => ({ type: 'alert', data: a, id: `t${a.id}` })),
          ]}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => {
            if (item.type === 'header') {
              const headerItem = item as { type: string; label: string; id: string };
              return <Text style={styles.sectionHeader}>{headerItem.label}</Text>;
            }
            const alert = (item as { type: string; data: PriceAlert; id: string }).data;
            return (
              <AlertCard
                alert={alert}
                onDelete={() => handleDelete(alert.id, alert.product?.name ?? `Produit #${alert.product_id}`)}
              />
            );
          }}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={C.primary} />
          }
          ListEmptyComponent={
            <View style={styles.emptyState}>
              <Ionicons name="notifications-off-outline" size={72} color="#d1d5db" />
              <Text style={styles.emptyTitle}>Aucune alerte</Text>
              <Text style={styles.emptySubtitle}>
                Créez des alertes depuis la fiche d'un produit pour être notifié quand son prix baisse.
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f8fafc' },
  centered: { flex: 1, alignItems: 'center', paddingTop: 80, gap: 12 },
  loadingText: { color: '#64748b', fontSize: 15 },
  errorText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  retryBtn: { backgroundColor: C.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 10 },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  listContent: { padding: 16, paddingBottom: 32 },
  sectionHeader: {
    fontSize: 13, fontWeight: '700', color: '#94a3b8',
    textTransform: 'uppercase', letterSpacing: 0.8,
    marginBottom: 8, marginTop: 8,
  },
  alertCard: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
    borderWidth: 1, borderColor: '#e2e8f0',
  },
  alertCardTriggered: { borderColor: '#bbf7d0', backgroundColor: '#f0fdf4' },
  alertLeft: { marginRight: 12 },
  alertIcon: {
    width: 40, height: 40, borderRadius: 12,
    backgroundColor: '#f0fdf4', alignItems: 'center', justifyContent: 'center',
  },
  alertIconTriggered: { backgroundColor: C.primary },
  alertContent: { flex: 1 },
  alertProductName: { fontSize: 15, fontWeight: '700', color: '#0f172a', marginBottom: 4 },
  alertStoreRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  alertStore: { fontSize: 12, color: '#94a3b8' },
  alertPriceRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 4 },
  alertPriceBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#f1f5f9', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4,
  },
  alertTriggeredBadge: { backgroundColor: '#f0fdf4' },
  alertPriceBadgeLabel: { fontSize: 11, color: '#64748b', fontWeight: '600' },
  alertPriceBadgeValue: { fontSize: 13, fontWeight: '800', color: '#0f172a' },
  alertStatus: { fontSize: 12, color: '#94a3b8', fontStyle: 'italic' },
  deleteBtn: { padding: 4, marginLeft: 4 },
  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 40, gap: 12 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#374151' },
  emptySubtitle: { fontSize: 14, color: '#9ca3af', textAlign: 'center', lineHeight: 20 },
});

export default MesAlertesScreen;
