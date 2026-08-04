import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  ScrollView,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { OcrAPI } from '@services/api';
import { C } from '@constants/colors';
import type { OcrScan } from '@types/models';

type ConfirmState = 'idle' | 'loading' | 'done' | 'error';

const FRAME_SIZE = 280;

// ── Capture progress steps ────────────────────────────────────────────────────

type CaptureStep = 'photo' | 'ocr' | 'done' | null;

const STEP_LABELS: Record<Exclude<CaptureStep, null>, string> = {
  photo: '📸 Photo prise…',
  ocr:   '⚙️ Analyse OCR…',
  done:  '✅ Terminé',
};

const CaptureProgress: React.FC<{ step: CaptureStep }> = ({ step }) => {
  if (!step) return null;
  const steps: Exclude<CaptureStep, null>[] = ['photo', 'ocr', 'done'];
  const currentIdx = steps.indexOf(step as Exclude<CaptureStep, null>);

  return (
    <View style={styles.progressWrap}>
      <View style={styles.progressCard}>
        {steps.map((s, idx) => (
          <View key={s} style={styles.progressStepRow}>
            <View
              style={[
                styles.progressDot,
                idx < currentIdx && styles.progressDotDone,
                idx === currentIdx && styles.progressDotActive,
              ]}
            >
              {idx < currentIdx ? (
                <Text style={styles.progressDotCheck}>✓</Text>
              ) : idx === currentIdx ? (
                <ActivityIndicator size="small" color="#ffffff" />
              ) : (
                <View style={styles.progressDotInner} />
              )}
            </View>
            <Text
              style={[
                styles.progressStepText,
                idx === currentIdx && styles.progressStepTextActive,
                idx < currentIdx && styles.progressStepTextDone,
              ]}
            >
              {STEP_LABELS[s]}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
};

// ── Empty results (done but nothing parsed) ───────────────────────────────────

const RetryGuide: React.FC<{ onReset: () => void }> = ({ onReset }) => (
  <View style={styles.retryGuideWrap}>
    <View style={styles.retryGuideCard}>
      <View style={styles.retryIconWrap}>
        <Text style={styles.retryIconEmoji}>🔍</Text>
      </View>
      <Text style={styles.retryGuideTitle}>Ticket difficile à lire</Text>
      <Text style={styles.retryGuideSubtitle}>
        L'OCR n'a pas pu extraire les données. Essayez ces conseils:
      </Text>

      <View style={styles.tipsList}>
        {[
          '✓ Bon éclairage (lumière naturelle de préférence)',
          '✓ Ticket bien aplati et sans plis',
          '✓ Évitez les reflets brillants',
          '✓ Cadrez tout le ticket dans le cadre',
          '✓ Tenez le téléphone stable lors de la capture',
        ].map((tip, i) => (
          <View key={i} style={styles.tipRow}>
            <Text style={styles.tipText}>{tip}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={styles.retryBtn}
        onPress={onReset}
        activeOpacity={0.85}
      >
        <Ionicons name="scan-outline" size={20} color="#ffffff" />
        <Text style={styles.retryBtnText}>Réessayer</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.manualLink}
        onPress={onReset}
        activeOpacity={0.7}
      >
        <Text style={styles.manualLinkText}>Saisir manuellement</Text>
      </TouchableOpacity>
    </View>
  </View>
);

// ── Editable item row ─────────────────────────────────────────────────────────

interface EditableItem {
  name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  is_promo?: boolean;
}

const EditableItemRow: React.FC<{
  item: EditableItem;
  index: number;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (updated: EditableItem) => void;
  isLast: boolean;
}> = ({ item, index, isEditing, onEdit, onSave, isLast }) => {
  const [name, setName] = useState(item.name);
  const [price, setPrice] = useState(item.unit_price.toFixed(2));

  const handleSave = () => {
    const parsedPrice = parseFloat(price.replace(',', '.'));
    if (!name.trim() || isNaN(parsedPrice) || parsedPrice <= 0) {
      Alert.alert('Valeur incorrecte', 'Entrez un nom et un prix valide.');
      return;
    }
    onSave({
      ...item,
      name: name.trim(),
      unit_price: parsedPrice,
      total_price: parsedPrice * item.quantity,
    });
  };

  if (isEditing) {
    return (
      <View style={[editStyles.editRow, !isLast && styles.itemRowBorder]}>
        <TextInput
          style={editStyles.nameInput}
          value={name}
          onChangeText={setName}
          placeholder="Nom du produit"
          placeholderTextColor="#9ca3af"
          returnKeyType="next"
        />
        <View style={editStyles.priceRow}>
          <TextInput
            style={editStyles.priceInput}
            value={price}
            onChangeText={setPrice}
            keyboardType="decimal-pad"
            placeholder="0.00"
            placeholderTextColor="#9ca3af"
          />
          <Text style={editStyles.priceCurrency}>MAD</Text>
          <TouchableOpacity style={editStyles.saveBtn} onPress={handleSave}>
            <Text style={editStyles.saveBtnText}>✓</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.itemRow, !isLast && styles.itemRowBorder]}>
      <View style={styles.itemInfo}>
        <Text style={styles.itemName} numberOfLines={2}>{item.name}</Text>
        {item.quantity > 1 ? (
          <Text style={styles.itemQty}>
            {item.quantity} × {item.unit_price.toFixed(2)} MAD
          </Text>
        ) : null}
        {item.is_promo ? (
          <View style={styles.promoBadge}>
            <Text style={styles.promoBadgeText}>PROMO</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.itemPriceWrap}>
        <Text style={styles.itemPrice}>{item.total_price.toFixed(2)}</Text>
        <Text style={styles.itemPriceUnit}>MAD</Text>
      </View>
      <TouchableOpacity style={editStyles.editBtn} onPress={onEdit}>
        <Ionicons name="pencil-outline" size={15} color="#94a3b8" />
      </TouchableOpacity>
    </View>
  );
};

// ── Results view ──────────────────────────────────────────────────────────────

const ResultsView: React.FC<{ scan: OcrScan; onReset: () => void }> = ({
  scan,
  onReset,
}) => {
  const [confirmState, setConfirmState] = useState<ConfirmState>('idle');
  const [pricesSaved, setPricesSaved] = useState<number>(0);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editedItems, setEditedItems] = useState<EditableItem[]>(
    () => (scan.parsed_data?.items ?? []).map((it) => ({ ...it })),
  );

  const parsed = scan.parsed_data;
  const storeName = parsed?.store?.name ?? parsed?.store?.chain ?? null;
  const isAlreadyConfirmed = !!parsed?.confirmed;
  const date = parsed?.date
    ? new Date(parsed.date).toLocaleDateString('fr-MA', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
      })
    : null;
  const total = parsed?.total;

  const statusColor =
    scan.status === 'done'
      ? C.primary
      : scan.status === 'failed'
      ? '#ef4444'
      : '#f59e0b';

  const statusLabel =
    scan.status === 'done'
      ? 'Traitement réussi'
      : scan.status === 'failed'
      ? 'Échec du traitement'
      : 'En cours de traitement…';

  const handleConfirm = async () => {
    if (confirmState === 'loading' || isAlreadyConfirmed) return;
    setEditingIndex(null);   // ferme tout champ en cours d'édition
    setConfirmState('loading');
    try {
      // Envoie les items corrigés si l'utilisateur les a modifiés
      const res = await OcrAPI.confirm(scan.id, undefined, editedItems);
      setPricesSaved(res.prices_saved ?? 0);
      setConfirmState('done');
    } catch {
      setConfirmState('error');
      Alert.alert(
        'Erreur',
        "Impossible d'enregistrer les prix. Vérifiez votre connexion.",
      );
    }
  };

  const handleItemSave = (index: number, updated: EditableItem) => {
    setEditedItems((prev) => prev.map((it, i) => (i === index ? updated : it)));
    setEditingIndex(null);
  };

  // When done but nothing was extracted → show retry guide
  const isDoneEmpty =
    scan.status === 'done' && editedItems.length === 0 && !storeName && total == null;

  if (isDoneEmpty) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <RetryGuide onReset={onReset} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.resultsScroll}
        contentContainerStyle={styles.resultsContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.resultsHeader}>
          <View style={[styles.resultsIconWrap, { borderColor: `${statusColor}30` }]}>
            <Ionicons
              name={
                scan.status === 'done'
                  ? 'checkmark-circle'
                  : scan.status === 'failed'
                  ? 'close-circle'
                  : 'hourglass'
              }
              size={38}
              color={statusColor}
            />
          </View>
          <Text style={styles.resultsTitle}>Ticket scanné</Text>
          <View
            style={[
              styles.statusBadge,
              { backgroundColor: `${statusColor}15` },
            ]}
          >
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusLabel, { color: statusColor }]}>
              {statusLabel}
            </Text>
          </View>
        </View>

        {/* Info card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Informations</Text>

          {storeName ? (
            <View style={styles.infoRow}>
              <Ionicons name="storefront-outline" size={16} color="#64748b" />
              <Text style={styles.infoLabel}>Magasin</Text>
              <Text style={styles.infoValue}>{storeName}</Text>
            </View>
          ) : null}

          {date ? (
            <View style={styles.infoRow}>
              <Ionicons name="calendar-outline" size={16} color="#64748b" />
              <Text style={styles.infoLabel}>Date</Text>
              <Text style={styles.infoValue}>{date}</Text>
            </View>
          ) : null}

          {total != null ? (
            <View style={[styles.infoRow, styles.totalRow]}>
              <Ionicons name="receipt-outline" size={16} color={C.primary} />
              <Text style={[styles.infoLabel, { color: C.primary }]}>Total</Text>
              <Text style={styles.totalValue}>{total.toFixed(2)} MAD</Text>
            </View>
          ) : null}

          {scan.status === 'failed' && (
            <Text style={styles.noInfoText}>
              {scan.error_message ?? 'Impossible de lire ce ticket.'}
            </Text>
          )}
        </View>

        {/* Articles (éditables) */}
        {editedItems.length > 0 && (
          <View style={styles.card}>
            <View style={styles.articlesTitleRow}>
              <Text style={styles.cardTitle}>Articles</Text>
              <View style={styles.articlesBadge}>
                <Text style={styles.articlesBadgeText}>{editedItems.length}</Text>
              </View>
              {!isAlreadyConfirmed && confirmState === 'idle' && (
                <Text style={editStyles.editHint}>
                  ✏️ Appuyez sur le crayon pour corriger
                </Text>
              )}
            </View>

            {editedItems.map((item, i) => (
              <EditableItemRow
                key={i}
                item={item}
                index={i}
                isEditing={editingIndex === i}
                onEdit={() => setEditingIndex(editingIndex === i ? null : i)}
                onSave={(updated) => handleItemSave(i, updated)}
                isLast={i === editedItems.length - 1}
              />
            ))}

            {/* Subtotal */}
            <View style={styles.subtotalRow}>
              <Text style={styles.subtotalLabel}>Sous-total calculé</Text>
              <Text style={styles.subtotalValue}>
                {editedItems.reduce((s, it) => s + it.total_price, 0).toFixed(2)} MAD
              </Text>
            </View>
          </View>
        )}

        {/* ── Validation des prix ── */}
        {scan.status === 'done' && editedItems.length > 0 && !isAlreadyConfirmed && (
          <TouchableOpacity
            style={[
              styles.confirmBtn,
              confirmState === 'done' && styles.confirmBtnDone,
              confirmState === 'loading' && styles.confirmBtnLoading,
            ]}
            onPress={handleConfirm}
            disabled={confirmState === 'loading' || confirmState === 'done'}
            activeOpacity={0.85}
          >
            {confirmState === 'loading' ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : confirmState === 'done' ? (
              <>
                <Ionicons name="checkmark-circle" size={20} color="#ffffff" />
                <Text style={styles.confirmBtnText}>
                  {pricesSaved > 0
                    ? `${pricesSaved} prix enregistrés ✓`
                    : 'Ticket confirmé ✓'}
                </Text>
              </>
            ) : (
              <>
                <Ionicons name="save-outline" size={20} color="#ffffff" />
                <Text style={styles.confirmBtnText}>
                  Valider et enregistrer les prix
                </Text>
              </>
            )}
          </TouchableOpacity>
        )}

        {/* Déjà confirmé */}
        {(isAlreadyConfirmed || confirmState === 'done') && (
          <View style={styles.confirmedBanner}>
            <Ionicons name="shield-checkmark-outline" size={16} color="#15803d" />
            <Text style={styles.confirmedBannerText}>
              Prix enregistrés — ils améliorent la précision de l'application pour tous
            </Text>
          </View>
        )}

        {/* Actions */}
        <TouchableOpacity
          style={styles.resetBtn}
          onPress={onReset}
          activeOpacity={0.85}
        >
          <Ionicons name="scan-outline" size={20} color="#ffffff" />
          <Text style={styles.resetBtnText}>Scanner un autre ticket</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
};

// ── Main scanner screen ───────────────────────────────────────────────────────

const ScannerScreen: React.FC = () => {
  const [permission, requestPermission] = useCameraPermissions();
  const [isCapturing, setIsCapturing] = useState(false);
  const [captureStep, setCaptureStep] = useState<CaptureStep>(null);
  const [scanResult, setScanResult] = useState<OcrScan | null>(null);
  const cameraRef = useRef<CameraView>(null);

  const handleCapture = async () => {
    if (!cameraRef.current || isCapturing) return;
    setIsCapturing(true);
    setScanResult(null);
    setCaptureStep('photo');

    try {
      // Quality 0.85 — receipts have fine text, good quality is critical for OCR
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.85 });
      if (!photo?.uri) throw new Error('Impossible de capturer la photo.');

      setCaptureStep('ocr');

      // 60 s timeout for OCR endpoint
      const result = await OcrAPI.scan(photo.uri);

      setCaptureStep('done');
      // Brief pause so user sees the "done" state
      await new Promise((r) => setTimeout(r, 600));
      setScanResult(result);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ??
        (err as Error)?.message ??
        'Une erreur est survenue lors du scan.';
      Alert.alert('Erreur de scan', msg);
    } finally {
      setIsCapturing(false);
      setCaptureStep(null);
    }
  };

  // Permission loading
  if (!permission) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      </SafeAreaView>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <View style={styles.permissionIconWrap}>
            <Ionicons name="camera-outline" size={48} color="#4b5563" />
          </View>
          <Text style={styles.permissionTitle}>Accès à la caméra requis</Text>
          <Text style={styles.permissionText}>
            Pour scanner vos tickets de caisse, PrixMaroc a besoin d'accéder à
            votre caméra.
          </Text>
          <TouchableOpacity
            style={styles.permissionBtn}
            onPress={requestPermission}
            activeOpacity={0.85}
          >
            <Text style={styles.permissionBtnText}>Autoriser la caméra</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Show scan results
  if (scanResult) {
    return (
      <ResultsView scan={scanResult} onReset={() => setScanResult(null)} />
    );
  }

  // Camera view
  return (
    <View style={styles.cameraContainer}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back">
        <View style={styles.overlay}>
          {/* Top hint */}
          <View style={styles.overlayTop}>
            <Text style={styles.topHint}>Scanner un ticket de caisse</Text>
            <Text style={styles.topHintSub}>
              Alignez votre ticket dans le cadre
            </Text>
          </View>

          {/* Scan frame row */}
          <View style={styles.overlayMiddle}>
            <View style={styles.overlaySide} />
            <View style={styles.scanFrame}>
              <View style={[styles.corner, styles.cornerTL]} />
              <View style={[styles.corner, styles.cornerTR]} />
              <View style={[styles.corner, styles.cornerBL]} />
              <View style={[styles.corner, styles.cornerBR]} />
              {/* Animated scan line hint */}
              {isCapturing && (
                <View style={styles.scanLineHint} />
              )}
            </View>
            <View style={styles.overlaySide} />
          </View>

          {/* Bottom controls */}
          <View style={styles.overlayBottom}>
            {isCapturing ? (
              <CaptureProgress step={captureStep} />
            ) : (
              <>
                <Text style={styles.scanHint}>
                  Placez votre ticket dans le cadre et appuyez sur le bouton
                </Text>
                <TouchableOpacity
                  style={styles.captureBtn}
                  onPress={handleCapture}
                  disabled={isCapturing}
                  activeOpacity={0.85}
                >
                  <View style={styles.captureInner} />
                </TouchableOpacity>
                <Text style={styles.scanHintSub}>
                  Astuce: bonne lumière = meilleur résultat
                </Text>
              </>
            )}
          </View>
        </View>
      </CameraView>
    </View>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#111827' },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },

  // Permission
  permissionIconWrap: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: '#1f2937',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 12,
    textAlign: 'center',
  },
  permissionText: {
    fontSize: 15,
    color: '#9ca3af',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 22,
  },
  permissionBtn: {
    backgroundColor: C.primary,
    paddingHorizontal: 32,
    paddingVertical: 15,
    borderRadius: 14,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  permissionBtnText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },

  // Camera
  cameraContainer: { flex: 1 },
  camera: { flex: 1 },
  overlay: { flex: 1 },
  overlayTop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.62)',
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 16,
    gap: 4,
  },
  topHint: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
  topHintSub: { color: 'rgba(255,255,255,0.65)', fontSize: 13 },

  overlayMiddle: { flexDirection: 'row', height: FRAME_SIZE },
  overlaySide: { flex: 1, backgroundColor: 'rgba(0,0,0,0.62)' },
  scanFrame: { width: FRAME_SIZE, height: FRAME_SIZE, position: 'relative' },

  corner: {
    position: 'absolute',
    width: 28,
    height: 28,
    borderColor: C.primary,
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderTopLeftRadius: 5,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderTopRightRadius: 5,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderBottomLeftRadius: 5,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderBottomRightRadius: 5,
  },

  scanLineHint: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '50%',
    height: 2,
    backgroundColor: `${C.primary}80`,
  },

  overlayBottom: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.62)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    gap: 14,
  },
  scanHint: {
    color: '#d1d5db',
    fontSize: 13,
    textAlign: 'center',
    paddingHorizontal: 40,
    lineHeight: 18,
  },
  scanHintSub: {
    color: 'rgba(255,255,255,0.45)',
    fontSize: 12,
    textAlign: 'center',
  },
  captureBtn: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 4,
    borderColor: '#ffffff',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.55,
    shadowRadius: 10,
    elevation: 10,
  },
  captureInner: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#ffffff',
  },

  // Capture progress
  progressWrap: {
    width: '100%',
    paddingHorizontal: 24,
  },
  progressCard: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 16,
    padding: 18,
    gap: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.15)',
  },
  progressStepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  progressDot: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  progressDotActive: {
    backgroundColor: C.primary,
  },
  progressDotDone: {
    backgroundColor: '#15803d',
  },
  progressDotInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(255,255,255,0.35)',
  },
  progressDotCheck: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '700',
  },
  progressStepText: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '500',
  },
  progressStepTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  progressStepTextDone: {
    color: 'rgba(255,255,255,0.65)',
  },

  // Retry guide
  retryGuideWrap: {
    flex: 1,
    backgroundColor: '#f8fafc',
    justifyContent: 'center',
    padding: 20,
  },
  retryGuideCard: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 28,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 6,
  },
  retryIconWrap: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#f0fdf4',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    borderWidth: 2,
    borderColor: '#bbf7d0',
  },
  retryIconEmoji: { fontSize: 38 },
  retryGuideTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0f172a',
    marginBottom: 8,
    textAlign: 'center',
  },
  retryGuideSubtitle: {
    fontSize: 14,
    color: '#64748b',
    textAlign: 'center',
    marginBottom: 22,
    lineHeight: 20,
  },
  tipsList: {
    alignSelf: 'stretch',
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 16,
    gap: 10,
    marginBottom: 24,
  },
  tipRow: {},
  tipText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: C.primary,
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: 40,
    alignSelf: 'stretch',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
    marginBottom: 14,
  },
  retryBtnText: { color: '#ffffff', fontSize: 17, fontWeight: '700' },
  manualLink: { paddingVertical: 6 },
  manualLinkText: {
    color: '#64748b',
    fontSize: 14,
    textDecorationLine: 'underline',
  },

  // Results
  resultsScroll: { flex: 1, backgroundColor: '#f8fafc' },
  resultsContent: { padding: 16, paddingBottom: 40 },
  resultsHeader: { alignItems: 'center', paddingVertical: 28, gap: 10 },
  resultsIconWrap: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 4,
  },
  resultsTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0f172a',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusLabel: { fontSize: 13, fontWeight: '600' },

  // Cards
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 18,
    marginBottom: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  },
  cardTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#94a3b8',
    marginBottom: 14,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  totalRow: { borderBottomWidth: 0, paddingTop: 14 },
  infoLabel: { flex: 1, fontSize: 14, color: '#64748b', fontWeight: '500' },
  infoValue: { fontSize: 14, fontWeight: '600', color: '#0f172a' },
  totalValue: { fontSize: 22, fontWeight: '800', color: C.primary },
  noInfoText: {
    color: '#94a3b8',
    fontSize: 14,
    fontStyle: 'italic',
    textAlign: 'center',
    paddingVertical: 8,
  },

  // Articles
  articlesTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  articlesBadge: {
    backgroundColor: '#f0fdf4',
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  articlesBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#16a34a',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 12,
    gap: 10,
  },
  itemRowBorder: { borderBottomWidth: 1, borderBottomColor: '#f1f5f9' },
  itemInfo: { flex: 1 },
  itemName: {
    fontSize: 14,
    color: '#0f172a',
    fontWeight: '600',
    marginBottom: 3,
    lineHeight: 19,
  },
  itemQty: { fontSize: 12, color: '#94a3b8', marginBottom: 3 },
  promoBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#fef2f2',
    borderRadius: 5,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginTop: 3,
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  promoBadgeText: { color: '#dc2626', fontSize: 9, fontWeight: '800' },
  itemPriceWrap: { alignItems: 'flex-end' },
  itemPrice: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0f172a',
    textAlign: 'right',
  },
  itemPriceUnit: {
    fontSize: 10,
    color: '#94a3b8',
    fontWeight: '600',
    textAlign: 'right',
  },
  subtotalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 14,
    marginTop: 4,
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
  },
  subtotalLabel: { fontSize: 13, color: '#64748b', fontWeight: '600' },
  subtotalValue: { fontSize: 15, fontWeight: '800', color: '#0f172a' },

  // Confirm button
  confirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#0891b2',  // cyan-600
    borderRadius: 16,
    paddingVertical: 17,
    marginBottom: 12,
    shadowColor: '#0891b2',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  confirmBtnDone: { backgroundColor: '#15803d' },
  confirmBtnLoading: { opacity: 0.7 },
  confirmBtnText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },

  confirmedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#f0fdf4',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  confirmedBannerText: {
    flex: 1,
    fontSize: 13,
    color: '#15803d',
    lineHeight: 18,
  },

  // Reset button
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: C.primary,
    borderRadius: 16,
    paddingVertical: 17,
    marginTop: 6,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  resetBtnText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
});

// ── Styles for editable items ─────────────────────────────────────────────────

const editStyles = StyleSheet.create({
  editHint: {
    flex: 1,
    textAlign: 'right',
    fontSize: 11,
    color: '#94a3b8',
    fontStyle: 'italic',
  },
  editRow: {
    paddingVertical: 10,
    gap: 8,
  },
  nameInput: {
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    color: '#0f172a',
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  priceInput: {
    flex: 1,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    color: '#0f172a',
    textAlign: 'right',
  },
  priceCurrency: {
    fontSize: 13,
    fontWeight: '700',
    color: '#64748b',
  },
  saveBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  editBtn: {
    padding: 6,
    marginLeft: 4,
    borderRadius: 6,
    backgroundColor: '#f1f5f9',
  },
});

export default ScannerScreen;
