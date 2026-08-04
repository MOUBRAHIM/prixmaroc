/**
 * MagasinsProchesScreen — Phase 6.2 : Géolocalisation & itinéraires
 * Carte interactive des magasins proches + optimisation de parcours
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  Modal,
  ActivityIndicator,
  Linking,
  Dimensions,
  Platform,
  ScrollView,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MapView, { Marker, Circle, PROVIDER_DEFAULT } from '@components/Maps';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { C } from '@constants/colors';
import { MAPS_ENABLED } from '@constants';
import { StoresAPI } from '@services/api';
import type { AccueilStackParamList } from '@types/models';
import type { StoreNearby } from '@types/models';

const FOYER_KEY = 'prixmaroc:foyer';

// ─── Types ────────────────────────────────────────────────────────────────────

interface RouteStop {
  order: number;
  store_id: number;
  store_name: string;
  store_address: string;
  latitude: number;
  longitude: number;
  products_to_buy: string[];
  estimated_savings: number;
}

interface RouteOptimizeResponse {
  stops: RouteStop[];
  total_stores: number;
  total_distance_km: number;
  total_savings: number;
  algorithm: string;
}

type ViewMode = 'carte' | 'liste';

type Props = NativeStackScreenProps<AccueilStackParamList, 'MagasinsProches'>;

// ─── Constants ────────────────────────────────────────────────────────────────

const SCREEN_HEIGHT = Dimensions.get('window').height;
const PANEL_HEIGHT = SCREEN_HEIGHT * 0.60;
const DEFAULT_RADIUS = 10;

const MARKER_GREEN  = C.primary;      // product_count > 20
const MARKER_ORANGE = '#f59e0b';      // product_count 5–20
const MARKER_GRAY   = '#94a3b8';      // product_count < 5

// ─── Helpers ──────────────────────────────────────────────────────────────────

function markerColor(count: number): string {
  if (count > 20) return MARKER_GREEN;
  if (count >= 5)  return MARKER_ORANGE;
  return MARKER_GRAY;
}

function distanceLabel(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1)} km`;
}

// ─── Sub-component: Store row in list ─────────────────────────────────────────

interface StoreRowProps {
  store: StoreNearby;
  selected: boolean;
  onToggle: (id: number) => void;
  onFocus: (store: StoreNearby) => void;
  userLat: number;
  userLng: number;
}

const StoreRow: React.FC<StoreRowProps> = ({ store, selected, onToggle, onFocus, userLat, userLng }) => {
  const color = markerColor(store.product_count);

  const navigateToStore = async () => {
    if (!store.latitude || !store.longitude) {
      Alert.alert('Adresse inconnue', 'Ce magasin n\'a pas de coordonnées GPS.');
      return;
    }
    const dest = `${store.latitude},${store.longitude}`;
    const nativeUrl = Platform.OS === 'ios'
      ? `comgooglemaps://?origin=${userLat},${userLng}&daddr=${dest}&directionsmode=driving`
      : `google.navigation:q=${dest}`;
    const webUrl = `https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${dest}`;
    const canNative = await Linking.canOpenURL(nativeUrl).catch(() => false);
    Linking.openURL(canNative ? nativeUrl : webUrl).catch(() =>
      Alert.alert('Erreur', "Impossible d'ouvrir la navigation.")
    );
  };

  return (
    <TouchableOpacity
      style={[styles.storeRow, selected && styles.storeRowSelected]}
      onPress={() => onFocus(store)}
      activeOpacity={0.7}
    >
      {/* Checkbox */}
      <TouchableOpacity
        style={[styles.checkbox, selected && styles.checkboxSelected]}
        onPress={() => onToggle(store.id)}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        {selected && <Ionicons name="checkmark" size={14} color={C.white} />}
      </TouchableOpacity>

      {/* Color dot */}
      <View style={[styles.colorDot, { backgroundColor: color }]} />

      {/* Info */}
      <View style={styles.storeInfo}>
        <Text style={styles.storeName} numberOfLines={1}>{store.name}</Text>
        <Text style={styles.storeCity} numberOfLines={1}>
          {store.city ?? store.address ?? '—'}
        </Text>
      </View>

      {/* Badges + Navigate */}
      <View style={styles.storeRight}>
        <View style={[styles.badge, { backgroundColor: color + '22' }]}>
          <Text style={[styles.badgeText, { color }]}>{store.product_count} prod.</Text>
        </View>
        <Text style={styles.distanceText}>{distanceLabel(store.distance_km)}</Text>
        <TouchableOpacity
          style={styles.navBtn}
          onPress={navigateToStore}
          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        >
          <Ionicons name="navigate" size={16} color={C.primary} />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
};

