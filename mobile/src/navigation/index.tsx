/**
 * Navigation PrixMaroc
 * RootStack → AuthStack | MainTabs
 * MainTabs → 5 onglets (chacun avec son propre Stack)
 *
 * navigationRef : exporté pour permettre la navigation depuis les services
 * (deep links notifications, etc.)
 */
import React, { useRef } from 'react';
import { Platform, View, Text } from 'react-native';
import {
  NavigationContainer,
  NavigationContainerRef,
  createNavigationContainerRef,
} from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';

import { Colors, C } from '@constants/colors';
import { useAuthStore } from '@store/authStore';

import type {
  RootStackParamList,
  AuthStackParamList,
  MainTabParamList,
  AccueilStackParamList,
  ComparerStackParamList,
  ListesStackParamList,
  ProfilStackParamList,
} from '@types/models';

// ── Écrans Auth ───────────────────────────────────────────────────────────────
import LoginScreen from '@screens/Auth/LoginScreen';
import RegisterScreen from '@screens/Auth/RegisterScreen';

// ── Écrans Accueil ────────────────────────────────────────────────────────────
import DashboardScreen from '@screens/Accueil/DashboardScreen';
import ProduitDetailScreen from '@screens/Accueil/ProduitDetailScreen';
import PromotionsScreen from '@screens/Accueil/PromotionsScreen';
import MagasinsProchesScreen from '@screens/Accueil/MagasinsProchesScreen';
import SoukPricesScreen from '@screens/Accueil/SoukPricesScreen';

// ── Écrans Scanner ────────────────────────────────────────────────────────────
import ScannerScreen from '@screens/Scanner/ScannerScreen';

// ── Écrans Comparer ───────────────────────────────────────────────────────────
import RechercheScreen from '@screens/Comparer/RechercheScreen';
import ComparerPrixScreen from '@screens/Comparer/ComparerPrixScreen';
import HistoriquePrixScreen from '@screens/Comparer/HistoriquePrixScreen';

// ── Écrans Listes ─────────────────────────────────────────────────────────────
import MesListesScreen from '@screens/Listes/MesListesScreen';
import DetailListeScreen from '@screens/Listes/DetailListeScreen';
import NouvelleListeIAScreen from '@screens/Listes/NouvelleListeIAScreen';

// ── Écrans Profil ─────────────────────────────────────────────────────────────
import MonProfilScreen from '@screens/Profil/MonProfilScreen';
import MesScansScreen from '@screens/Profil/MesScansScreen';
import MesAlertesScreen from '@screens/Profil/MesAlertesScreen';
import ParametresScreen from '@screens/Profil/ParametresScreen';

// ─────────────────────────────────────────────────────────────────────────────

const RootStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

const AccueilStack = createNativeStackNavigator<AccueilStackParamList>();
const ComparerStack = createNativeStackNavigator<ComparerStackParamList>();
const ListesStack = createNativeStackNavigator<ListesStackParamList>();
const ProfilStack = createNativeStackNavigator<ProfilStackParamList>();

// ── NavigationRef global — utilisé par le service de notifications ────────────

export const navigationRef = createNavigationContainerRef<RootStackParamList>();

/**
 * Navigue depuis n'importe où dans l'app, même hors d'un composant React.
 * Utilisé par le handler de notification (deep link tap).
 */
export function navigateFromNotification(screen: string, params?: object) {
  if (!navigationRef.isReady()) return;
  try {
    // @ts-ignore — dynamic screen name from notification payload
    navigationRef.navigate('Main', { screen: 'Accueil', params: { screen, params } });
  } catch (e) {
    // Fallback : navigate to root
    try {
      // @ts-ignore
      navigationRef.navigate(screen as any, params as any);
    } catch { /* ignore */ }
  }
}

// ── Linking config pour deep links prixmaroc:// ───────────────────────────────

export const linking = {
  prefixes: ['prixmaroc://', 'https://prixmaroc.ma'],
  config: {
    screens: {
      Main: {
        screens: {
          Accueil: {
            screens: {
              Dashboard:       'dashboard',
              Promotions:      'promotions',
              MagasinsProches: 'magasins',
              SoukPrices:      'souk',
              ProduitDetail:   'produit/:productId',
            },
          },
          Listes: {
            screens: {
              MesListes:       'listes',
              DetailListe:     'liste/:listId',
              NouvelleListeIA: 'liste/ia',
            },
          },
          Profil: {
            screens: {
              MonProfil:  'profil',
              Parametres: 'parametres',
            },
          },
        },
      },
    },
  },
};

// ── Options header partagées ──────────────────────────────────────────────────

const headerOptions = {
  headerStyle: { backgroundColor: C.primary },
  headerTintColor: C.white,
  headerTitleStyle: { fontWeight: '700' as const, fontSize: 17 },
  headerBackTitle: '',
};

// ── Stacks individuels ────────────────────────────────────────────────────────

function AccueilNavigator() {
  return (
    <AccueilStack.Navigator screenOptions={headerOptions}>
      <AccueilStack.Screen name="Dashboard" component={DashboardScreen} options={{ title: 'PrixMaroc' }} />
      <AccueilStack.Screen name="ProduitDetail" component={ProduitDetailScreen}
        options={({ route }) => ({ title: route.params.productName })} />
      <AccueilStack.Screen name="Promotions" component={PromotionsScreen} options={{ title: '🔥 Promotions' }} />
      <AccueilStack.Screen name="MagasinsProches" component={MagasinsProchesScreen} options={{ title: 'Magasins proches' }} />
      <AccueilStack.Screen name="SoukPrices" component={SoukPricesScreen} options={{ title: '🧺 Prix du souk' }} />
    </AccueilStack.Navigator>
  );
}

