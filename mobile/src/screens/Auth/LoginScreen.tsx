import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  Modal,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useAuthStore } from '@store/authStore';
import { API_URL_STORAGE_KEY, setApiUrl } from '@services/api';
import { API_BASE_URL } from '@constants/index';

type RootStackParamList = {
  Login: undefined;
  Register: undefined;
};

type Props = NativeStackScreenProps<RootStackParamList, 'Login'>;

const LoginScreen: React.FC<Props> = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [urlInput, setUrlInput] = useState('');

  const { login, loginAsGuest, isLoading, error, clearError } = useAuthStore();

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      return;
    }
    clearError();
    await login(email.trim(), password);
  };

  const handleEmailChange = (val: string) => {
    if (error) clearError();
    setEmail(val);
  };

  const handlePasswordChange = (val: string) => {
    if (error) clearError();
    setPassword(val);
  };

  const openUrlModal = async () => {
    const stored = await AsyncStorage.getItem(API_URL_STORAGE_KEY);
    setUrlInput(stored || API_BASE_URL);
    setShowUrlModal(true);
  };

  const saveUrl = async () => {
    const url = urlInput.trim().replace(/\/$/, '');
    if (!url.startsWith('http')) {
      Alert.alert('URL invalide', "L'URL doit commencer par http:// ou https://");
      return;
    }
    await setApiUrl(url);
    setShowUrlModal(false);
    Alert.alert('URL mise à jour', `Backend : ${url}`);
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor="#0C3F30" />

      {/* ── Green background layers ─────────────────────────────────────── */}
      <View style={styles.bgTop} />
      <View style={styles.bgBottom} />

      {/* ── URL config button (top-right) ──────────────────────────────── */}
      <TouchableOpacity style={styles.urlConfigBtn} onPress={openUrlModal} activeOpacity={0.7}>
        <Text style={styles.urlConfigIcon}>⚙️</Text>
      </TouchableOpacity>

      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardAvoid}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* ── Logo section ──────────────────────────────────────────────── */}
            <View style={styles.logoSection}>
              <View style={styles.logoIconWrap}>
                <Text style={styles.logoEmoji}>🏷️</Text>
              </View>
              <Text style={styles.logoText}>PrixMaroc</Text>
              <Text style={styles.logoSubtitle}>Économisez intelligemment</Text>
            </View>

            {/* ── White card ────────────────────────────────────────────────── */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Connexion</Text>

              {/* Error banner */}
              {error ? (
                <View style={styles.errorBox}>
                  <Text style={styles.errorIcon}>⚠️</Text>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Email input */}
              <View style={styles.inputGroup}>
                <View
                  style={[
                    styles.inputWrap,
                    emailFocused && styles.inputWrapFocused,
                    error ? styles.inputWrapError : null,
                  ]}
                >
                  <Text style={styles.inputIcon}>📧</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="votre@email.com"
                    placeholderTextColor="#b0b8c4"
                    value={email}
                    onChangeText={handleEmailChange}
                    autoCapitalize="none"
                    keyboardType="email-address"
                    editable={!isLoading}
                    onFocus={() => setEmailFocused(true)}
                    onBlur={() => setEmailFocused(false)}
                    returnKeyType="next"
                  />
                </View>
              </View>

              {/* Password input */}
              <View style={styles.inputGroup}>
                <View
                  style={[
                    styles.inputWrap,
                    passwordFocused && styles.inputWrapFocused,
                    error ? styles.inputWrapError : null,
                  ]}
                >
                  <Text style={styles.inputIcon}>🔒</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="••••••••"
                    placeholderTextColor="#b0b8c4"
                    value={password}
                    onChangeText={handlePasswordChange}
                    secureTextEntry
                    editable={!isLoading}
                    onFocus={() => setPasswordFocused(true)}
                    onBlur={() => setPasswordFocused(false)}
                    returnKeyType="done"
                    onSubmitEditing={handleLogin}
                  />
                </View>
              </View>

              {/* Login button */}
              <TouchableOpacity
                style={[
                  styles.button,
                  isLoading && styles.buttonDisabled,
                  (!email.trim() || !password.trim()) && !isLoading
                    ? styles.buttonInactive
                    : null,
                ]}
                onPress={handleLogin}
                disabled={isLoading}
                activeOpacity={0.85}
              >
                {isLoading ? (
                  <ActivityIndicator color="#ffffff" size="small" />
                ) : (
                  <Text style={styles.buttonText}>Se connecter</Text>
                )}
              </TouchableOpacity>

              {/* Guest mode */}
              <TouchableOpacity
                style={styles.guestBtn}
                onPress={() => loginAsGuest()}
                activeOpacity={0.75}
              >
                <Text style={styles.guestBtnText}>Continuer sans compte →</Text>
              </TouchableOpacity>

              {/* Register link */}
              <View style={styles.registerRow}>
                <Text style={styles.registerText}>Pas encore de compte? </Text>
                <TouchableOpacity
                  onPress={() => navigation.navigate('Register')}
                  activeOpacity={0.7}
                >
                  <Text style={styles.registerLink}>S'inscrire</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* ── URL Modal ─────────────────────────────────────────────────── */}
            <Modal visible={showUrlModal} transparent animationType="fade">
              <View style={styles.modalOverlay}>
                <View style={styles.modalCard}>
                  <Text style={styles.modalTitle}>🌐 URL du serveur</Text>
                  <Text style={styles.modalHint}>
                    Entrez l'URL Cloudflare ou l'IP du backend
                  </Text>
                  <TextInput
                    style={styles.modalInput}
                    value={urlInput}
                    onChangeText={setUrlInput}
                    placeholder="https://xxx.trycloudflare.com"
                    placeholderTextColor="#8A9A92"
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                  />
                  <View style={styles.modalActions}>
                    <TouchableOpacity
                      style={styles.modalCancel}
                      onPress={() => setShowUrlModal(false)}
                    >
                      <Text style={styles.modalCancelText}>Annuler</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.modalSave} onPress={saveUrl}>
                      <Text style={styles.modalSaveText}>Enregistrer</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
            </Modal>

            {/* ── Bottom tagline ────────────────────────────────────────────── */}
            <View style={styles.taglineWrap}>
              <Text style={styles.tagline}>
                50 000+ Marocains économisent avec PrixMaroc
              </Text>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
};

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },

  // Background layers to simulate a green gradient
  bgTop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#0C3F30',
    bottom: '45%',
  },
  bgBottom: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#EEF6F1',
    top: '55%',
  },

  safeArea: {
    flex: 1,
  },
  keyboardAvoid: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingBottom: 40,
  },

  // Logo section
  logoSection: {
    alignItems: 'center',
    paddingTop: 32,
    paddingBottom: 36,
  },
  logoIconWrap: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  logoEmoji: {
    fontSize: 40,
  },
  logoText: {
    fontSize: 38,
    fontWeight: '800',
    color: '#ffffff',
    letterSpacing: -0.5,
    marginBottom: 6,
  },
  logoSubtitle: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.82)',
    fontWeight: '400',
    letterSpacing: 0.2,
  },

  // Card
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 22,
    padding: 28,
    shadowColor: '#0f4c26',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 10,
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0B2019',
    marginBottom: 22,
    letterSpacing: -0.3,
  },

  // Error
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#fef2f2',
    borderRadius: 10,
    padding: 12,
    marginBottom: 18,
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
    gap: 8,
  },
  errorIcon: {
    fontSize: 14,
    marginTop: 1,
  },
  errorText: {
    flex: 1,
    color: '#b91c1c',
    fontSize: 14,
    lineHeight: 20,
  },

  // Inputs
  inputGroup: {
    marginBottom: 14,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: '#E2E9DF',
    borderRadius: 14,
    backgroundColor: '#F2F6F0',
    paddingHorizontal: 14,
    paddingVertical: 4,
    gap: 8,
  },
  inputWrapFocused: {
    borderColor: '#0F4C3A',
    backgroundColor: '#EEF6F1',
  },
  inputWrapError: {
    borderColor: '#fca5a5',
    backgroundColor: '#fff8f8',
  },
  inputIcon: {
    fontSize: 18,
    width: 24,
    textAlign: 'center',
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: '#0B2019',
    paddingVertical: 13,
  },

  // Button
  button: {
    backgroundColor: '#0F4C3A',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 6,
    shadowColor: '#0F4C3A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  buttonDisabled: {
    backgroundColor: '#3D8F6E',
    shadowOpacity: 0.1,
    elevation: 2,
  },
  buttonInactive: {
    backgroundColor: '#6FB294',
    shadowOpacity: 0.08,
    elevation: 1,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.2,
  },

  // Register row
  registerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 20,
  },
  registerText: {
    color: '#4A5B53',
    fontSize: 15,
  },
  registerLink: {
    color: '#0F4C3A',
    fontSize: 15,
    fontWeight: '700',
  },

  // Bottom tagline
  taglineWrap: {
    alignItems: 'center',
    marginTop: 28,
  },
  tagline: {
    color: '#4A5B53',
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 18,
  },

  // URL config button
  urlConfigBtn: {
    position: 'absolute',
    top: 52,
    right: 16,
    zIndex: 10,
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  urlConfigIcon: { fontSize: 18 },

  // Guest button
  guestBtn: {
    alignItems: 'center',
    paddingVertical: 12,
    marginTop: 4,
    marginBottom: 4,
  },
  guestBtnText: {
    fontSize: 14,
    color: '#0C3F30',
    fontWeight: '600',
  },

  // URL modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#0B2019',
    marginBottom: 6,
  },
  modalHint: {
    fontSize: 13,
    color: '#4A5B53',
    marginBottom: 16,
    lineHeight: 18,
  },
  modalInput: {
    borderWidth: 1.5,
    borderColor: '#E2E9DF',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: '#0B2019',
    marginBottom: 20,
  },
  modalActions: {
    flexDirection: 'row',
    gap: 12,
  },
  modalCancel: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#E2E9DF',
    alignItems: 'center',
  },
  modalCancelText: { fontSize: 15, color: '#4A5B53', fontWeight: '600' },
  modalSave: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#0C3F30',
    alignItems: 'center',
  },
  modalSaveText: { fontSize: 15, color: '#fff', fontWeight: '700' },
});

export default LoginScreen;
