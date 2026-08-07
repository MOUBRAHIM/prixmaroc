"""
Service OCR complet pour tickets de caisse marocains.

Pipeline :
  Image (JPEG/PNG/PDF)
    → ImagePreprocessor  (OpenCV : débruitage, redressement, contraste)
    → Tesseract ara+fra
    → ReceiptParser      (regex : magasin, date, produits, total)
    → ProductNormalizer  (fuzzy-match contre catalogue BDD)
    → dict structuré
"""
from __future__ import annotations

import gc
import io
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import BinaryIO

# Dépendances OCR lourdes (cv2/numpy/pytesseract/PIL) — optionnelles.
# Absentes en dev léger : le module s'importe quand même, seul le scan échoue.
try:
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image
    OCR_SUPPORT = True
except ImportError:  # pragma: no cover
    cv2 = None            # type: ignore[assignment]
    np = None             # type: ignore[assignment]
    pytesseract = None    # type: ignore[assignment]
    Image = None          # type: ignore[assignment]
    OCR_SUPPORT = False

# pdf2image est optionnel — uniquement pour les PDF
try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


# ──────────────────────────────────────────────────────────────────────────────
# Structures de données
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ReceiptItem:
    name: str
    quantity: float
    unit_price: float
    total_price: float
    normalized_name: str | None = None
    confidence: float = 0.0


@dataclass
class ParsedReceipt:
    store_name: str | None
    store_chain: str | None          # "marjane" | "carrefour" | "labelvie" | "bim" | "atacadao" | …
    purchase_date: datetime | None
    items: list[ReceiptItem] = field(default_factory=list)
    subtotal: float | None = None
    total: float | None = None
    currency: str = "MAD"
    raw_text: str = ""
    ocr_confidence: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 1. Préprocesseur d'image
# ──────────────────────────────────────────────────────────────────────────────

