/**
 * ScanCodeBarresScreen — Reconnaître un produit par son code-barres.
 *
 * L'utilisateur vise l'étiquette ; le serveur interroge Open Food Facts et
 * renvoie photo officielle, marque et valeurs nutritionnelles. C'est la seule
 * voie qui enrichit le catalogue sans travail manuel — y compris pour les
 * produits que les utilisateurs ajoutent eux-mêmes.
 *
 * Tous les codes ne sont pas connus : la base est collaborative et sa
 * couverture du Maroc est partielle. L'échec est donc un cas ordinaire, traité
 * comme tel — on le dit et on propose la recherche par nom.
 */
import React, { useCallback, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

import { ProductsAPI } from '@services/api';
import { C, Radius } from '@constants/colors';

/** Formats portés par les produits d'épicerie ; les QR codes sont écartés. */
const FORMATS = ['ean13', 'ean8', 'upc_a', 'upc_e', 'itf14'] as const;

type Etat =
  | { phase: 'pret' }
  | { phase: 'recherche'; code: string }
  | { phase: 'inconnu'; code: string }
  | { phase: 'erreur'; message: string };

const ScanCodeBarresScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const [permission, demanderPermission] = useCameraPermissions();
  const [etat, setEtat] = useState<Etat>({ phase: 'pret' });

  // La caméra émet plusieurs fois le même code en une seconde. Sans ce
  // verrou, un seul passage déclencherait une rafale de requêtes.
  const verrou = useRef(false);

  const relancer = useCallback(() => {
    verrou.current = false;
    setEtat({ phase: 'pret' });
  }, []);

  const auScan = useCallback(
    async ({ data }: { data: string }) => {
      if (verrou.current) return;
      verrou.current = true;

      const code = data.replace(/\D/g, '');
      if (code.length < 8) {
        relancer();
        return;
      }

      setEtat({ phase: 'recherche', code });
      try {
        const produit = await ProductsAPI.getByBarcode(code);
        if (!produit) {
          setEtat({ phase: 'inconnu', code });
          return;
        }
        // On remplace l'écran de scan : revenir en arrière depuis la fiche
        // doit ramener à la liste, pas rouvrir la caméra sur le même code.
        navigation.navigate('ProduitDetail', {
          productId: produit.id,
          productName: produit.name,
        });
        relancer();
      } catch {
        setEtat({
          phase: 'erreur',
          message: "Connexion impossible. Vérifiez votre réseau et réessayez.",
        });
      }
    },
    [navigation, relancer],
  );

  // ── Caméra indisponible sur le web ────────────────────────────────────────
  if (Platform.OS === 'web') {
    return (
      <Message
        icone="phone-portrait-outline"
        titre="Scan disponible sur mobile"
        texte="La lecture de code-barres demande l'appareil photo du téléphone. Sur ordinateur, cherchez le produit par son nom."
        action={{ libelle: 'Rechercher un produit', onPress: () => navigation.navigate('Comparer') }}
      />
    );
  }

  if (!permission) {
    return <Chargement texte="Préparation de l'appareil photo…" />;
  }

  if (!permission.granted) {
    return (
      <Message
        icone="camera-outline"
        titre="Autoriser l'appareil photo"
        texte="PrixMaroc en a besoin pour lire le code-barres du produit. Aucune image n'est conservée ni envoyée."
        action={{ libelle: 'Autoriser', onPress: demanderPermission }}
      />
    );
  }

  return (
    <View style={styles.root}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: [...FORMATS] }}
        onBarcodeScanned={etat.phase === 'pret' ? auScan : undefined}
      />

      <SafeAreaView style={styles.calque} edges={['top', 'bottom']}>
        <View style={styles.entete}>
          <Text style={styles.enteteTitre}>Scanner un produit</Text>
          <Text style={styles.enteteTexte}>
            Cadrez le code-barres, la reconnaissance est automatique.
          </Text>
        </View>

        <View style={styles.viseur}>
          <View style={[styles.coin, styles.coinHG]} />
          <View style={[styles.coin, styles.coinHD]} />
          <View style={[styles.coin, styles.coinBG]} />
          <View style={[styles.coin, styles.coinBD]} />
        </View>

        <View style={styles.pied}>
          {etat.phase === 'recherche' && (
            <View style={styles.bandeau}>
              <ActivityIndicator color={C.white} />
              <Text style={styles.bandeauTexte}>Recherche du produit…</Text>
            </View>
          )}

          {etat.phase === 'inconnu' && (
            <View style={styles.bandeau}>
              <Ionicons name="help-circle-outline" size={22} color={C.white} />
              <View style={{ flex: 1 }}>
                <Text style={styles.bandeauTexte}>Produit inconnu</Text>
                <Text style={styles.bandeauSous}>
                  Le code {etat.code} ne figure dans aucune base.
                </Text>
              </View>
            </View>
          )}

          {etat.phase === 'erreur' && (
            <View style={[styles.bandeau, styles.bandeauErreur]}>
              <Ionicons name="cloud-offline-outline" size={22} color={C.white} />
              <Text style={styles.bandeauTexte}>{etat.message}</Text>
            </View>
          )}

          {(etat.phase === 'inconnu' || etat.phase === 'erreur') && (
            <View style={styles.actions}>
              <TouchableOpacity style={styles.boutonPlein} onPress={relancer}>
                <Ionicons name="scan-outline" size={18} color={C.white} />
                <Text style={styles.boutonPleinTexte}>Scanner à nouveau</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.boutonVide}
                onPress={() => navigation.navigate('Comparer')}
              >
                <Text style={styles.boutonVideTexte}>Chercher par nom</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </SafeAreaView>
    </View>
  );
};