function ScannerNavigator() {
  return <ScannerScreen />;
}

function ComparerNavigator() {
  return (
    <ComparerStack.Navigator screenOptions={headerOptions}>
      <ComparerStack.Screen name="Recherche" component={RechercheScreen} options={{ title: 'Comparer les prix' }} />
      <ComparerStack.Screen name="ProduitDetail" component={ProduitDetailScreen}
        options={({ route }) => ({ title: route.params.productName })} />
      <ComparerStack.Screen name="ComparerPrix" component={ComparerPrixScreen} options={{ title: 'Comparaison' }} />
      <ComparerStack.Screen name="HistoriquePrix" component={HistoriquePrixScreen}
        options={({ route }) => ({ title: `Historique — ${route.params.productName}` })} />
    </ComparerStack.Navigator>
  );
}

function ListesNavigator() {
  return (
    <ListesStack.Navigator screenOptions={headerOptions}>
      <ListesStack.Screen name="MesListes" component={MesListesScreen} options={{ title: 'Mes listes' }} />
      <ListesStack.Screen name="DetailListe" component={DetailListeScreen}
        options={({ route }) => ({ title: route.params.listName })} />
      <ListesStack.Screen name="NouvelleListeIA" component={NouvelleListeIAScreen} options={{ title: '✨ Liste IA' }} />
    </ListesStack.Navigator>
  );
}

function ProfilNavigator() {
  return (
    <ProfilStack.Navigator screenOptions={headerOptions}>
      <ProfilStack.Screen name="MonProfil" component={MonProfilScreen} options={{ title: 'Mon profil' }} />
      <ProfilStack.Screen name="MesScans" component={MesScansScreen} options={{ title: 'Mes tickets scannés' }} />
      <ProfilStack.Screen name="MesAlertes" component={MesAlertesScreen} options={{ title: 'Mes alertes prix' }} />
      <ProfilStack.Screen name="Parametres" component={ParametresScreen} options={{ title: 'Préférences' }} />
    </ProfilStack.Navigator>
  );
}

// ── Tab Icon helper ───────────────────────────────────────────────────────────

type IoniconsName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof MainTabParamList, { active: IoniconsName; inactive: IoniconsName }> = {
  Accueil:  { active: 'home',          inactive: 'home-outline' },
  Scanner:  { active: 'scan',          inactive: 'scan-outline' },
  Comparer: { active: 'stats-chart',   inactive: 'stats-chart-outline' },
  Listes:   { active: 'list',          inactive: 'list-outline' },
  Profil:   { active: 'person',        inactive: 'person-outline' },
};

const TAB_LABELS: Record<keyof MainTabParamList, string> = {
  Accueil:  'Accueil',
  Scanner:  'Scanner',
  Comparer: 'Comparer',
  Listes:   'Listes',
  Profil:   'Profil',
};

// ── Main Tabs ─────────────────────────────────────────────────────────────────

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: '#8A9A92',
        tabBarStyle: {
          backgroundColor: '#ffffff',
          borderTopColor: '#E9F0E6',
          borderTopWidth: 1,
          height: Platform.OS === 'ios' ? 90 : 68,
          paddingBottom: Platform.OS === 'ios' ? 26 : 10,
          paddingTop: 6,
          elevation: 20,
          shadowColor: '#000',
          shadowOffset: { width: 0, height: -4 },
          shadowOpacity: 0.08,
          shadowRadius: 16,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '700', marginTop: 2 },
        tabBarItemStyle: { borderRadius: 12 },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name as keyof MainTabParamList];
          return (
            <View style={{
              alignItems: 'center',
              justifyContent: 'center',
              width: 40,
              height: 32,
              borderRadius: 10,
              backgroundColor: focused ? `${C.primary}18` : 'transparent',
            }}>
              <Ionicons name={focused ? icons.active : icons.inactive} size={size} color={color} />
            </View>
          );
        },
        tabBarLabel: TAB_LABELS[route.name as keyof MainTabParamList],
      })}
    >
      <Tab.Screen name="Accueil"  component={AccueilNavigator} />
      <Tab.Screen name="Scanner"  component={ScannerNavigator}
        options={{
          tabBarIcon: ({ focused }) => (
            <View style={{
              backgroundColor: C.primary,
              width: 56, height: 56,
              borderRadius: 28,
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: Platform.OS === 'ios' ? 12 : 0,
              shadowColor: C.primary,
              shadowOffset: { width: 0, height: 4 },
              shadowOpacity: 0.35,
              shadowRadius: 8,
              elevation: 8,
            }}>
              <Ionicons name="scan" size={26} color={C.white} />
            </View>
          ),
          tabBarLabel: () => null,
        }}
      />
      <Tab.Screen name="Comparer" component={ComparerNavigator} />
      <Tab.Screen name="Listes"   component={ListesNavigator} />
      <Tab.Screen name="Profil"   component={ProfilNavigator} />
    </Tab.Navigator>
  );
}

// ── Auth Stack ────────────────────────────────────────────────────────────────

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
    </AuthStack.Navigator>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function Navigation() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: C.primary }}>
        <Text style={{ color: C.white, fontSize: 24, fontWeight: '700' }}>PrixMaroc</Text>
        <Text style={{ color: Colors.primary[200], marginTop: 8 }}>Chargement…</Text>
      </View>
    );
  }

  return (
    <NavigationContainer ref={navigationRef} linking={linking}>
      <RootStack.Navigator screenOptions={{ headerShown: false }}>
        {isAuthenticated ? (
          <RootStack.Screen name="Main" component={MainTabs} />
        ) : (
          <RootStack.Screen name="Auth" component={AuthNavigator} />
        )}
      </RootStack.Navigator>
    </NavigationContainer>
  );
}
