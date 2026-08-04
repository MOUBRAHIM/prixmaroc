import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { DashboardAPI } from '@services/api';
import { useAuthStore } from '@store/authStore';
import { C, Colors } from '@constants/colors';
import type { MainTabParamList, DashboardResponse, DashboardAlerte } from '@types/models';

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 5)  return 'Bonne nuit';
  if (h < 12) return 'Bonjour';
  if (h < 18) return 'Bon après-midi';
  return 'Bonsoir';
}

// ── Header ────────────────────────────────────────────────────────────────────

const DashboardHeader: React.FC = () => {
  const { user } = useAuthStore();
  const firstName = user?.full_name?.split(' ')[0] ?? user?.username ?? '';
  return (
    <View style={styles.header}>
      {/* Top row */}
      <View style={styles.headerTopRow}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerGreeting}>{getGreeting()} {firstName ? `${firstName} 👋` : '👋'}</Text>
          <Text style={styles.headerTitle}>PrixMaroc</Text>
          <Text style={styles.headerSub}>Comparez et économisez sur vos courses</Text>
        </View>
        <View style={styles.headerRight}>
          <View style={styles.notifBtn}>
            <Ionicons name="notifications-outline" size={22} color="rgba(255,255,255,0.9)" />
          </View>
        </View>
      </View>
      {/* Decorative wave */}
      <View style={styles.headerWave} />
    </View>
  );
};

// ── Economy card ──────────────────────────────────────────────────────────────

const EconomieCard: React.FC<{ economies: DashboardResponse['economies'] }> = ({ economies }) => (
  <View style={styles.economieCard}>
    {/* green left accent border */}
    <View style={styles.economieAccent} />
    <View style={styles.economieInner}>
      <View style={styles.economieTitleRow}>
        <Text style={styles.economieTitleIcon}>💰</Text>
        <Text style={styles.economieTitle}>Vos Économies</Text>
      </View>
      <View style={styles.economieRow}>
        <View style={styles.economieItem}>
          <Text style={styles.economieAmount}>
            {economies.ce_mois.toFixed(2)}
          </Text>
          <Text style={styles.economieUnit}>MAD</Text>
          <Text style={styles.economieLabel}>Ce mois</Text>
        </View>
        <View style={styles.economieDivider} />
        <View style={styles.economieItem}>
          <Text style={styles.economieAmount}>
            {economies.cumul_annee.toFixed(2)}
          </Text>
          <Text style={styles.economieUnit}>MAD</Text>
          <Text style={styles.economieLabel}>Cette année</Text>
        </View>
      </View>
    </View>
  </View>
);

// ── Stats row ─────────────────────────────────────────────────────────────────

const StatsRow: React.FC<{ stats: DashboardResponse['statistiques'] }> = ({ stats }) => (
  <View style={styles.statsRow}>
    <View style={[styles.statCard, styles.statCardGreen]}>
      <Text style={styles.statEmoji}>🎫</Text>
      <Text style={[styles.statValue, styles.statValueGreen]}>
        {stats.tickets_scannes}
      </Text>
      <Text style={[styles.statLabel, styles.statLabelGreen]}>Tickets</Text>
    </View>
    <View style={[styles.statCard, styles.statCardBlue]}>
      <Text style={styles.statEmoji}>📦</Text>
      <Text style={[styles.statValue, styles.statValueBlue]}>
        {stats.produits_suivis}
      </Text>
      <Text style={[styles.statLabel, styles.statLabelBlue]}>Produits</Text>
    </View>
    <View style={[styles.statCard, styles.statCardOrange]}>
      <Text style={styles.statEmoji}>⭐</Text>
      <Text style={[styles.statValue, styles.statValueOrange]}>
        {stats.score_econome}
      </Text>
      <Text style={[styles.statLabel, styles.statLabelOrange]}>Score</Text>
    </View>
  </View>
);

// ── Quick actions ─────────────────────────────────────────────────────────────