class ImagePreprocessor:
    """
    Améliore la qualité de l'image avant l'OCR :
      1. Conversion en niveaux de gris
      2. Débruitage (Non-Local Means)
      3. Redressement (deskew via lignes de Hough)
      4. Amélioration du contraste (CLAHE)
      5. Binarisation adaptative
    """

    TARGET_DPI = 300   # résolution cible pour Tesseract

    def process(self, image_data: bytes, mime_type: str = "image/jpeg") -> np.ndarray:
        """Retourne un tableau numpy prêt pour Tesseract."""
        pages = self._decode(image_data, mime_type)
        # On traite la première page (ou la seule)
        return self._enhance(pages[0])

    def process_all_pages(self, image_data: bytes, mime_type: str) -> list[np.ndarray]:
        """Retourne toutes les pages (utile pour les PDF multi-pages)."""
        return [self._enhance(p) for p in self._decode(image_data, mime_type)]

    # ── Décodage ──────────────────────────────────────────────────────────────

    def _decode(self, data: bytes, mime_type: str) -> list[np.ndarray]:
        if mime_type == "application/pdf":
            return self._decode_pdf(data)
        return [self._decode_image(data)]

    def _decode_image(self, data: bytes) -> np.ndarray:
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            # Fallback via Pillow
            pil = Image.open(io.BytesIO(data)).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        return img

    def _decode_pdf(self, data: bytes) -> list[np.ndarray]:
        if not PDF_SUPPORT:
            raise RuntimeError("pdf2image non installé — pip install pdf2image")
        pil_pages = convert_from_bytes(data, dpi=self.TARGET_DPI)
        result = []
        for pil in pil_pages:
            img = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
            result.append(img)
        return result

    # ── Pipeline d'amélioration ───────────────────────────────────────────────

    def _enhance(self, img: np.ndarray) -> np.ndarray:
        gray   = self._to_gray(img)
        scaled = self._scale_to_dpi(gray)
        denoised = self._denoise(scaled)
        deskewed = self._deskew(denoised)
        contrasted = self._enhance_contrast(deskewed)
        binary = self._binarize(contrasted)
        return binary

    def _enhance_light(self, img: np.ndarray) -> np.ndarray:
        """Preprocessing léger — conserve plus de détails (fallback)."""
        gray   = self._to_gray(img)
        scaled = self._scale_to_dpi(gray)
        denoised = self._denoise(scaled)
        contrasted = self._enhance_contrast(denoised)
        # Seuillage Otsu global (moins agressif que l'adaptatif)
        _, binary = cv2.threshold(contrasted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _to_gray(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    # Plafond de résolution : au-delà, Tesseract consomme énormément de RAM
    # sans gagner en précision sur un ticket de caisse.
    MAX_DIMENSION = 2200

    def _scale_to_dpi(self, gray: np.ndarray) -> np.ndarray:
        """Ajuste la résolution : agrandit si trop petit, réduit si trop grand."""
        h, w = gray.shape[:2]
        longest = max(h, w)
        if longest < 1500:
            scale = 1500 / longest
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        elif longest > self.MAX_DIMENSION:
            scale = self.MAX_DIMENSION / longest
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        return gray

    def _denoise(self, gray: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    def _deskew(self, gray: np.ndarray) -> np.ndarray:
        """Détecte l'angle d'inclinaison et redresse l'image."""
        angle = self._detect_skew_angle(gray)
        if abs(angle) < 0.5:
            return gray
        return self._rotate(gray, angle)

    def _detect_skew_angle(self, gray: np.ndarray) -> float:
        # Méthode 1 : moments sur image binarisée
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 100:
            return 0.0
        angle = cv2.minAreaRect(coords)[-1]
        # minAreaRect retourne un angle entre -90 et 0
        if angle < -45:
            angle += 90
        return -angle

    def _rotate(self, gray: np.ndarray, angle: float) -> np.ndarray:
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            gray, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    def _enhance_contrast(self, gray: np.ndarray) -> np.ndarray:
        """CLAHE — améliore le contraste local."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    def _binarize(self, gray: np.ndarray) -> np.ndarray:
        """
        Seuillage adaptatif — gère les éclairages non uniformes.
        Paramètres optimisés pour les tickets thermiques marocains :
        - blockSize=11 : fenêtre locale réduite, préserve les petits caractères
        - C=6 : offset légèrement réduit pour mieux capturer le texte à faible contraste
        """
        # Tentative avec seuillage adaptatif
        adaptive = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=6,
        )
        # Si l'image résultante est trop noire (sur-binarisation), utilise Otsu
        white_ratio = np.sum(adaptive == 255) / adaptive.size
        if white_ratio < 0.4:
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return otsu
        return adaptive


# ──────────────────────────────────────────────────────────────────────────────
# 2. Parser de ticket
# ──────────────────────────────────────────────────────────────────────────────

# Patterns des enseignes marocaines
STORE_PATTERNS: dict[str, list[str]] = {
    "marjane":   [r"marjane", r"مرجان"],
    "carrefour": [r"carrefour", r"كارفور"],
    "labelvie":  [r"label.?vie", r"label vie", r"اتيكيت الحياة"],
    "bim":       [r"\bbim\b", r"بيم"],
    "atacadao":  [r"atacad[aã]o", r"اتاكاداو"],
    "aswak":     [r"aswak\s*assalam", r"اسواق السلام"],
    "acima":     [r"acima", r"اسيما"],
    "hanouty":   [r"hanouty", r"حانوتي"],
    "kazyon":    [r"kazyon", r"كازيون"],
    "sopreco":   [r"sopreco"],
}

# Affichage normalisé
STORE_DISPLAY: dict[str, str] = {
    "marjane":   "Marjane",
    "carrefour": "Carrefour",
    "labelvie":  "Label'Vie",
    "bim":       "BIM",
    "atacadao":  "Atacadão",
    "aswak":     "Aswak Assalam",
    "acima":     "Acima",
    "hanouty":   "Hanouty",
    "kazyon":    "Kazyon",
    "sopreco":   "Sopreco",
}


class ReceiptParser:
    """
    Parse le texte brut d'un ticket en données structurées.

    Patterns supportés (prix en MAD) :
      • Produit + prix sur une seule ligne :
          LAIT CENTRAL 1L                  8.50
      • Produit + quantité × prix unitaire + total :
          COCA COLA 33CL        2 x  5.00  10.00
      • Prix avec virgule (format français) :
          BEURRE PRESIDENT      12,50
      • Texte arabe mélangé
    """

    # ── Expressions régulières ────────────────────────────────────────────────

    _DATE_PATTERNS = [
        r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})\s+(\d{2})[:\s](\d{2})(?:[:\s](\d{2}))?",   # DD/MM/YYYY HH:MM[:SS]
        r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})\s+(?:heure\s*[:\s]+)(\d{2})[:\s](\d{2})(?:[:\s](\d{2}))?",  # Kazyon: DD/MM/YYYY Heure: HH:MM:SS
        r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})",                                             # DD/MM/YYYY
        r"(\d{4})[/\-.](\d{2})[/\-.](\d{2})",                                             # YYYY-MM-DD
    ]

    _PRICE_RE = r"(\d{1,5}[.,]\d{2})"

    # Ligne avec quantité × prix unitaire + total  (ex: COCA COLA 2 x 12.50 25.00)
    _ITEM_QTY_RE = re.compile(
        r"^(.+?)\s+"
        r"(\d+(?:[.,]\d+)?)\s*[xX×*]\s*"
        r"(\d{1,5}[.,]\d{2})\s+"
        r"(\d{1,5}[.,]\d{2})\s*(?:MAD|DH|د\.م\.)?$",
        re.IGNORECASE,
    )

    # Format Kazyon / colonnes : QTY  PRODUCT  PU  PT  (ex: 1.00  PAIN TORTILLA 25cm  14.95  14.95)
    _ITEM_LEADING_QTY_RE = re.compile(
        r"^(\d+[.,]\d{2})\s{2,}"          # quantité au début (1.00 ou 2,00)
        r"(.{3,}?)\s{2,}"                  # nom du produit (min 3 chars, suivi de 2+ espaces)
        r"(\d{1,5}[.,]\d{2})\s+"           # prix unitaire
        r"(\d{1,5}[.,]\d{2})\s*(?:MAD|DH)?$",
        re.IGNORECASE,
    )

    # Ligne produit + prix (sans quantité explicite)
    _ITEM_SIMPLE_RE = re.compile(
        r"^(.{3,}?)\s+(\d{1,5}[.,]\d{2})\s*(?:MAD|DH|د\.م\.)?$",
        re.IGNORECASE,
    )

    # Matches grand total lines — negative lookbehind excludes "sous-total"
    _TOTAL_RE = re.compile(
        r"(?<!\w)(?:net\s*[aà]\s*payer|[aà]\s*payer|montant\s*net|montant\s*total"
        r"|total\s*net|total\s*ttc|مجموع|المبلغ)[^\d]*(\d{1,6}[.,]\d{2})"
        r"|^total\s*[^\d]*(\d{1,6}[.,]\d{2})",
        re.IGNORECASE | re.MULTILINE,
    )

    _SUBTOTAL_RE = re.compile(
        r"(?:sous.?total|total\s*ht|hors\s*taxe)[^\d]*(\d{1,6}[.,]\d{2})",
        re.IGNORECASE,
    )

    # ── API publique ──────────────────────────────────────────────────────────

    def parse(self, raw_text: str) -> ParsedReceipt:
        lines = self._clean_lines(raw_text)
        receipt = ParsedReceipt(
            store_name=None,
            store_chain=None,
            purchase_date=None,
            raw_text=raw_text,
        )
        receipt.store_chain, receipt.store_name = self._extract_store(lines)
        receipt.purchase_date = self._extract_date(raw_text)
        receipt.items = self._extract_items(lines)
        receipt.total = self._extract_total(raw_text)
        receipt.subtotal = self._extract_subtotal(raw_text)

        # Si aucun total trouvé → on somme les lignes
        if receipt.total is None and receipt.items:
            receipt.total = round(sum(i.total_price for i in receipt.items), 2)

        return receipt

    # ── Nettoyage ─────────────────────────────────────────────────────────────

    def _clean_lines(self, text: str) -> list[str]:
        lines = []
        for line in text.splitlines():
            line = line.strip()
            # Supprime les lignes trop courtes ou composées de séparateurs
            if len(line) < 3 or re.match(r"^[-=*_]{3,}$", line):
                continue
            lines.append(line)
        return lines

    # ── Magasin ───────────────────────────────────────────────────────────────

    def _extract_store(self, lines: list[str]) -> tuple[str | None, str | None]:
        # On cherche dans les 10 premières lignes (header du ticket)
        header = " ".join(lines[:10]).lower()
        for chain, patterns in STORE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, header, re.IGNORECASE):
                    # Nom affiché = première ligne qui contient le pattern
                    for line in lines[:10]:
                        if re.search(pat, line, re.IGNORECASE):
                            return chain, line.strip()
                    return chain, STORE_DISPLAY[chain]
        return None, None

    # ── Date ──────────────────────────────────────────────────────────────────

    def _extract_date(self, text: str) -> datetime | None:
        for pattern in self._DATE_PATTERNS:
            m = re.search(pattern, text)
            if not m:
                continue
            groups = m.groups()
            try:
                if len(groups) >= 6 and groups[5]:  # avec secondes
                    dd, mo, yy, hh, mi, ss = (int(g) for g in groups[:6])
                    return datetime(yy, mo, dd, hh, mi, ss)
                elif len(groups) >= 5:               # avec heure:minute
                    dd, mo, yy, hh, mi = (int(g) for g in groups[:5])
                    return datetime(yy, mo, dd, hh, mi)
                elif len(groups) >= 3:
                    g = [int(x) for x in groups[:3]]
                    if g[0] > 31:                    # YYYY-MM-DD (year first)
                        return datetime(g[0], g[1], g[2])
                    return datetime(g[2], g[1], g[0])  # DD/MM/YYYY (year last)
            except (ValueError, TypeError):
                continue
        return None

    # ── Produits ──────────────────────────────────────────────────────────────

    def _extract_items(self, lines: list[str]) -> list[ReceiptItem]:
        items: list[ReceiptItem] = []
        in_items_section = False

        skip_keywords = re.compile(
            r"total|sous.total|tva|taxe|remise|reduction|fidel|avoir"
            r"|caisse|ticket|merci|bienvenue|espece|rendu|timbre|points"
            r"|ventilation|numero|client|caissier|مجموع|ضريبة|خصم",
            re.IGNORECASE,
        )

        for line in lines:
            # Détection du début de section produits (après l'en-tête)
            if re.search(r"article|produit|libelle|désignation|description", line, re.IGNORECASE):
                in_items_section = True
                continue

            if skip_keywords.search(line):
                continue

            item = self._parse_item_line(line)
            if item:
                in_items_section = True
                items.append(item)

        return items

    def _parse_item_line(self, line: str) -> ReceiptItem | None:
        # Tentative 1 : QTY × UNIT_PRICE  TOTAL  (ex: COCA COLA 2 x 12.50 25.00)
        m = self._ITEM_QTY_RE.match(line)
        if m:
            name, qty, unit, total = m.groups()
            return ReceiptItem(
                name=name.strip(),
                quantity=self._parse_price(qty),
                unit_price=self._parse_price(unit),
                total_price=self._parse_price(total),
            )

        # Tentative 2 : QTY  NAME  PU  PT  (format Kazyon: 1.00  PAIN TORTILLA  14.95  14.95)
        m = self._ITEM_LEADING_QTY_RE.match(line)
        if m:
            qty, name, unit, total = m.groups()
            return ReceiptItem(
                name=name.strip(),
                quantity=self._parse_price(qty),
                unit_price=self._parse_price(unit),
                total_price=self._parse_price(total),
            )

        # Tentative 3 : NAME PRICE (quantité = 1)
        m = self._ITEM_SIMPLE_RE.match(line)
        if m:
            name, price = m.groups()
            name = name.strip()
            # Filtre les faux positifs
            if len(name) < 2:
                return None
            # Exclure les lignes de totaux/taxes qui auraient échappé aux skip_keywords
            if re.search(
                r"^(total|sous.?total|tva|taxe|remise|fidel|avoir|net\s*à|montant)",
                name,
                re.IGNORECASE,
            ):
                return None
            # Exclure les lignes avec un prix irréaliste (> 9999 MAD)
            price_val = self._parse_price(price)
            if price_val > 9999:
                return None
            return ReceiptItem(
                name=name,
                quantity=1.0,
                unit_price=price_val,
                total_price=price_val,
            )

        return None

    # ── Total ─────────────────────────────────────────────────────────────────

    def _extract_total(self, text: str) -> float | None:
        # Try "NET A PAYER / MONTANT NET / TOTAL NET" patterns first (highest priority)
        m = self._TOTAL_RE.search(text)
        if m:
            val = m.group(1) or m.group(2)
            return self._parse_price(val)
        # Fallback: last occurrence of a bare "TOTAL" line (avoids "SOUS-TOTAL")
        _bare = re.compile(
            r"^(?:total)\s+(\d{1,6}[.,]\d{2})\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        matches = _bare.findall(text)
        if matches:
            return self._parse_price(matches[-1])
        return None

    def _extract_subtotal(self, text: str) -> float | None:
        m = self._SUBTOTAL_RE.search(text)
        return self._parse_price(m.group(1)) if m else None

    # ── Utilitaires ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_price(value: str) -> float:
        return float(value.replace(",", "."))


# ──────────────────────────────────────────────────────────────────────────────
# 3. Normaliseur de noms de produits
# ──────────────────────────────────────────────────────────────────────────────

# Catalogue de référence : noms bruts → noms normalisés
# (en production : charger depuis la BDD via Product.name)
DEFAULT_CATALOG: list[str] = [
    "Lait Centrale Danone 1L",
    "Lait Bimo 1L",
    "Eau Sidi Ali 1.5L",
    "Eau Ain Saiss 1.5L",
    "Eau Oulmès 1.5L",
    "Coca-Cola 33cl",
    "Coca-Cola 1.5L",
    "Pain de mie Harry's",
    "Beurre Président 250g",
    "Fromage Kiri 8 portions",
    "Yaourt Activia nature",
    "Huile de table Lesieur 1L",
    "Sucre cristal 1kg",
    "Farine Tria 1kg",
    "Riz long grain 1kg",
    "Pâtes Barilla spaghetti 500g",
    "Thon en boîte Doha 120g",
    "Sardines Doha 125g",
    "Café Nescafé Classic 100g",
    "Savon Lux 100g",
    "Lessive Tide 1kg",
    "Shampoing Head & Shoulders 200ml",
]


class ProductNormalizer:
    """
    Associe un nom de produit brut (issu de l'OCR) au produit le plus proche
    dans le catalogue en utilisant la similarité de chaînes (SequenceMatcher).
    """

    MATCH_THRESHOLD = 0.55  # score minimum pour accepter un match

    def __init__(self, catalog: list[str] | None = None):
        self._catalog = [self._normalize(n) for n in (catalog or DEFAULT_CATALOG)]
        self._catalog_raw = catalog or DEFAULT_CATALOG

    def normalize(self, raw_name: str) -> tuple[str | None, float]:
        """
        Retourne (nom_normalisé, score) ou (None, 0.0) si aucun match suffisant.
        """
        normalized = self._normalize(raw_name)
        best_score = 0.0
        best_match: str | None = None

        for ref_norm, ref_raw in zip(self._catalog, self._catalog_raw):
            score = self._similarity(normalized, ref_norm)
            if score > best_score:
                best_score = score
                best_match = ref_raw

        if best_score >= self.MATCH_THRESHOLD:
            return best_match, round(best_score, 3)
        return None, 0.0

    @staticmethod
    def _normalize(text: str) -> str:
        """Supprime les accents, met en minuscules, nettoie les espaces."""
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


# ──────────────────────────────────────────────────────────────────────────────
# 4. Service principal
# ──────────────────────────────────────────────────────────────────────────────

class OcrService:
    """
    Orchestre le pipeline complet :
      Image → préprocessing → Tesseract (multi-passes) → parsing → normalisation → JSON
    """

    # Configs Tesseract essayées dans l'ordre : colonne unique (tickets), bloc uniforme, auto
    # psm 4 = colonne unique (optimal pour tickets thermiques étroits)
    # psm 6 = bloc de texte uniforme
    # psm 3 = segmentation auto (fallback)
    # Ordonnées de la plus rentable à la plus coûteuse. Le français seul est
    # placé en tête : il charge un seul modèle de langue (moitié moins de
    # mémoire) et suffit à la très grande majorité des tickets marocains.
    _TESSERACT_CONFIGS = [
        "--oem 3 --psm 4 -l fra",       # colonne unique, français — le plus léger
        "--oem 3 --psm 6 -l fra",       # bloc de texte uniforme, français
        "--oem 3 --psm 4 -l fra+ara",   # ajoute l'arabe si le français ne suffit pas
        "--oem 3 --psm 6 -l fra+ara",   # bloc uniforme, bilingue
        "--oem 3 --psm 3 -l fra+ara",   # segmentation auto (dernier recours)
    ]

    # Nombre maximum de configurations essayées. Réglable via l'environnement :
    # 2 suffit sur un hébergement à mémoire limitée (512 Mo), 5 sur un serveur
    # confortable pour maximiser la précision.
    DEFAULT_MAX_PASSES = 2

    def __init__(self, catalog: list[str] | None = None, max_passes: int | None = None):
        try:
            env_passes = int(os.getenv("OCR_MAX_PASSES", "") or 0)
        except ValueError:
            env_passes = 0
        self.max_passes = max(1, max_passes or env_passes or self.DEFAULT_MAX_PASSES)
        self.preprocessor = ImagePreprocessor()
        self.parser = ReceiptParser()
        self.normalizer = ProductNormalizer(catalog)

    # ── API publique ──────────────────────────────────────────────────────────

    def process_image(
        self,
        image_data: bytes,
        mime_type: str = "image/jpeg",
    ) -> dict:
        """
        Traite une image et retourne un dict JSON structuré.

        Args:
            image_data: Contenu binaire de l'image (JPEG, PNG ou PDF).
            mime_type:  Type MIME du fichier.

        Returns:
            {
              "store": {"name": ..., "chain": ...},
              "date": "ISO8601" | null,
              "items": [{"name", "normalized_name", "quantity",
                         "unit_price", "total_price", "confidence"}],
              "subtotal": float | null,
              "total": float | null,
              "currency": "MAD",
              "raw_text": str,
              "ocr_confidence": float,
            }
        """
        if mime_type == "application/pdf":
            pages = self.preprocessor.process_all_pages(image_data, mime_type)
            raw_text = "\n\n--- PAGE ---\n\n".join(
                self._best_ocr(p) for p in pages
            )
        else:
            # Le second prétraitement n'est calculé que s'il est réellement
            # nécessaire (évite de garder deux grandes images en mémoire).
            processed_full = self.preprocessor.process(image_data, mime_type)
            raw_text = self._best_ocr_dual(
                processed_full,
                lambda: self.preprocessor._enhance_light(
                    self.preprocessor._decode_image(image_data)
                ),
            )

        receipt = self.parser.parse(raw_text)
        receipt.ocr_confidence = self._estimate_confidence(raw_text)
        self._normalize_items(receipt)

        return self._to_dict(receipt)

    # ── OCR ───────────────────────────────────────────────────────────────────

    def _run_tesseract(self, img: np.ndarray, config: str) -> str:
        pil_img = Image.fromarray(img)
        return pytesseract.image_to_string(pil_img, config=config)

    def _score_text(self, text: str) -> float:
        """Score = nombre de lignes contenant un prix MAD-like."""
        price_lines = len(re.findall(r'\d{1,5}[.,]\d{2}', text))
        readable = self._estimate_confidence(text)
        return price_lines * readable

    # Un ticket correctement lu dépasse largement ce score : inutile de
    # continuer à essayer d'autres configurations (chaque passe Tesseract
    # charge les modèles de langue et coûte cher en mémoire).
    _GOOD_ENOUGH_SCORE = 4.0

    def _best_ocr(self, img: np.ndarray) -> str:
        """
        Essaie les configs Tesseract et retourne le meilleur résultat.

        S'arrête dès qu'un résultat est suffisamment bon, et se limite à
        OCR_MAX_PASSES configurations : sur un hébergement à mémoire réduite,
        enchaîner toutes les passes fait tuer le processus (OOM).
        """
        best_text = ""
        best_score = -1.0
        for cfg in self._TESSERACT_CONFIGS[:self.max_passes]:
            try:
                text = self._run_tesseract(img, cfg)
                score = self._score_text(text)
                if score > best_score:
                    best_score = score
                    best_text = text
                if best_score >= self._GOOD_ENOUGH_SCORE:
                    break
            except Exception:
                continue
            finally:
                gc.collect()
        return best_text or ""

    def _best_ocr_dual(self, img_full: np.ndarray, make_light) -> str:
        """
        Lit l'image principale, et ne tente le second prétraitement que si le
        résultat est faible. `make_light` est un callable : l'image allégée
        n'est donc calculée qu'en cas de besoin (économie mémoire).
        """
        text_full = self._best_ocr(img_full)
        if self._score_text(text_full) >= self._GOOD_ENOUGH_SCORE:
            return text_full

        del img_full
        gc.collect()

        try:
            img_light = make_light()
        except Exception:
            return text_full

        text_light = self._best_ocr(img_light)
        if self._score_text(text_light) > self._score_text(text_full):
            return text_light
        return text_full

    def _estimate_confidence(self, text: str) -> float:
        """Score de confiance basé sur la proportion de caractères lisibles."""
        if not text:
            return 0.0
        readable = sum(1 for c in text if c.isalnum() or c in " .,-:/\n")
        return round(readable / len(text), 3)

    # ── Normalisation ─────────────────────────────────────────────────────────

    def _normalize_items(self, receipt: ParsedReceipt) -> None:
        for item in receipt.items:
            norm, score = self.normalizer.normalize(item.name)
            item.normalized_name = norm
            item.confidence = score

    # ── Sérialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(receipt: ParsedReceipt) -> dict:
        return {
            "store": {
                "name": receipt.store_name,
                "chain": receipt.store_chain,
                "display": STORE_DISPLAY.get(receipt.store_chain or "", receipt.store_name),
            },
            "date": receipt.purchase_date.isoformat() if receipt.purchase_date else None,
            "items": [
                {
                    "name": item.name,
                    "normalized_name": item.normalized_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "match_confidence": item.confidence,
                }
                for item in receipt.items
            ],
            "subtotal": receipt.subtotal,
            "total": receipt.total,
            "currency": receipt.currency,
            "item_count": len(receipt.items),
            "raw_text": receipt.raw_text,
            "ocr_confidence": receipt.ocr_confidence,
        }
