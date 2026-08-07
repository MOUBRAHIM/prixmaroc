import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  TextInput,
  ActivityIndicator,
  Image,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as ImagePicker from 'expo-image-picker';
import { AuthAPI, ProfileAPI, AdminAPI } from '@services/api';
import { useAuthStore } from '@store/authStore';
import { C } from '@constants/colors';
import type { ProfilStackParamList } from '@types/models';

type Props = NativeStackScreenProps<ProfilStackParamList, 'MonProfil'>;

const FOYER_KEY = 'prixmaroc:foyer';

const MOROCCAN_CITIES = [
  'Casablanca', 'Rabat', 'Marrakech', 'Fès', 'Tanger', 'Agadir',
  'Meknès', 'Oujda', 'Kénitra', 'Tétouan', 'Safi', 'Mohammedia',
  'Laâyoune', 'El Jadida', 'Nador', 'Béni Mellal', 'Khouribga',
];

const STORE_OPTIONS = [
  { slug: 'marjane', name: 'Marjane' },
  { slug: 'carrefour', name: 'Carrefour' },
  { slug: 'labelvie', name: "Label'Vie" },
  { slug: 'bim', name: 'BIM' },
  { slug: 'atacadao', name: 'Atacadão' },
  { slug: 'acima', name: 'Acima' },
];

const CATEGORIES_BUDGET = [
  { key: 'epicerie', label: 'Épicerie' },
  { key: 'viandes', label: 'Viandes & Poisson' },
  { key: 'fruits_legumes', label: 'Fruits & Légumes' },
  { key: 'produits_laitiers', label: 'Produits Laitiers' },
  { key: 'boissons', label: 'Boissons' },
  { key: 'hygiene', label: 'Hygiène & Beauté' },
  { key: 'menage', label: 'Ménage' },
];

// ── Composants réutilisables ──────────────────────────────────────────────────

const MenuItem: React.FC<{
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  onPress: () => void;
  color?: string;
  value?: string;
}> = ({ icon, label, onPress, color = '#0B2019', value }) => (
  <TouchableOpacity style={styles.menuItem} onPress={onPress} activeOpacity={0.7}>
    <View style={[styles.menuIconWrap, { backgroundColor: `${color}15` }]}>
      <Ionicons name={icon} size={20} color={color} />
    </View>
    <Text style={[styles.menuLabel, { color }]}>{label}</Text>
    {value ? (
      <Text style={styles.menuValue}>{value}</Text>
    ) : (
      <Ionicons name="chevron-forward" size={16} color="#d1d5db" />
    )}
  </TouchableOpacity>
);

const EditField: React.FC<{
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  keyboardType?: 'default' | 'email-address' | 'phone-pad' | 'decimal-pad';
}> = ({ label, value, onChangeText, placeholder, keyboardType = 'default' }) => (
  <View style={styles.editField}>
    <Text style={styles.editLabel}>{label}</Text>
    <TextInput
      style={styles.editInput}
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor="#8A9A92"
      keyboardType={keyboardType}
      autoCapitalize="none"
    />
  </View>
);

// ── Slider 1-10 custom ────────────────────────────────────────────────────────

const HouseholdSlider: React.FC<{
  value: number;
  onChange: (n: number) => void;
}> = ({ value, onChange }) => (
  <View style={styles.sliderWrap}>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sliderRow}>
      {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
        <TouchableOpacity
          key={n}
          style={[styles.sliderBtn, value === n && styles.sliderBtnActive]}
          onPress={() => onChange(n)}
        >
          <Text style={[styles.sliderNum, value === n && { color: '#fff' }]}>{n}</Text>
          <Text style={[styles.sliderLabel, value === n && { color: '#e0fdf4' }]}>pers.</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
    <Text style={styles.sliderHint}>Foyer de {value} personne{value > 1 ? 's' : ''}</Text>
  </View>
);

// ── Compteur tranche d'âge ────────────────────────────────────────────────────