// ─── Sub-component: Route result modal ────────────────────────────────────────

interface RouteModalProps {
  visible: boolean;
  route: RouteOptimizeResponse | null;
  originLat: number;
  originLng: number;
  onClose: () => void;
}

const RouteModal: React.FC<RouteModalProps> = ({ visible, route, originLat, originLng, onClose }) => {
  if (!route) return null;

  const openGoogleMaps = async () => {
    if (route.stops.length === 0) return;

    const lastStop = route.stops[route.stops.length - 1];
    const destination = `${lastStop.latitude},${lastStop.longitude}`;

    const waypoints = route.stops.length > 1
      ? route.stops.slice(0, -1).map((s) => `${s.latitude},${s.longitude}`).join('|')
      : undefined;

    // Try native Google Maps app first (Android + iOS)
    const nativeBase = Platform.OS === 'ios'
      ? `comgooglemaps://?origin=${originLat},${originLng}&daddr=${destination}&directionsmode=driving`
      : `google.navigation:q=${destination}`;

    const webUrl =
      `https://www.google.com/maps/dir/?api=1` +
      `&origin=${originLat},${originLng}` +
      `&destination=${destination}` +
      (waypoints ? `&waypoints=${encodeURIComponent(waypoints)}` : '');

    const canOpenNative = await Linking.canOpenURL(nativeBase).catch(() => false);
    Linking.openURL(canOpenNative ? nativeBase : webUrl).catch(() =>
      Alert.alert('Erreur', "Impossible d'ouvrir la navigation.")
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalSheet}>
          {/* Header */}
          <View style={styles.modalHeader}>
            <View>
              <Text style={styles.modalTitle}>Parcours optimisé</Text>
              <Text style={styles.modalSubtitle}>
                {route.total_stores} magasin{route.total_stores > 1 ? 's' : ''} •{' '}
                {route.total_distance_km.toFixed(1)} km •{' '}
                <Text style={styles.savingsText}>
                  −{route.total_savings.toFixed(2)} MAD
                </Text>
              </Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.modalClose}>
              <Ionicons name="close" size={22} color={C.textSub} />
            </TouchableOpacity>
          </View>

          <ScrollView
            style={styles.modalScroll}
            showsVerticalScrollIndicator={false}
          >
            {route.stops.map((stop) => (
              <View key={stop.store_id} style={styles.stopCard}>
                {/* Step number */}
                <View style={styles.stopBadge}>
                  <Text style={styles.stopBadgeText}>{stop.order}</Text>
                </View>

                <View style={styles.stopContent}>
                  <Text style={styles.stopName}>{stop.store_name}</Text>
                  <Text style={styles.stopAddress} numberOfLines={2}>
                    {stop.store_address}
                  </Text>

                  {stop.products_to_buy.length > 0 && (
                    <View style={styles.productsContainer}>
                      {stop.products_to_buy.map((p, i) => (
                        <View key={i} style={styles.productChip}>
                          <Text style={styles.productChipText}>{p}</Text>
                        </View>
                      ))}
                    </View>
                  )}

                  {stop.estimated_savings > 0 && (
                    <Text style={styles.stopSavings}>
                      Économie estimée :{' '}
                      <Text style={styles.savingsAmount}>
                        −{stop.estimated_savings.toFixed(2)} MAD
                      </Text>
                    </Text>
                  )}
                </View>
              </View>
            ))}

            {/* Spacer for buttons */}
            <View style={{ height: 16 }} />
          </ScrollView>

          {/* Actions */}
          <View style={styles.modalActions}>
            <TouchableOpacity
              style={styles.mapsButton}
              onPress={openGoogleMaps}
              activeOpacity={0.85}
            >
              <Ionicons name="navigate" size={18} color={C.white} />
              <Text style={styles.mapsButtonText}>
                Lancer l'itinéraire Google Maps
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.closeButton}
              onPress={onClose}
              activeOpacity={0.7}
            >
              <Text style={styles.closeButtonText}>Fermer</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

