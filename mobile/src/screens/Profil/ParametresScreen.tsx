import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  I18nManager,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { C } from '@constants/colors';

export const PREFS_KEY = 'prixmaroc:preferences';

export interface UserPreferences {
  langue: 'fr' | 'ar' | 'darija';
  regime: 'standard' | 'halal' | 'vegetarien' | 'sansgluten';
  notifPromo: boolean;
  notifListe: boolean;
  notifEconomies: boolean;
  rayonMax: number;
}

export const DEFAULT_PREFS: UserPreferences = {
  langue: 'fr',
  regime: 'halal',
  notifPromo: true,
  notifListe: true,
  notifEconomies: true,
  rayonMax: 10,
};

export async function loadPreferences(): Promise<UserPreferences> {
  try {
    const raw = await AsyncStorage.getItem(PREFS_KEY);
    if (raw) return { ...DEFAULT_PREFS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return DEFAULT_PREFS;
}

export async function savePreferences(prefs: UserPreferences): Promise<void> {
  await AsyncStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

// ── Option selector ────────────────────────────────────────────────────────────

function OptionSelector<T extends string>({
  label,
  options,
  value,
  onSelect,
}: {
  label: string;
  options: { value: T; label: string; icon?: string }[];
  value: T;
  onSelect: (v: T) => void;
}) {
  return (
    <View style={styles.optGroup}>
      <Text style={styles.optLabel}>{label}</Text>
      <View style={styles.optRow}>
        {options.map((o) => (
          <TouchableOpacity
            key={o.value}
            style={[styles.optBtn, value === o.value && styles.optBtnActive]}
            onPress={() => onSelect(o.value)}
          >
            {o.icon ? <Text style={styles.optIcon}>{o.icon}</Text> : null}
            <Text style={[styles.optBtnText, value === o.value && styles.optBtnTextActive]}>
              {o.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ── Toggle notification ────────────────────────────────────────────────────────

function NotifToggle({
  icon,
  label,
  description,
  value,
  onToggle,
}: {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  description: string;
  value: boolean;
  onToggle: (v: boolean) => void;
}) {
  return (
    <View style={styles.notifRow}>
      <View style={styles.notifIconWrap}>
        <Ionicons name={icon} size={20} color={C.primary} />
      </View>
      <View style={styles.notifInfo}>
        <Text style={styles.notifLabel}>{label}</Text>
        <Text style={styles.notifDesc}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ false: '#E2E9DF', true: `${C.primary}80` }}
        thumbColor={value ? C.primary : '#E9F0E6'}
      />
    </View>
  );
}

// ── Screen ─────────────────────────────────────────────────────────────────────

const ParametresScreen: React.FC = () => {
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadPreferences().then(setPrefs);
  }, []);

  const update = (partial: Partial<UserPreferences>) => {
    setPrefs((p) => ({ ...p, ...partial }));
    setSaved(false);
  };

  const handleLangueChange = (lang: UserPreferences['langue']) => {
    const wasAr = prefs.langue === 'ar';
    const isAr = lang === 'ar';
    update({ langue: lang });

    if (isAr !== wasAr) {
      // RTL switch : informe l'utilisateur qu'un redémarrage est nécessaire
      Alert.alert(
        isAr ? 'Mode arabe (RTL)' : 'Mode LTR',
        isAr
          ? "L'affichage passera en arabe (droite à gauche) au prochain démarrage. Enregistrez puis relancez l'application."
          : "L'affichage repassera en mode gauche à droite au prochain démarrage. Enregistrez puis relancez l'application.",
        [
          { text: 'Annuler', style: 'cancel', onPress: () => update({ langue: prefs.langue }) },
          {
            text: 'Confirmer',
            onPress: async () => {
              const newPrefs = { ...prefs, langue: lang };
              await savePreferences(newPrefs);
              I18nManager.forceRTL(isAr);
              setSaved(true);
            },
          },
        ],
      );
    }
  };

  const handleSave = async () => {
    await savePreferences(prefs);
    // Appliquer RTL selon la langue enregistrée
    I18nManager.forceRTL(prefs.langue === 'ar');
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>

        {/* Langue */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Langue</Text>
          <View style={styles.card}>
            <OptionSelector
              label="Interface de l'application"
              options={[
                { value: 'fr', label: 'Français', icon: '🇫🇷' },
                { value: 'darija', label: 'Darija', icon: '🇲🇦' },
                { value: 'ar', label: 'العربية', icon: '🌙' },
              ]}
              value={prefs.langue}
              onSelect={(v) => handleLangueChange(v as UserPreferences['langue'])}
            />
            {prefs.langue === 'ar' && (
              <View style={styles.rtlHint}>
                <Ionicons name="information-circle-outline" size={16} color="#0284c7" />
                <Text style={styles.rtlHintText}>
                  Le mode arabe (RTL) sera actif au prochain démarrage
                </Text>
              </View>
            )}
          </View>
        </View>

        {/* Régime alimentaire */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Régime alimentaire</Text>
          <View style={styles.card}>
            <OptionSelector
              label="Préférence pour les recommandations IA"
              options={[
                { value: 'standard', label: 'Standard', icon: '🍽️' },
                { value: 'halal', label: 'Halal', icon: '☪️' },
                { value: 'vegetarien', label: 'Végé', icon: '🥦' },
                { value: 'sansgluten', label: 'Sans gluten', icon: '🌾' },
              ]}
              value={prefs.regime}
              onSelect={(v) => update({ regime: v })}
            />
          </View>
        </View>

        {/* Rayon de recherche */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Rayon de recherche</Text>
          <View style={styles.card}>
            <Text style={styles.optLabel}>Distance maximale des magasins</Text>
            <View style={styles.rayonRow}>
              {([3, 5, 10, 15, 20] as const).map((km) => (
                <TouchableOpacity
                  key={km}
                  style={[styles.rayonBtn, prefs.rayonMax === km && styles.rayonBtnActive]}
                  onPress={() => update({ rayonMax: km })}
                >
                  <Text style={[styles.rayonBtnText, prefs.rayonMax === km && styles.rayonBtnTextActive]}>
                    {km} km
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        {/* Notifications */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notifications</Text>
          <View style={styles.card}>
            <NotifToggle
              icon="pricetag-outline"
              label="Alertes promotions"
              description="Promos sur vos produits habituels"
              value={prefs.notifPromo}
              onToggle={(v) => update({ notifPromo: v })}
            />
            <View style={styles.divider} />
            <NotifToggle
              icon="list-outline"
              label="Rappel de liste"
              description="Chaque semaine le dimanche matin"
              value={prefs.notifListe}
              onToggle={(v) => update({ notifListe: v })}
            />
            <View style={styles.divider} />
            <NotifToggle
              icon="trending-down-outline"
              label="Récap économies"
              description="Votre bilan hebdomadaire le lundi"
              value={prefs.notifEconomies}
              onToggle={(v) => update({ notifEconomies: v })}
            />
          </View>
        </View>

        {/* Sauvegarder */}
        <TouchableOpacity
          style={[styles.saveBtn, saved && styles.saveBtnDone]}
          onPress={handleSave}
        >
          <Ionicons name={saved ? 'checkmark-circle' : 'save-outline'} size={20} color="#fff" />
          <Text style={styles.saveBtnText}>
            {saved ? 'Préférences enregistrées !' : 'Enregistrer les préférences'}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F2F6F0' },
  content: { padding: 16, paddingBottom: 40 },
  section: { marginBottom: 16 },
  sectionTitle: {
    fontSize: 13, fontWeight: '700', color: '#8A9A92',
    textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8,
  },
  card: {
    backgroundColor: '#fff', borderRadius: 16, padding: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 4, elevation: 2, gap: 12,
  },
  optGroup: { gap: 8 },
  optLabel: { fontSize: 14, fontWeight: '600', color: '#0B2019' },
  optRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  optBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E9DF',
    backgroundColor: '#F2F6F0',
  },
  optBtnActive: { borderColor: C.primary, backgroundColor: '#EEF6F1' },
  optIcon: { fontSize: 15 },
  optBtnText: { fontSize: 13, fontWeight: '600', color: '#4A5B53' },
  optBtnTextActive: { color: C.primary },
  rayonRow: { flexDirection: 'row', gap: 6 },
  rayonBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 8,
    borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E9DF',
    backgroundColor: '#F2F6F0',
  },
  rayonBtnActive: { borderColor: C.primary, backgroundColor: '#EEF6F1' },
  rayonBtnText: { fontSize: 12, fontWeight: '700', color: '#4A5B53' },
  rayonBtnTextActive: { color: C.primary },
  notifRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  notifIconWrap: {
    width: 40, height: 40, borderRadius: 10,
    backgroundColor: '#EEF6F1', alignItems: 'center', justifyContent: 'center',
  },
  notifInfo: { flex: 1 },
  notifLabel: { fontSize: 15, fontWeight: '600', color: '#0B2019' },
  notifDesc: { fontSize: 12, color: '#8A9A92', marginTop: 2 },
  divider: { height: 1, backgroundColor: '#E9F0E6' },
  rtlHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#e0f2fe',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#bae6fd',
  },
  rtlHintText: { flex: 1, fontSize: 12, color: '#0284c7', fontWeight: '500' },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 10, backgroundColor: C.primary, borderRadius: 14, paddingVertical: 16,
    shadowColor: C.primary, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 8, elevation: 6,
  },
  saveBtnDone: { backgroundColor: '#1E6B4F' },
  saveBtnText: { color: '#fff', fontWeight: '800', fontSize: 16 },
});

export default ParametresScreen;