const AgeCounter: React.FC<{
  label: string;
  icon: string;
  value: number;
  onChange: (n: number) => void;
}> = ({ label, icon, value, onChange }) => (
  <View style={styles.ageRow}>
    <Text style={styles.ageIcon}>{icon}</Text>
    <Text style={styles.ageLabel}>{label}</Text>
    <View style={styles.ageControls}>
      <TouchableOpacity
        style={styles.ageBtn}
        onPress={() => onChange(Math.max(0, value - 1))}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="remove" size={16} color={C.primary} />
      </TouchableOpacity>
      <Text style={styles.ageValue}>{value}</Text>
      <TouchableOpacity
        style={styles.ageBtn}
        onPress={() => onChange(value + 1)}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="add" size={16} color={C.primary} />
      </TouchableOpacity>
    </View>
  </View>
);

// ── Admin Section ─────────────────────────────────────────────────────────────

const SCRAPERS = [
  { slug: 'marjane',   label: 'Marjane',    color: '#C1272D' },
  { slug: 'carrefour', label: 'Carrefour',  color: '#2563eb' },
  { slug: 'labelvie',  label: "Label'Vie",  color: '#0F4C3A' },
  { slug: 'bim',       label: 'BIM',        color: '#ca8a04' },
  { slug: 'kazyon',    label: 'Kazyon',     color: '#ea580c' },
  { slug: 'sopreco',   label: 'Sopreco',    color: '#7c3aed' },
  { slug: 'hmizate',   label: 'Hmizate',    color: '#0891b2' },
];