const QuickActions: React.FC = () => {
  const nav = useNavigation<BottomTabNavigationProp<MainTabParamList>>();

  const actions: { emoji: string; label: string; tab: keyof MainTabParamList }[] = [
    { emoji: '🔍', label: 'Comparer',  tab: 'Comparer' },
    { emoji: '📷', label: 'Scanner',   tab: 'Scanner' },
    { emoji: '🛒', label: 'Ma liste',  tab: 'Listes' },
    { emoji: '🏪', label: 'Magasins',  tab: 'Accueil' },
  ];

  return (
    <View style={styles.actionsGrid}>
      {actions.map((a) => (
        <TouchableOpacity
          key={a.label}
          style={styles.actionBtn}
          activeOpacity={0.78}
          onPress={() => nav.navigate(a.tab)}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{a.emoji}</Text>
          </View>
          <Text style={styles.actionLabel}>{a.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
};

// ── Alerts list ───────────────────────────────────────────────────────────────

const ALERT_COLORS = ['#16a34a', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6'];

const AlertesList: React.FC<{ alertes: DashboardAlerte[] }> = ({ alertes }) => {
  if (alertes.length === 0) {
    return (
      <View style={styles.alertesEmpty}>
        <Text style={styles.alertesEmptyEmoji}>✅</Text>
        <Text style={styles.alertesEmptyText}>
          Aucune alerte pour le moment.
        </Text>
        <Text style={styles.alertesEmptyHint}>
          Ajoutez des produits pour recevoir des alertes de prix.
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.alertesList}>
      {alertes.map((alerte, i) => {
        const accentColor = ALERT_COLORS[i % ALERT_COLORS.length];
        return (
          <View
            key={i}
            style={[styles.alerteItem, { borderLeftColor: accentColor }]}
          >
            <View style={styles.alerteContent}>
              <Text style={styles.alerteProduit}>{alerte.product_name}</Text>
              <Text style={styles.alerteMessage}>
                Cible : {alerte.target_price.toFixed(2)} MAD
                {alerte.current_price != null ? ` · Actuel : ${alerte.current_price.toFixed(2)} MAD` : ''}
              </Text>
              {alerte.is_triggered ? (
                <Text style={[styles.alertePrix, { color: '#16a34a' }]}>
                  🎉 Prix atteint !
                </Text>
              ) : null}
            </View>
            <Text style={styles.alerteChevron}>›</Text>
          </View>
        );
      })}
    </View>
  );
};

// ── Section header ────────────────────────────────────────────────────────────

const SectionHeader: React.FC<{ title: string; onVoirTout?: () => void }> = ({
  title,
  onVoirTout,
}) => (
  <View style={styles.sectionHeader}>
    <Text style={styles.sectionTitle}>{title}</Text>
    {onVoirTout ? (
      <TouchableOpacity onPress={onVoirTout} activeOpacity={0.7}>
        <Text style={styles.voirTout}>Voir tout</Text>
      </TouchableOpacity>
    ) : null}
  </View>
);

// ── Main Screen ───────────────────────────────────────────────────────────────

const DashboardScreen: React.FC<{ navigation: any }> = ({ navigation }) => {
  const { data, isLoading, isError, error, refetch, isRefetching } =
    useQuery<DashboardResponse>({
      queryKey: ['dashboard'],
      queryFn: DashboardAPI.get,
    });

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor="#15803d" />
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <DashboardHeader />
      </SafeAreaView>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor={C.primary}
            colors={[C.primary]}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Loading */}
        {isLoading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Chargement de votre tableau de bord…</Text>
          </View>
        )}

        {/* Error */}
        {isError && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorEmoji}>😕</Text>
            <Text style={styles.errorTitle}>Impossible de charger</Text>
            <Text style={styles.errorMessage}>
              {(error as Error)?.message ?? 'Une erreur est survenue.'}
            </Text>
            <TouchableOpacity
              style={styles.retryButton}
              onPress={() => refetch()}
              activeOpacity={0.8}
            >
              <Text style={styles.retryButtonText}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Content */}
        {data && (
          <>
            {/* Economy card */}
            <EconomieCard economies={data.economies} />

            {/* Stats */}
            <SectionHeader title="Statistiques" />
            <StatsRow stats={data.statistiques} />

            {/* Quick actions */}
            <SectionHeader title="Actions rapides" />
            <QuickActions />

            {/* Shortcuts to main sections */}
            <SectionHeader title="Accès rapides" />
            <View style={styles.shortcutsRow}>
              <TouchableOpacity
                style={styles.shortcutCard}
                activeOpacity={0.82}
                onPress={() => navigation.navigate('Promotions')}
              >
                <Text style={styles.shortcutEmoji}>🔥</Text>
                <Text style={styles.shortcutLabel}>Promotions</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.shortcutCard}
                activeOpacity={0.82}
                onPress={() => navigation.navigate('MagasinsProches')}
              >
                <Text style={styles.shortcutEmoji}>📍</Text>
                <Text style={styles.shortcutLabel}>Magasins</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.shortcutCard}
                activeOpacity={0.82}
                onPress={() => navigation.navigate('SoukPrices')}
              >
                <Text style={styles.shortcutEmoji}>🧺</Text>
                <Text style={styles.shortcutLabel}>Prix du souk</Text>
              </TouchableOpacity>
            </View>

            {/* Alerts */}
            <SectionHeader
              title="Alertes récentes"
              onVoirTout={() => navigation.navigate('MesAlertes' as never)}
            />
            <AlertesList alertes={data.alertes_actives} />
          </>
        )}
      </ScrollView>
    </View>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f1f5f9' },
  safeArea: { backgroundColor: '#15803d' },
  scroll: { flex: 1, marginTop: -1 },
  scrollContent: { paddingBottom: 40 },

  // Header
  header: {
    backgroundColor: '#15803d',
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 0,
  },
  headerTopRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingBottom: 20,
  },
  headerLeft: { flex: 1 },
  headerRight: {},
  headerGreeting: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.75)',
    fontWeight: '500',
    marginBottom: 4,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '900',
    color: '#ffffff',
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  headerSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.65)',
    fontWeight: '400',
  },
  headerWave: {
    height: 20,
    backgroundColor: '#f1f5f9',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    marginTop: -2,
  },
  notifBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.25)',
  },
  notifIcon: { fontSize: 20 },

  // Loading / Error
  loadingContainer: { alignItems: 'center', paddingVertical: 64 },
  loadingText: { marginTop: 14, color: '#64748b', fontSize: 15 },
  errorContainer: {
    margin: 20,
    padding: 28,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  },
  errorEmoji: { fontSize: 40, marginBottom: 12 },
  errorTitle: { fontSize: 17, fontWeight: '700', color: '#0f172a', marginBottom: 8 },
  errorMessage: { fontSize: 14, color: '#64748b', textAlign: 'center', marginBottom: 20, lineHeight: 20 },
  retryButton: {
    backgroundColor: C.primary,
    paddingHorizontal: 28,
    paddingVertical: 12,
    borderRadius: 10,
  },
  retryButtonText: { color: '#ffffff', fontWeight: '700', fontSize: 15 },

  // Economy card
  economieCard: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 4,
    backgroundColor: '#15803d',
    borderRadius: 20,
    shadowColor: '#15803d',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.30,
    shadowRadius: 14,
    elevation: 8,
    overflow: 'hidden',
  },
  economieAccent: {
    width: 5,
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  economieInner: {
    flex: 1,
    padding: 20,
  },
  economieTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 18,
  },
  economieTitleIcon: { fontSize: 20 },
  economieTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.75)',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  economieRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  economieItem: { flex: 1, alignItems: 'center' },
  economieDivider: { width: 1, height: 48, backgroundColor: 'rgba(255,255,255,0.25)' },
  economieAmount: {
    fontSize: 32,
    fontWeight: '900',
    color: '#ffffff',
    letterSpacing: -0.5,
  },
  economieUnit: {
    fontSize: 12,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.7)',
    marginTop: -2,
  },
  economieLabel: { fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 4 },

  // Section header
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: -0.2,
  },
  voirTout: {
    fontSize: 13,
    fontWeight: '700',
    color: '#16a34a',
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: '#f0fdf4',
    borderRadius: 12,
  },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 4,
  },
  statCard: {
    flex: 1,
    borderRadius: 14,
    padding: 14,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  statEmoji: { fontSize: 22, marginBottom: 6 },
  statValue: { fontSize: 22, fontWeight: '800', letterSpacing: -0.5 },
  statLabel: { fontSize: 11, marginTop: 3, fontWeight: '600', textAlign: 'center' },

  statCardGreen: { backgroundColor: '#f0fdf4', borderWidth: 1, borderColor: '#bbf7d0' },
  statValueGreen: { color: '#15803d' },
  statLabelGreen: { color: '#16a34a' },

  statCardBlue: { backgroundColor: '#eff6ff', borderWidth: 1, borderColor: '#bfdbfe' },
  statValueBlue: { color: '#1d4ed8' },
  statLabelBlue: { color: '#2563eb' },

  statCardOrange: { backgroundColor: '#fff7ed', borderWidth: 1, borderColor: '#fed7aa' },
  statValueOrange: { color: '#c2410c' },
  statLabelOrange: { color: '#ea580c' },

  // Quick actions
  actionsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 4,
  },
  actionBtn: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 4,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  actionIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: '#f0fdf4',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#dcfce7',
  },
  actionEmoji: { fontSize: 24 },
  actionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#374151',
    textAlign: 'center',
  },

  // Shortcuts
  shortcutsRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    gap: 12,
    marginBottom: 4,
  },
  shortcutCard: {
    flex: 1,
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 20,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 4,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  shortcutEmoji: { fontSize: 32, marginBottom: 10 },
  shortcutLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
  },

  // Alerts
  alertesList: { marginHorizontal: 16 },
  alertesEmpty: {
    marginHorizontal: 16,
    padding: 24,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  alertesEmptyEmoji: { fontSize: 32, marginBottom: 10 },
  alertesEmptyText: { color: '#374151', fontSize: 15, fontWeight: '600', marginBottom: 4 },
  alertesEmptyHint: { color: '#94a3b8', fontSize: 13, textAlign: 'center' },
  alerteItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 4,
  },
  alerteContent: { flex: 1 },
  alerteProduit: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0f172a',
    marginBottom: 3,
  },
  alerteMessage: { fontSize: 13, color: '#64748b', lineHeight: 18 },
  alertePrix: {
    fontSize: 14,
    fontWeight: '700',
    marginTop: 6,
  },
  alerteChevron: {
    fontSize: 22,
    color: '#cbd5e1',
    marginLeft: 8,
    fontWeight: '300',
  },
});

export default DashboardScreen;