// ─── Map error boundary (évite un crash dur si la carte échoue à charger) ──────

interface MapBoundaryState { hasError: boolean; }

class MapErrorBoundary extends React.Component<React.PropsWithChildren, MapBoundaryState> {
  state: MapBoundaryState = { hasError: false };

  static getDerivedStateFromError(): MapBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Log silencieux — on ne veut surtout pas faire planter l'app
    console.warn('[Carte] MapView indisponible :', error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={[styles.map, styles.mapFallback]}>
          <Ionicons name="map-outline" size={40} color={MARKER_GRAY} />
          <Text style={styles.mapFallbackText}>
            Carte indisponible sur cet appareil.{'\n'}Utilisez l'onglet « Liste » ci-dessous.
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

const MagasinsProchesScreen: React.FC<Props> = () => {
  const mapRef = useRef<MapView>(null);

  // Location state
  const [locationStatus, setLocationStatus] = useState<
    'idle' | 'loading' | 'granted' | 'denied' | 'error'
  >('idle');
  const [userLat, setUserLat] = useState<number | null>(null);
  const [userLng, setUserLng] = useState<number | null>(null);

  // Profile radius
  const [radius, setRadius] = useState(DEFAULT_RADIUS);
  React.useEffect(() => {
    AsyncStorage.getItem(FOYER_KEY).then((raw) => {
      if (raw) {
        try { const f = JSON.parse(raw); if (f.rayonKm) setRadius(f.rayonKm); } catch { /* */ }
      }
    });
  }, []);

  // UI state — sans clé Google Maps, on démarre (et on reste) sur la liste
  const [viewMode, setViewMode] = useState<ViewMode>(MAPS_ENABLED ? 'carte' : 'liste');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Route state
  const [optimizing, setOptimizing] = useState(false);
  const [routeResult, setRouteResult] = useState<RouteOptimizeResponse | null>(null);
  const [routeModalVisible, setRouteModalVisible] = useState(false);

  // ── Request location ─────────────────────────────────────────────────────────

  const requestLocation = useCallback(async () => {
    setLocationStatus('loading');
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocationStatus('denied');
        return;
      }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setUserLat(pos.coords.latitude);
      setUserLng(pos.coords.longitude);
      setLocationStatus('granted');
    } catch {
      setLocationStatus('error');
    }
  }, []);

  // Auto-request on first render
  React.useEffect(() => {
    requestLocation();
  }, [requestLocation]);

  // ── Nearby stores query ───────────────────────────────────────────────────────

  const [refreshing, setRefreshing] = useState(false);

  const {
    data: storesPrimary = [],
    isLoading: storesLoading,
    isError: storesError,
    refetch,
  } = useQuery({
    queryKey: ['stores-nearby', userLat, userLng, radius],
    queryFn: () => StoresAPI.getNearby(userLat!, userLng!, radius),
    enabled: locationStatus === 'granted' && userLat !== null && userLng !== null,
    staleTime: 30 * 1000,  // 30s — se rafraîchit régulièrement
  });