const AdminSection: React.FC = () => {
  const [triggering, setTriggering] = React.useState<string | null>(null);

  const trigger = async (slug: string) => {
    setTriggering(slug);
    try {
      await AdminAPI.triggerScraper(slug);
      Alert.alert('✅ Scraper lancé', `Le scraper ${slug} a été déclenché.`);
    } catch {
      Alert.alert('Erreur', `Impossible de lancer le scraper ${slug}.`);
    } finally {
      setTriggering(null);
    }
  };

  return (
    <View style={styles.section}>
      <View style={styles.adminHeader}>
        <Ionicons name="shield-checkmark" size={16} color="#7c3aed" />
        <Text style={styles.sectionTitle}>Administration</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.fieldLabel}>Déclencher un scraper</Text>
        <View style={styles.scraperGrid}>
          {SCRAPERS.map((s) => (
            <TouchableOpacity
              key={s.slug}
              style={[styles.scraperBtn, { borderColor: s.color }]}
              onPress={() => trigger(s.slug)}
              disabled={triggering !== null}
              activeOpacity={0.75}
            >
              {triggering === s.slug ? (
                <ActivityIndicator size="small" color={s.color} />
              ) : (
                <Ionicons name="play-circle" size={18} color={s.color} />
              )}
              <Text style={[styles.scraperBtnText, { color: s.color }]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    </View>
  );
};

// ── Écran principal ───────────────────────────────────────────────────────────

const MonProfilScreen: React.FC<Props> = ({ navigation }) => {
  const { user, logout, isGuest } = useAuthStore();
  const queryClient = useQueryClient();

  // Compte
  const [isEditing, setIsEditing] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [city, setCity] = useState(user?.city ?? '');
  const [showCityPicker, setShowCityPicker] = useState(false);

  // Foyer
  const [householdSize, setHouseholdSize] = useState(2);
  const [adultes, setAdultes] = useState(2);
  const [enfants, setEnfants] = useState(0);
  const [seniors, setSeniors] = useState(0);

  // Budget
  const [budgetMensuel, setBudgetMensuel] = useState('');
  const [objectifEconomies, setObjectifEconomies] = useState('');
  const [budgetCategories, setBudgetCategories] = useState<Record<string, string>>({});
  const [showBudgetCats, setShowBudgetCats] = useState(false);

  // Magasins
  const [preferredStores, setPreferredStores] = useState<string[]>([]);
  const [rayonKm, setRayonKm] = useState(10);

  // Avatar
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  // Stats
  const { data: statsData } = useQuery({
    queryKey: ['user-stats'],
    queryFn: ProfileAPI.getStats,
    retry: false,
  });

  useEffect(() => {
    AsyncStorage.getItem(FOYER_KEY).then((raw) => {
      if (raw) {
        try {
          const f = JSON.parse(raw);
          if (f.householdSize)     setHouseholdSize(f.householdSize);
          if (f.adultes != null)   setAdultes(f.adultes);
          if (f.enfants != null)   setEnfants(f.enfants);
          if (f.seniors != null)   setSeniors(f.seniors);
          if (f.budgetMensuel)     setBudgetMensuel(String(f.budgetMensuel));
          if (f.objectifEconomies) setObjectifEconomies(String(f.objectifEconomies));
          if (f.budgetCategories)  setBudgetCategories(f.budgetCategories);
          if (f.preferredStores)   setPreferredStores(f.preferredStores);
          if (f.rayonKm != null)   setRayonKm(f.rayonKm);
        } catch { /* ignore */ }
      }
    });
  }, []);

  const saveFoyer = (patch: Partial<{
    householdSize: number;
    adultes: number;
    enfants: number;
    seniors: number;
    budgetMensuel: string;
    objectifEconomies: string;
    budgetCategories: Record<string, string>;
    preferredStores: string[];
    rayonKm: number;
  }>) => {
    AsyncStorage.getItem(FOYER_KEY).then((raw) => {
      const current = raw ? JSON.parse(raw) : {};
      AsyncStorage.setItem(FOYER_KEY, JSON.stringify({ ...current, ...patch }));
    });
  };

  const updateMutation = useMutation({
    mutationFn: () => AuthAPI.updateMe({ full_name: fullName, phone, city }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] });
      setIsEditing(false);
      Alert.alert('✅ Profil mis à jour', 'Vos informations ont été sauvegardées.');
    },
    onError: () => Alert.alert('Erreur', 'Impossible de mettre à jour le profil.'),
  });

  const handleLogout = () => {
    Alert.alert('Déconnexion', 'Voulez-vous vous déconnecter ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Déconnexion', style: 'destructive', onPress: () => logout() },
    ]);
  };

  const handlePickAvatar = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission requise', "Autorisez l'accès à la galerie.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      try {
        setUploadingAvatar(true);
        await ProfileAPI.uploadAvatar(result.assets[0].uri);
        queryClient.invalidateQueries({ queryKey: ['me'] });
        Alert.alert('✅ Photo mise à jour');
      } catch {
        Alert.alert('Erreur', 'Impossible de mettre à jour la photo.');
      } finally {
        setUploadingAvatar(false);
      }
    }
  };

  const initials = (user?.full_name ?? user?.username ?? '?')
    .split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();

  // Économies cible validées (%) — indicateur
  const budgetNum = parseFloat(budgetMensuel) || 0;
  const objectifNum = parseFloat(objectifEconomies) || 0;
  const pctObjectif = budgetNum > 0 ? Math.min(100, Math.round((objectifNum / budgetNum) * 100)) : 0;

  // Mode invité : écran simplifié
  if (isGuest) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <View style={styles.guestContainer}>
          <Text style={styles.guestEmoji}>👋</Text>
          <Text style={styles.guestTitle}>Mode Invité</Text>
          <Text style={styles.guestSubtitle}>
            Vous naviguez sans compte.{'\n'}
            Connectez-vous pour accéder à toutes les fonctionnalités.
          </Text>
          <TouchableOpacity style={styles.guestLoginBtn} onPress={() => logout()} activeOpacity={0.85}>
            <Text style={styles.guestLoginBtnText}>Se connecter / Créer un compte</Text>
          </TouchableOpacity>
          <Text style={styles.guestFeatures}>
            ✓ Comparer les prix{'\n'}
            ✓ Voir les promotions{'\n'}
            ✓ Trouver les magasins proches{'\n'}
            ✗ Scanner des tickets (connexion requise){'\n'}
            ✗ Listes de courses (connexion requise)
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>

        {/* Avatar + infos */}
        <View style={styles.profileHeader}>
          <Pressable onPress={handlePickAvatar} style={styles.avatarContainer}>
            {(user as any)?.avatar_url ? (
              <Image source={{ uri: (user as any).avatar_url }} style={styles.avatarImg} />
            ) : (
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{initials}</Text>
              </View>
            )}
            <View style={styles.avatarEditBadge}>
              {uploadingAvatar
                ? <ActivityIndicator size="small" color="#0C3F30" />
                : <Ionicons name="camera" size={14} color="#0C3F30" />
              }
            </View>
          </Pressable>
          <Text style={styles.displayName}>{user?.full_name ?? user?.username}</Text>
          <Text style={styles.email}>{user?.email}</Text>
          {user?.city && (
            <View style={styles.cityRow}>
              <Ionicons name="location-outline" size={14} color="#4A5B53" />
              <Text style={styles.cityText}>{user.city}</Text>
            </View>
          )}
          <TouchableOpacity style={styles.editProfileBtn} onPress={() => setIsEditing(!isEditing)}>
            <Ionicons name={isEditing ? 'close' : 'pencil'} size={16} color={C.primary} />
            <Text style={styles.editProfileBtnText}>{isEditing ? 'Annuler' : 'Modifier'}</Text>
          </TouchableOpacity>
        </View>

        {/* Formulaire édition */}
        {isEditing && (
          <View style={styles.editForm}>
            <Text style={styles.sectionTitle}>Modifier le profil</Text>
            <EditField label="Nom complet" value={fullName} onChangeText={setFullName} placeholder="Votre nom" />
            <EditField label="Téléphone" value={phone} onChangeText={setPhone} placeholder="+212 6XX XXX XXX" keyboardType="phone-pad" />
            <View style={styles.editField}>
              <Text style={styles.editLabel}>Ville</Text>
              <TouchableOpacity
                style={[styles.editInput, styles.editInputRow]}
                onPress={() => setShowCityPicker(!showCityPicker)}
              >
                <Text style={{ color: city ? '#0B2019' : '#8A9A92', fontSize: 15, flex: 1 }}>
                  {city || 'Sélectionnez votre ville'}
                </Text>
                <Ionicons name={showCityPicker ? 'chevron-up' : 'chevron-down'} size={16} color="#8A9A92" />
              </TouchableOpacity>
              {showCityPicker && (
                <View style={styles.cityDropdown}>
                  <ScrollView nestedScrollEnabled style={{ maxHeight: 180 }}>
                    {MOROCCAN_CITIES.map((c) => (
                      <TouchableOpacity
                        key={c}
                        style={[styles.cityOption, city === c && styles.cityOptionActive]}
                        onPress={() => { setCity(c); setShowCityPicker(false); }}
                      >
                        <Text style={[styles.cityOptionText, city === c && { color: C.primary, fontWeight: '700' }]}>{c}</Text>
                        {city === c && <Ionicons name="checkmark" size={16} color={C.primary} />}
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>
              )}
            </View>
            <TouchableOpacity
              style={[styles.saveBtn, updateMutation.isPending && { opacity: 0.7 }]}
              onPress={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending
                ? <ActivityIndicator size="small" color="#fff" />
                : <Text style={styles.saveBtnText}>Enregistrer les modifications</Text>
              }
            </TouchableOpacity>
          </View>
        )}

        {/* ── Mon foyer ─────────────────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Mon foyer</Text>
          <View style={styles.card}>

            {/* Slider 1-10 */}
            <Text style={styles.fieldLabel}>Nombre de personnes</Text>
            <HouseholdSlider
              value={householdSize}
              onChange={(n) => { setHouseholdSize(n); saveFoyer({ householdSize: n }); }}
            />

            {/* Tranches d'âge */}
            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Tranches d'âge</Text>
            <View style={styles.ageCats}>
              <AgeCounter
                label="Adultes" icon="🧑" value={adultes}
                onChange={(n) => { setAdultes(n); saveFoyer({ adultes: n }); }}
              />
              <AgeCounter
                label="Enfants" icon="🧒" value={enfants}
                onChange={(n) => { setEnfants(n); saveFoyer({ enfants: n }); }}
              />
              <AgeCounter
                label="Seniors" icon="👴" value={seniors}
                onChange={(n) => { setSeniors(n); saveFoyer({ seniors: n }); }}
              />
            </View>

            {/* Magasins préférés */}
            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Magasins préférés</Text>
            <View style={styles.storeGrid}>
              {STORE_OPTIONS.map((s) => {
                const isActive = preferredStores.includes(s.slug);
                return (
                  <TouchableOpacity
                    key={s.slug}
                    style={[styles.storeChip, isActive && styles.storeChipActive]}
                    onPress={() => {
                      const next = isActive
                        ? preferredStores.filter((x) => x !== s.slug)
                        : [...preferredStores, s.slug];
                      setPreferredStores(next);
                      saveFoyer({ preferredStores: next });
                    }}
                  >
                    <Text style={[styles.storeChipText, isActive && { color: C.primary }]}>{s.name}</Text>
                    {isActive && <Ionicons name="checkmark-circle" size={14} color={C.primary} />}
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Rayon de recherche */}
            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Rayon de recherche magasins</Text>
            <View style={styles.rayonRow}>
              {[2, 5, 10, 20, 50].map((km) => (
                <TouchableOpacity
                  key={km}
                  style={[styles.rayonBtn, rayonKm === km && styles.rayonBtnActive]}
                  onPress={() => { setRayonKm(km); saveFoyer({ rayonKm: km }); }}
                >
                  <Text style={[styles.rayonBtnText, rayonKm === km && styles.rayonBtnTextActive]}>
                    {km} km
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={styles.infoRow}>
              <Ionicons name="information-circle-outline" size={14} color="#4A5B53" />
              <Text style={styles.infoText}>
                Ces données personnalisent vos listes IA et recommandations.
              </Text>
            </View>
          </View>
        </View>

        {/* ── Mon budget ────────────────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Mon budget</Text>
          <View style={styles.card}>

            {/* Budget mensuel global */}
            <Text style={styles.fieldLabel}>Budget mensuel total</Text>
            <View style={styles.budgetRow}>
              <TextInput
                style={styles.budgetInput}
                placeholder="Ex : 3000"
                placeholderTextColor="#8A9A92"
                value={budgetMensuel}
                onChangeText={(v) => { setBudgetMensuel(v); saveFoyer({ budgetMensuel: v }); }}
                keyboardType="decimal-pad"
              />
              <Text style={styles.budgetCurrency}>MAD / mois</Text>
            </View>

            {/* Objectif économies */}
            <Text style={[styles.fieldLabel, { marginTop: 14 }]}>Objectif d'économies mensuel</Text>
            <View style={styles.budgetRow}>
              <TextInput
                style={styles.budgetInput}
                placeholder="Ex : 400"
                placeholderTextColor="#8A9A92"
                value={objectifEconomies}
                onChangeText={(v) => { setObjectifEconomies(v); saveFoyer({ objectifEconomies: v }); }}
                keyboardType="decimal-pad"
              />
              <Text style={styles.budgetCurrency}>MAD / mois</Text>
            </View>
            {objectifNum > 0 && budgetNum > 0 && (
              <View style={styles.objectifBar}>
                <View style={styles.objectifTrack}>
                  <View style={[styles.objectifFill, { width: `${pctObjectif}%` as any }]} />
                </View>
                <Text style={styles.objectifPct}>
                  Objectif : {pctObjectif}% du budget ({objectifNum.toFixed(0)} MAD)
                </Text>
              </View>
            )}

            {/* Budget par catégorie */}
            <TouchableOpacity
              style={styles.catsBudgetToggle}
              onPress={() => setShowBudgetCats((v) => !v)}
            >
              <Text style={styles.fieldLabel}>Budget par catégorie</Text>
              <Ionicons
                name={showBudgetCats ? 'chevron-up' : 'chevron-down'}
                size={16}
                color="#8A9A92"
              />
            </TouchableOpacity>

            {showBudgetCats && (
              <View style={styles.catsBudgetList}>
                {CATEGORIES_BUDGET.map((cat) => (
                  <View key={cat.key} style={styles.catBudgetRow}>
                    <Text style={styles.catBudgetLabel}>{cat.label}</Text>
                    <View style={styles.catBudgetInput}>
                      <TextInput
                        style={styles.catBudgetField}
                        placeholder="—"
                        placeholderTextColor="#d1d5db"
                        value={budgetCategories[cat.key] ?? ''}
                        onChangeText={(v) => {
                          const next = { ...budgetCategories, [cat.key]: v };
                          setBudgetCategories(next);
                          saveFoyer({ budgetCategories: next });
                        }}
                        keyboardType="decimal-pad"
                      />
                      <Text style={styles.catBudgetUnit}>MAD</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>
        </View>

        {/* ── Mon compte ────────────────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Mon compte</Text>
          <View style={styles.card}>
            <MenuItem icon="receipt-outline" label="Mes tickets scannés" onPress={() => navigation.navigate('MesScans')} />
            <View style={styles.separator} />
            <MenuItem icon="notifications-outline" label="Mes alertes prix" onPress={() => navigation.navigate('MesAlertes')} />
            <View style={styles.separator} />
            <MenuItem icon="settings-outline" label="Préférences" onPress={() => navigation.navigate('Parametres')} />
            <View style={styles.separator} />
            <MenuItem icon="person-outline" label="Identifiant" onPress={() => {}} value={`@${user?.username}`} />
          </View>
        </View>

        {/* ── Statistiques ──────────────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Statistiques</Text>
          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Ionicons name="scan-outline" size={24} color={C.primary} />
              <Text style={styles.statValue}>{statsData?.scans ?? '—'}</Text>
              <Text style={styles.statLabel}>Scans</Text>
            </View>
            <View style={styles.statCard}>
              <Ionicons name="list-outline" size={24} color="#E8A020" />
              <Text style={styles.statValue}>{statsData?.listes ?? '—'}</Text>
              <Text style={styles.statLabel}>Listes</Text>
            </View>
            <View style={styles.statCard}>
              <Ionicons name="trending-down-outline" size={24} color="#3b82f6" />
              <Text style={styles.statValue}>
                {statsData?.economies != null ? `${statsData.economies} MAD` : '—'}
              </Text>
              <Text style={styles.statLabel}>Économies</Text>
            </View>
          </View>
        </View>

        {/* ── Administration (superuser seulement) ─────────────────────── */}
        {(user as any)?.is_superuser && (
          <AdminSection />
        )}

        {/* Déconnexion */}
        <View style={styles.section}>
          <View style={styles.card}>
            <MenuItem icon="log-out-outline" label="Déconnexion" onPress={handleLogout} color="#ef4444" />
          </View>
        </View>

        <Text style={styles.version}>PrixMaroc v1.0.0 — © 2025</Text>
      </ScrollView>
    </SafeAreaView>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#E9F0E6' },
  content: { paddingBottom: 40 },

  profileHeader: {
    alignItems: 'center', backgroundColor: '#0C3F30', paddingTop: 28, paddingBottom: 32,
  },
  avatarContainer: { position: 'relative', marginBottom: 14 },
  avatar: {
    width: 86, height: 86, borderRadius: 43,
    backgroundColor: 'rgba(255,255,255,0.25)', alignItems: 'center', justifyContent: 'center',
    borderWidth: 3, borderColor: 'rgba(255,255,255,0.5)',
  },
  avatarImg: { width: 86, height: 86, borderRadius: 43 },
  avatarText: { fontSize: 30, fontWeight: '800', color: '#fff' },
  avatarEditBadge: {
    position: 'absolute', bottom: 0, right: 0,
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: '#0C3F30',
  },
  displayName: { fontSize: 21, fontWeight: '800', color: '#ffffff', marginBottom: 4 },
  email: { fontSize: 14, color: 'rgba(255,255,255,0.75)', marginBottom: 6 },
  cityRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 14 },
  cityText: { fontSize: 13, color: 'rgba(255,255,255,0.75)' },
  editProfileBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.6)',
    borderRadius: 12, paddingHorizontal: 16, paddingVertical: 8,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  editProfileBtnText: { color: '#ffffff', fontWeight: '700', fontSize: 13 },

  editForm: {
    backgroundColor: '#fff', margin: 16, borderRadius: 16, padding: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 3,
  },
  editField: { marginBottom: 14 },
  editLabel: { fontSize: 13, fontWeight: '600', color: '#4A5B53', marginBottom: 6 },
  editInput: { backgroundColor: '#E9F0E6', borderRadius: 10, padding: 12, fontSize: 15, color: '#0B2019' },
  editInputRow: { flexDirection: 'row', alignItems: 'center' },
  cityDropdown: {
    backgroundColor: '#fff', borderRadius: 10, borderWidth: 1, borderColor: '#E2E9DF', marginTop: 4, overflow: 'hidden',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 6, elevation: 4,
  },
  cityOption: { paddingVertical: 10, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#E9F0E6' },
  cityOptionActive: { backgroundColor: '#EEF6F1' },
  cityOptionText: { fontSize: 14, color: '#0B2019' },

  section: { paddingHorizontal: 16, marginTop: 16 },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: '#8A9A92', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 },
  card: {
    backgroundColor: '#fff', borderRadius: 16, overflow: 'hidden',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.07, shadowRadius: 8, elevation: 3, padding: 16,
  },
  fieldLabel: { fontSize: 14, fontWeight: '600', color: '#0B2019', marginBottom: 10 },

  // Slider 1-10
  sliderWrap: { gap: 8 },
  sliderRow: { gap: 6, paddingVertical: 2 },
  sliderBtn: {
    alignItems: 'center', justifyContent: 'center',
    width: 52, paddingVertical: 10,
    backgroundColor: '#F2F6F0', borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E9DF',
  },
  sliderBtnActive: { borderColor: C.primary, backgroundColor: C.primary },
  sliderNum: { fontSize: 17, fontWeight: '800', color: '#3C4F47' },
  sliderLabel: { fontSize: 8, color: '#8A9A92', marginTop: 1 },
  sliderHint: { fontSize: 12, color: '#4A5B53', fontStyle: 'italic' },

  // Tranches d'âge
  ageCats: { gap: 8 },
  ageRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  ageIcon: { fontSize: 20 },
  ageLabel: { flex: 1, fontSize: 14, color: '#374151', fontWeight: '500' },
  ageControls: { flexDirection: 'row', alignItems: 'center', gap: 0, backgroundColor: '#E9F0E6', borderRadius: 10, overflow: 'hidden' },
  ageBtn: { padding: 10, paddingHorizontal: 14 },
  ageValue: { fontSize: 17, fontWeight: '800', color: '#0B2019', minWidth: 28, textAlign: 'center' },

  // Budget
  budgetRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#F2F6F0', borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E9DF', paddingHorizontal: 12,
  },
  budgetInput: { flex: 1, fontSize: 16, color: '#0B2019', paddingVertical: 12 },
  budgetCurrency: { fontSize: 13, fontWeight: '600', color: '#4A5B53' },

  // Objectif économies
  objectifBar: { marginTop: 8, gap: 4 },
  objectifTrack: { height: 6, backgroundColor: '#E2E9DF', borderRadius: 3, overflow: 'hidden' },
  objectifFill: { height: 6, backgroundColor: '#1E6B4F', borderRadius: 3 },
  objectifPct: { fontSize: 12, color: '#0F4C3A', fontWeight: '600' },

  // Budget par catégorie
  catsBudgetToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 14 },
  catsBudgetList: { marginTop: 8, gap: 8 },
  catBudgetRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  catBudgetLabel: { flex: 1, fontSize: 13, color: '#374151' },
  catBudgetInput: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#E9F0E6', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  catBudgetField: { width: 64, fontSize: 14, fontWeight: '700', color: '#0B2019', textAlign: 'right' },
  catBudgetUnit: { fontSize: 12, color: '#4A5B53', marginLeft: 4 },

  // Magasins
  storeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  storeChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: '#E9F0E6', borderRadius: 20, borderWidth: 1.5, borderColor: '#E2E9DF' },
  storeChipActive: { borderColor: C.primary, backgroundColor: '#EEF6F1' },
  storeChipText: { fontSize: 13, fontWeight: '600', color: '#3C4F47' },

  infoRow: { flexDirection: 'row', gap: 6, marginTop: 12, backgroundColor: '#f0f9ff', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: '#bae6fd' },
  infoText: { flex: 1, fontSize: 12, color: '#0369a1', lineHeight: 16 },

  menuItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 0, gap: 12 },
  menuIconWrap: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  menuLabel: { flex: 1, fontSize: 15, fontWeight: '600' },
  menuValue: { fontSize: 14, color: '#8A9A92' },
  separator: { height: 1, backgroundColor: '#E9F0E6', marginLeft: 48 },

  saveBtn: { backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 4 },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  statsGrid: { flexDirection: 'row', gap: 10 },
  statCard: { flex: 1, backgroundColor: '#fff', borderRadius: 14, padding: 16, alignItems: 'center', gap: 6, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 4, elevation: 2 },
  statValue: { fontSize: 20, fontWeight: '800', color: '#0B2019' },
  statLabel: { fontSize: 12, color: '#8A9A92' },
  version: { textAlign: 'center', fontSize: 12, color: '#d1d5db', marginTop: 24 },

  // Guest mode
  guestContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32 },
  guestEmoji: { fontSize: 64, marginBottom: 16 },
  guestTitle: { fontSize: 24, fontWeight: '800', color: '#0B2019', marginBottom: 10 },
  guestSubtitle: { fontSize: 15, color: '#4A5B53', textAlign: 'center', lineHeight: 22, marginBottom: 28 },
  guestLoginBtn: { backgroundColor: '#0C3F30', borderRadius: 14, paddingVertical: 16, paddingHorizontal: 32, marginBottom: 28 },
  guestLoginBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  guestFeatures: { fontSize: 14, color: '#3C4F47', lineHeight: 26, textAlign: 'left' },

  // Rayon de recherche
  rayonRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  rayonBtn: { paddingHorizontal: 16, paddingVertical: 9, borderRadius: 20, borderWidth: 1.5, borderColor: '#E2E9DF', backgroundColor: '#F2F6F0' },
  rayonBtnActive: { borderColor: C.primary, backgroundColor: '#EEF6F1' },
  rayonBtnText: { fontSize: 13, fontWeight: '600', color: '#3C4F47' },
  rayonBtnTextActive: { color: C.primary },

  // Admin section
  adminHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  scraperGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 4 },
  scraperBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, backgroundColor: '#fafafa', minWidth: '45%' as any },
  scraperBtnText: { fontSize: 13, fontWeight: '700' },
});

export default MonProfilScreen;