// ── Écrans secondaires ──────────────────────────────────────────────────────

const Chargement: React.FC<{ texte: string }> = ({ texte }) => (
  <View style={styles.centre}>
    <ActivityIndicator color={C.primary} size="large" />
    <Text style={styles.centreTexte}>{texte}</Text>
  </View>
);

const Message: React.FC<{
  icone: keyof typeof Ionicons.glyphMap;
  titre: string;
  texte: string;
  action: { libelle: string; onPress: () => void };
}> = ({ icone, titre, texte, action }) => (
  <View style={styles.centre}>
    <View style={styles.rond}>
      <Ionicons name={icone} size={34} color={C.primary} />
    </View>
    <Text style={styles.centreTitre}>{titre}</Text>
    <Text style={styles.centreTexte}>{texte}</Text>
    <TouchableOpacity style={styles.boutonPlein} onPress={action.onPress}>
      <Text style={styles.boutonPleinTexte}>{action.libelle}</Text>
    </TouchableOpacity>
  </View>
);

// ── Styles ──────────────────────────────────────────────────────────────────

const OR = '#F2C230';

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  calque: { flex: 1, justifyContent: 'space-between' },

  entete: { paddingHorizontal: 24, paddingTop: 12 },
  enteteTitre: { color: C.white, fontSize: 20, fontWeight: '800' },
  enteteTexte: { color: 'rgba(255,255,255,0.78)', fontSize: 13.5, marginTop: 4 },

  viseur: { alignSelf: 'center', width: 264, height: 168 },
  coin: { position: 'absolute', width: 34, height: 34, borderColor: OR },
  coinHG: { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 10 },
  coinHD: { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 10 },
  coinBG: { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 10 },
  coinBD: { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 10 },

  pied: { paddingHorizontal: 20, paddingBottom: 16, gap: 12 },
  bandeau: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(15,76,58,0.94)',
    paddingVertical: 14, paddingHorizontal: 16, borderRadius: Radius.md,
  },
  bandeauErreur: { backgroundColor: 'rgba(178,31,36,0.94)' },
  bandeauTexte: { color: C.white, fontSize: 14.5, fontWeight: '600', flexShrink: 1 },
  bandeauSous: { color: 'rgba(255,255,255,0.8)', fontSize: 12.5, marginTop: 2 },

  actions: { gap: 10 },
  boutonPlein: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: C.primary, paddingVertical: 14, borderRadius: Radius.md,
  },
  boutonPleinTexte: { color: C.white, fontSize: 15, fontWeight: '700' },
  boutonVide: { alignItems: 'center', paddingVertical: 12 },
  boutonVideTexte: { color: C.white, fontSize: 14, fontWeight: '600', textDecorationLine: 'underline' },

  centre: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 14, backgroundColor: C.bg },
  rond: {
    width: 76, height: 76, borderRadius: 38, backgroundColor: C.primaryLight,
    alignItems: 'center', justifyContent: 'center',
  },
  centreTitre: { fontSize: 19, fontWeight: '800', color: C.text, textAlign: 'center' },
  centreTexte: { fontSize: 14.5, color: C.textSub, textAlign: 'center', lineHeight: 21 },
});

export default ScanCodeBarresScreen;