  // Fallback : si aucun magasin dans le rayon profil → recherche élargie 200 km
  const needsFallback = !storesLoading && !storesError && storesPrimary.length === 0;
  const {
    data: storesFallback = [],
    isLoading: fallbackLoading,
    refetch: refetchFallback,
  } = useQuery({
    queryKey: ['stores-nearby-fallback', userLat, userLng],
    queryFn: () => StoresAPI.getNearby(userLat!, userLng!, 200),
    enabled: needsFallback && userLat !== null && userLng !== null,
    staleTime: 60 * 1000,
  });

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([refetch(), needsFallback ? refetchFallback() : Promise.resolve()]);
    } finally {
      setRefreshing(false);
    }
  }, [refetch, refetchFallback, needsFallback]);

  const isFallbackMode = needsFallback && storesFallback.length > 0;
  const stores = isFallbackMode ? storesFallback : storesPrimary;

  // ── Selection helpers ─────────────────────────────────────────────────────────

  const toggleStore = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const focusStore = useCallback((store: StoreNearby) => {
    if (
      viewMode === 'carte' &&
      store.latitude !== null &&
      store.longitude !== null &&
      mapRef.current
    ) {
      mapRef.current.animateToRegion(
        {
          latitude: store.latitude,
          longitude: store.longitude,
          latitudeDelta: 0.01,
          longitudeDelta: 0.01,
        },
        600
      );
    }
  }, [viewMode]);

  // ── Route optimization ────────────────────────────────────────────────────────

  const handleOptimize = useCallback(async () => {
    if (selectedIds.size < 2 || userLat === null || userLng === null) return;

    setOptimizing(true);
    try {
      const ids = Array.from(selectedIds);
      const result = await StoresAPI.optimizeRoute(ids, undefined);
      setRouteResult(result as RouteOptimizeResponse);
      setRouteModalVisible(true);
    } catch {
      Alert.alert(
        'Erreur réseau',
        'Impossible de calculer le parcours. Vérifiez votre connexion.'
      );
    } finally {
      setOptimizing(false);
    }
  }, [selectedIds, userLat, userLng]);

  // ── Render states ─────────────────────────────────────────────────────────────

  if (locationStatus === 'idle' || locationStatus === 'loading') {
    return (
      <SafeAreaView style={styles.centered}>
        <ActivityIndicator size="large" color={C.primary} />
        <Text style={styles.loadingText}>Localisation en cours…</Text>
      </SafeAreaView>
    );
  }

  if (locationStatus === 'denied') {
    return (
      <SafeAreaView style={styles.centered}>
        <View style={styles.errorCard}>
          <Ionicons name="location-outline" size={48} color={MARKER_GRAY} />
          <Text style={styles.errorTitle}>Accès refusé</Text>
          <Text style={styles.errorBody}>
            PrixMaroc a besoin de votre position pour afficher les magasins proches.
            Veuillez activer la localisation dans les réglages de l'application.
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={requestLocation}
            activeOpacity={0.85}
          >
            <Ionicons name="refresh" size={16} color={C.white} />
            <Text style={styles.retryText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  if (locationStatus === 'error') {
    return (
      <SafeAreaView style={styles.centered}>
        <View style={styles.errorCard}>
          <Ionicons name="warning-outline" size={48} color={C.promo} />
          <Text style={styles.errorTitle}>Erreur de localisation</Text>
          <Text style={styles.errorBody}>
            Impossible d'obtenir votre position. Assurez-vous que le GPS est activé.
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={requestLocation}
            activeOpacity={0.85}
          >
            <Ionicons name="refresh" size={16} color={C.white} />
            <Text style={styles.retryText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // locationStatus === 'granted'
  const lat = userLat!;
  const lng = userLng!;

  return (
    <View style={styles.root}>
      {/* ── MAP (montée uniquement si une clé Google Maps est présente) ── */}
      {!MAPS_ENABLED ? (
        <View style={[styles.map, styles.mapFallback]}>
          <Ionicons name="map-outline" size={40} color={MARKER_GRAY} />
          <Text style={styles.mapFallbackText}>
            Vue liste des magasins proches ci-dessous.{'\n'}La carte interactive arrive bientôt.
          </Text>
        </View>
      ) : (
      <MapErrorBoundary>
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={{
          latitude: lat,
          longitude: lng,
          latitudeDelta: 0.08,
          longitudeDelta: 0.08,
        }}
        showsUserLocation={false}
        showsMyLocationButton={false}
      >
        {/* User position */}
        <Circle
          center={{ latitude: lat, longitude: lng }}
          radius={80}
          fillColor="rgba(59,130,246,0.25)"
          strokeColor="rgba(59,130,246,0.6)"
          strokeWidth={2}
        />
        <Marker
          coordinate={{ latitude: lat, longitude: lng }}
          anchor={{ x: 0.5, y: 0.5 }}
        >
          <View style={styles.userMarker}>
            <View style={styles.userMarkerInner} />
          </View>
        </Marker>

        {/* Store markers */}
        {stores.map((store) => {
          if (store.latitude === null || store.longitude === null) return null;
          const color = markerColor(store.product_count);
          const isSelected = selectedIds.has(store.id);
          return (
            <Marker
              key={store.id}
              coordinate={{ latitude: store.latitude, longitude: store.longitude }}
              onPress={() => toggleStore(store.id)}
              anchor={{ x: 0.5, y: 1 }}
            >
              <View style={[styles.storeMarker, { borderColor: color }, isSelected && styles.storeMarkerSelected]}>
                <View style={[styles.storeMarkerDot, { backgroundColor: color }]} />
                {isSelected && (
                  <View style={[styles.storeMarkerCheck, { backgroundColor: color }]}>
                    <Ionicons name="checkmark" size={8} color={C.white} />
                  </View>
                )}
              </View>
              <View style={[styles.markerTail, { borderTopColor: color }]} />
            </Marker>
          );
        })}
      </MapView>
      </MapErrorBoundary>
      )}

      {/* Recenter button */}
      {MAPS_ENABLED && (
      <TouchableOpacity
        style={styles.recenterBtn}
        onPress={() => {
          mapRef.current?.animateToRegion(
            { latitude: lat, longitude: lng, latitudeDelta: 0.08, longitudeDelta: 0.08 },
            500
          );
        }}
        activeOpacity={0.8}
      >
        <Ionicons name="locate" size={22} color={C.primary} />
      </TouchableOpacity>
      )}

      {/* ── BOTTOM PANEL ── */}
      <View style={styles.panel}>
        {/* Panel handle */}
        <View style={styles.panelHandle} />

        {/* Tabs */}
        <View style={styles.tabRow}>
          <TouchableOpacity
            style={[styles.tab, viewMode === 'carte' && styles.tabActive]}
            onPress={() => setViewMode('carte')}
            activeOpacity={0.7}
          >
            <Ionicons
              name="map-outline"
              size={16}
              color={viewMode === 'carte' ? C.primary : C.textSub}
            />
            <Text style={[styles.tabText, viewMode === 'carte' && styles.tabTextActive]}>
              Carte
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tab, viewMode === 'liste' && styles.tabActive]}
            onPress={() => setViewMode('liste')}
            activeOpacity={0.7}
          >
            <Ionicons
              name="list-outline"
              size={16}
              color={viewMode === 'liste' ? C.primary : C.textSub}
            />
            <Text style={[styles.tabText, viewMode === 'liste' && styles.tabTextActive]}>
              Liste
            </Text>
          </TouchableOpacity>

          {/* Store count */}
          <View style={styles.tabSpacer} />
          {storesLoading || fallbackLoading ? (
            <ActivityIndicator size="small" color={C.primary} style={{ marginRight: 12 }} />
          ) : (
            <Text style={styles.storeCount}>
              {stores.length} magasin{stores.length !== 1 ? 's' : ''}
              {isFallbackMode ? ' (zone élargie)' : ''}
            </Text>
          )}
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Content */}
        {(storesLoading || fallbackLoading) ? (
          <View style={styles.panelLoader}>
            <ActivityIndicator size="large" color={C.primary} />
            <Text style={styles.loadingText}>Recherche des magasins…</Text>
          </View>
        ) : storesError ? (
          <View style={styles.panelLoader}>
            <Ionicons name="cloud-offline-outline" size={40} color={MARKER_GRAY} />
            <Text style={styles.errorTitle}>Erreur réseau</Text>
            <TouchableOpacity style={styles.retryButtonSmall} onPress={() => refetch()}>
              <Text style={styles.retryTextSmall}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        ) : stores.length === 0 ? (
          <View style={styles.panelLoader}>
            <Ionicons name="storefront-outline" size={40} color={MARKER_GRAY} />
            <Text style={styles.errorTitle}>Aucun magasin référencé</Text>
            <Text style={styles.errorBody}>
              Nous n'avons pas encore de magasins enregistrés dans votre région. Notre base de données s'enrichit régulièrement.
            </Text>
            <TouchableOpacity style={styles.retryButtonSmall} onPress={() => refetch()}>
              <Text style={styles.retryTextSmall}>Actualiser</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <FlatList
            data={stores}
            keyExtractor={(item) => String(item.id)}
            renderItem={({ item }) => (
              <StoreRow
                store={item}
                selected={selectedIds.has(item.id)}
                onToggle={toggleStore}
                onFocus={focusStore}
                userLat={lat}
                userLng={lng}
              />
            )}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
            ItemSeparatorComponent={() => <View style={styles.itemSep} />}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={handleRefresh}
                colors={[C.primary]}
                tintColor={C.primary}
              />
            }
          />
        )}

        {/* Bouton navigation : 1 magasin → itinéraire direct, 2+ → optimisation */}
        {selectedIds.size >= 1 && (
          <View style={styles.optimizeContainer}>
            {selectedIds.size === 1 ? (
              // Navigation directe vers le magasin sélectionné
              <TouchableOpacity
                style={styles.optimizeButton}
                activeOpacity={0.85}
                onPress={() => {
                  const store = stores.find((s) => selectedIds.has(s.id));
                  if (store && store.latitude && store.longitude) {
                    const dest = `${store.latitude},${store.longitude}`;
                    const nativeUrl = Platform.OS === 'ios'
                      ? `comgooglemaps://?origin=${lat},${lng}&daddr=${dest}&directionsmode=driving`
                      : `google.navigation:q=${dest}`;
                    const webUrl = `https://www.google.com/maps/dir/?api=1&origin=${lat},${lng}&destination=${dest}`;
                    Linking.canOpenURL(nativeUrl).then((can) =>
                      Linking.openURL(can ? nativeUrl : webUrl)
                    ).catch(() => Linking.openURL(webUrl));
                  }
                }}
              >
                <Ionicons name="navigate" size={18} color={C.white} />
                <Text style={styles.optimizeText}>Itinéraire vers ce magasin</Text>
              </TouchableOpacity>
            ) : (
              // Optimisation multi-magasins
              <TouchableOpacity
                style={[styles.optimizeButton, optimizing && styles.optimizeButtonDisabled]}
                onPress={handleOptimize}
                disabled={optimizing}
                activeOpacity={0.85}
              >
                {optimizing ? (
                  <ActivityIndicator size="small" color={C.white} />
                ) : (
                  <Ionicons name="git-branch-outline" size={18} color={C.white} />
                )}
                <Text style={styles.optimizeText}>
                  {optimizing
                    ? 'Calcul en cours…'
                    : `Optimiser le parcours (${selectedIds.size} magasins)`}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>

      {/* Legend (carte mode only, when stores loaded) */}
      {MAPS_ENABLED && viewMode === 'carte' && stores.length > 0 && (
        <View style={styles.legend}>
          <LegendDot color={MARKER_GREEN}  label="> 20 produits" />
          <LegendDot color={MARKER_ORANGE} label="5–20 produits" />
          <LegendDot color={MARKER_GRAY}   label="< 5 produits" />
        </View>
      )}

      {/* Route result modal */}
      <RouteModal
        visible={routeModalVisible}
        route={routeResult}
        originLat={lat}
        originLng={lng}
        onClose={() => setRouteModalVisible(false)}
      />
    </View>
  );
};

// ─── Legend dot ───────────────────────────────────────────────────────────────

const LegendDot: React.FC<{ color: string; label: string }> = ({ color, label }) => (
  <View style={styles.legendItem}>
    <View style={[styles.legendDot, { backgroundColor: color }]} />
    <Text style={styles.legendLabel}>{label}</Text>
  </View>
);

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  // ── Layout ──────────────────────────────────────────────────────────────────
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },
  centered: {
    flex: 1,
    backgroundColor: C.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },

  // ── Map ─────────────────────────────────────────────────────────────────────
  map: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: PANEL_HEIGHT - 24, // slight overlap for smooth transition
  },
  mapFallback: {
    backgroundColor: '#eef2f6',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    gap: 10,
  },
  mapFallbackText: {
    fontSize: 13,
    color: C.textSub,
    textAlign: 'center',
    lineHeight: 19,
  },

  // ── User marker ─────────────────────────────────────────────────────────────
  userMarker: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: 'rgba(59,130,246,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#3b82f6',
  },
  userMarkerInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#3b82f6',
  },

  // ── Store marker ─────────────────────────────────────────────────────────────
  storeMarker: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: C.white,
    borderWidth: 2.5,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
    elevation: 4,
  },
  storeMarkerSelected: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 3,
  },
  storeMarkerDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  storeMarkerCheck: {
    position: 'absolute',
    top: -4,
    right: -4,
    width: 14,
    height: 14,
    borderRadius: 7,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: C.white,
  },
  markerTail: {
    width: 0,
    height: 0,
    alignSelf: 'center',
    borderLeftWidth: 5,
    borderRightWidth: 5,
    borderTopWidth: 6,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    marginTop: -1,
  },

  // ── Recenter button ──────────────────────────────────────────────────────────
  recenterBtn: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 56 : 40,
    right: 14,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: C.white,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 5,
  },

  // ── Legend ───────────────────────────────────────────────────────────────────
  legend: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 56 : 40,
    left: 14,
    backgroundColor: C.white,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
    elevation: 4,
    gap: 5,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
  legendLabel: {
    fontSize: 11,
    color: C.textSub,
    fontWeight: '500',
  },

  // ── Bottom panel ─────────────────────────────────────────────────────────────
  panel: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: PANEL_HEIGHT,
    backgroundColor: C.white,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 12,
    overflow: 'hidden',
  },
  panelHandle: {
    width: 36,
    height: 4,
    backgroundColor: C.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 10,
    marginBottom: 4,
  },

  // ── Tabs ─────────────────────────────────────────────────────────────────────
  tabRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 6,
    alignItems: 'center',
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 7,
    paddingHorizontal: 14,
    borderRadius: 20,
    marginRight: 8,
  },
  tabActive: {
    backgroundColor: C.primaryLight ?? '#dcfce7',
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.textSub,
  },
  tabTextActive: {
    color: C.primary,
  },
  tabSpacer: {
    flex: 1,
  },
  storeCount: {
    fontSize: 12,
    color: C.textMuted,
    marginRight: 4,
  },
  divider: {
    height: 1,
    backgroundColor: C.border,
    marginHorizontal: 16,
  },

  // ── List ─────────────────────────────────────────────────────────────────────
  listContent: {
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 80, // space for optimize button
  },
  panelLoader: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 24,
  },

  // ── Store row ─────────────────────────────────────────────────────────────────
  storeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderRadius: 12,
    backgroundColor: C.white,
    gap: 10,
  },
  storeRowSelected: {
    backgroundColor: '#f0fdf4',
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.white,
  },
  checkboxSelected: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  colorDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    flexShrink: 0,
  },
  storeInfo: {
    flex: 1,
    minWidth: 0,
  },
  storeName: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  storeCity: {
    fontSize: 12,
    color: C.textMuted,
    marginTop: 1,
  },
  storeRight: {
    alignItems: 'flex-end',
    gap: 3,
    flexShrink: 0,
  },
  badge: {
    borderRadius: 8,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  distanceText: {
    fontSize: 11,
    color: C.textMuted,
    fontWeight: '500',
  },
  navBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: `${C.primary}15`,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  itemSep: {
    height: 1,
    backgroundColor: C.border,
    marginHorizontal: 4,
  },

  // ── Optimize button ───────────────────────────────────────────────────────────
  optimizeContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 16,
    paddingBottom: Platform.OS === 'ios' ? 28 : 16,
    paddingTop: 10,
    backgroundColor: C.white,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  optimizeButton: {
    backgroundColor: C.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  optimizeButtonDisabled: {
    opacity: 0.7,
  },
  optimizeText: {
    color: C.white,
    fontSize: 15,
    fontWeight: '700',
  },

  // ── Error / loading ───────────────────────────────────────────────────────────
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: C.textSub,
    fontWeight: '500',
  },
  errorCard: {
    backgroundColor: C.white,
    borderRadius: 20,
    padding: 28,
    alignItems: 'center',
    width: '100%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 6,
    gap: 12,
  },
  errorTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: C.text,
    textAlign: 'center',
  },
  errorBody: {
    fontSize: 14,
    color: C.textSub,
    textAlign: 'center',
    lineHeight: 20,
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: C.primary,
    paddingVertical: 10,
    paddingHorizontal: 22,
    borderRadius: 12,
    marginTop: 4,
  },
  retryText: {
    color: C.white,
    fontWeight: '700',
    fontSize: 14,
  },
  retryButtonSmall: {
    paddingVertical: 8,
    paddingHorizontal: 18,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: C.primary,
  },
  retryTextSmall: {
    color: C.primary,
    fontWeight: '600',
    fontSize: 13,
  },

  // ── Route modal ───────────────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: C.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: SCREEN_HEIGHT * 0.85,
    paddingBottom: Platform.OS === 'ios' ? 32 : 16,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
  },
  modalSubtitle: {
    fontSize: 13,
    color: C.textSub,
    marginTop: 3,
  },
  savingsText: {
    color: C.primary,
    fontWeight: '600',
  },
  modalClose: {
    padding: 4,
    marginTop: -2,
  },
  modalScroll: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },

  // ── Stop card ─────────────────────────────────────────────────────────────────
  stopCard: {
    flexDirection: 'row',
    gap: 12,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  stopBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  stopBadgeText: {
    color: C.white,
    fontSize: 13,
    fontWeight: '700',
  },
  stopContent: {
    flex: 1,
    gap: 4,
  },
  stopName: {
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
  },
  stopAddress: {
    fontSize: 13,
    color: C.textSub,
    lineHeight: 18,
  },
  productsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
    marginTop: 4,
  },
  productChip: {
    backgroundColor: '#f0fdf4',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  productChipText: {
    fontSize: 11,
    color: C.primary,
    fontWeight: '500',
  },
  stopSavings: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 4,
  },
  savingsAmount: {
    color: C.primary,
    fontWeight: '700',
  },

  // ── Modal actions ─────────────────────────────────────────────────────────────
  modalActions: {
    paddingHorizontal: 16,
    paddingTop: 14,
    gap: 10,
  },
  mapsButton: {
    backgroundColor: C.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  mapsButtonText: {
    color: C.white,
    fontWeight: '700',
    fontSize: 15,
  },
  closeButton: {
    paddingVertical: 12,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: C.border,
    alignItems: 'center',
  },
  closeButtonText: {
    color: C.textSub,
    fontWeight: '600',
    fontSize: 14,
  },
});

export default MagasinsProchesScreen;
