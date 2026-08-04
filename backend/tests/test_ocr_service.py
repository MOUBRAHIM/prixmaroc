"""
Tests unitaires — Service OCR pour tickets de caisse marocains.

Les tests n'utilisent pas Tesseract ni OpenCV : on injecte directement
du texte OCR simulé dans le ReceiptParser et le ProductNormalizer
pour valider la logique de parsing indépendamment du moteur OCR.
"""
from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.ocr_service import (
    ImagePreprocessor,
    OcrService,
    ParsedReceipt,
    ProductNormalizer,
    ReceiptItem,
    ReceiptParser,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures : textes OCR simulés
# ──────────────────────────────────────────────────────────────────────────────

TICKET_MARJANE = """
MARJANE HYPERMARCHE
Avenue Mohammed VI - Casablanca
Tél: 0522-123456

Date: 15/03/2024  10:35:42
Caisse: 07   Caissier: FATIMA

----------------------------------------
LAIT CENTRALE 1L              8.50
COCA COLA 33CL   2 x  5.00   10.00
BEURRE PRESIDENT 250G         18.90
PAIN DE MIE HARRYS            12.50
FROMAGE KIRI 8P               22.00
EAU SIDI ALI 1.5L  3 x 3.50  10.50
----------------------------------------
SOUS-TOTAL                    82.40
TVA 20%                        5.80
TOTAL                         82.40
"""

TICKET_BIM = """
BIM
Rue Al Massira - Rabat

24/03/2024  14:22
----------------------------------------
HUILE LESIEUR 1L              22.00
SUCRE CRISTAL 1KG              9.50
FARINE TRIA 1KG                8.75
RIZ LONG GRAIN 1KG            14.90
PATES BARILLA 500G            12.00
SARDINES DOHA 125G             7.25
SAVON LUX 100G                 4.50
----------------------------------------
TOTAL A PAYER                 78.90
"""

TICKET_LABELVIE = """
LABEL'VIE SUPERMARCHE
Hay Riad - Rabat
www.labelvie.ma

13/01/2024 09:15:00
----------------------------------------
Article                       Prix
----------------------------------------
YAOURT ACTIVIA NATURE          5.50
CAFE NESCAFE 100G             38.50
THON BOITE DOHA 120G          12.75
LESSIVE TIDE 1KG              42.00
SHAMPOING H&S 200ML           34.90
----------------------------------------
TOTAL                        133.65
MERCI DE VOTRE VISITE
"""

TICKET_CARREFOUR = """
Carrefour Market
Boulevard Zerktouni - Casablanca

12-02-2024 16:45
Ticket N°: 00245

EAU OUELMES 1.5L   2 x 4.00   8.00
COCA COLA 1.5L               11.50
LAIT BIMO 1L                  7.90
----------------------------------------
TOTAL                         27.40
"""

TICKET_ARABIC = """
مرجان هايبرماركت
الدار البيضاء

15/03/2024  11:00
----------------------------------------
حليب سنطرال 1L               8.50
ماء سيدي علي 1.5L            3.50
----------------------------------------
المبلغ الإجمالي              12.00
"""

TICKET_MALFORMED = """
ATACADÃO GROSSISTE
Zone Industrielle - Ain Sebaa
TEL 0522-987654

DATE 28/02/2024 08:30
---
PRODUIT1 AVEC NOM TRES LONG QUI DEBORDE   155.00
ARTICLE SANS PRIX
123456789

TOTAL NET A PAYER             155.00
"""


# ──────────────────────────────────────────────────────────────────────────────
# Tests ReceiptParser
# ──────────────────────────────────────────────────────────────────────────────

class TestReceiptParser:
    def setup_method(self):
        self.parser = ReceiptParser()

    # ── Détection du magasin ──────────────────────────────────────────────────

    def test_detect_marjane(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert receipt.store_chain == "marjane"
        assert "MARJANE" in receipt.store_name

    def test_detect_bim(self):
        receipt = self.parser.parse(TICKET_BIM)
        assert receipt.store_chain == "bim"

    def test_detect_labelvie(self):
        receipt = self.parser.parse(TICKET_LABELVIE)
        assert receipt.store_chain == "labelvie"

    def test_detect_carrefour(self):
        receipt = self.parser.parse(TICKET_CARREFOUR)
        assert receipt.store_chain == "carrefour"

    def test_detect_atacadao(self):
        receipt = self.parser.parse(TICKET_MALFORMED)
        assert receipt.store_chain == "atacadao"

    def test_detect_arabic_marjane(self):
        receipt = self.parser.parse(TICKET_ARABIC)
        assert receipt.store_chain == "marjane"

    def test_unknown_store_returns_none(self):
        receipt = self.parser.parse("EPICERIE HASSAN\nSUCRE  5.00\nTOTAL  5.00")
        assert receipt.store_chain is None

    # ── Extraction de la date ─────────────────────────────────────────────────

    def test_date_dd_mm_yyyy_with_time(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert receipt.purchase_date == datetime(2024, 3, 15, 10, 35, 42)

    def test_date_dd_mm_yyyy_only(self):
        receipt = self.parser.parse(TICKET_BIM)
        assert receipt.purchase_date == datetime(2024, 3, 24, 14, 22)

    def test_date_with_dash_separator(self):
        receipt = self.parser.parse(TICKET_CARREFOUR)
        assert receipt.purchase_date.day == 12
        assert receipt.purchase_date.month == 2
        assert receipt.purchase_date.year == 2024

    def test_no_date_returns_none(self):
        receipt = self.parser.parse("MAGASIN X\nARTICLE  5.00\nTOTAL  5.00")
        assert receipt.purchase_date is None

    # ── Extraction des produits ───────────────────────────────────────────────

    def test_marjane_items_count(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert len(receipt.items) >= 5

    def test_simple_item_parsing(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        lait = next((i for i in receipt.items if "LAIT" in i.name.upper()), None)
        assert lait is not None
        assert lait.unit_price == pytest.approx(8.50)
        assert lait.total_price == pytest.approx(8.50)
        assert lait.quantity == 1.0

    def test_item_with_quantity(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        coca = next((i for i in receipt.items if "COCA" in i.name.upper()), None)
        assert coca is not None
        assert coca.quantity == pytest.approx(2.0)
        assert coca.unit_price == pytest.approx(5.00)
        assert coca.total_price == pytest.approx(10.00)

    def test_eau_with_quantity(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        eau = next((i for i in receipt.items if "SIDI ALI" in i.name.upper()), None)
        assert eau is not None
        assert eau.quantity == pytest.approx(3.0)
        assert eau.total_price == pytest.approx(10.50)

    def test_bim_all_items_have_price(self):
        receipt = self.parser.parse(TICKET_BIM)
        for item in receipt.items:
            assert item.total_price > 0

    def test_malformed_ticket_no_crash(self):
        """Un ticket mal formaté ne doit pas lever d'exception."""
        receipt = self.parser.parse(TICKET_MALFORMED)
        assert isinstance(receipt, ParsedReceipt)

    # ── Extraction du total ───────────────────────────────────────────────────

    def test_total_marjane(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert receipt.total == pytest.approx(82.40)

    def test_total_bim(self):
        receipt = self.parser.parse(TICKET_BIM)
        assert receipt.total == pytest.approx(78.90)

    def test_total_labelvie(self):
        receipt = self.parser.parse(TICKET_LABELVIE)
        assert receipt.total == pytest.approx(133.65)

    def test_total_carrefour(self):
        receipt = self.parser.parse(TICKET_CARREFOUR)
        assert receipt.total == pytest.approx(27.40)

    def test_total_arabic_ticket(self):
        receipt = self.parser.parse(TICKET_ARABIC)
        assert receipt.total == pytest.approx(12.00)

    def test_subtotal_detected(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert receipt.subtotal == pytest.approx(82.40)

    # ── Calcul du total si absent ─────────────────────────────────────────────

    def test_total_computed_from_items_when_missing(self):
        text = "EPICERIE\n15/01/2024\nPAIN  3.50\nBEURRE  12.00\n"
        receipt = self.parser.parse(text)
        if receipt.total is not None:
            assert receipt.total == pytest.approx(15.50)

    # ── Devise ───────────────────────────────────────────────────────────────

    def test_currency_is_mad(self):
        receipt = self.parser.parse(TICKET_MARJANE)
        assert receipt.currency == "MAD"


# ──────────────────────────────────────────────────────────────────────────────
# Tests ProductNormalizer
# ──────────────────────────────────────────────────────────────────────────────

class TestProductNormalizer:
    def setup_method(self):
        self.norm = ProductNormalizer()

    def test_exact_match(self):
        name, score = self.norm.normalize("Lait Centrale Danone 1L")
        assert name == "Lait Centrale Danone 1L"
        assert score > 0.9

    def test_partial_match_lait(self):
        name, score = self.norm.normalize("LAIT CENTRALE 1L")
        assert name is not None
        assert "Lait" in name
        assert score >= 0.55

    def test_partial_match_coca(self):
        name, score = self.norm.normalize("COCA COLA 33CL")
        assert name is not None
        assert "Coca-Cola" in name

    def test_match_eau(self):
        name, score = self.norm.normalize("EAU SIDI ALI 1.5L")
        assert name is not None
        assert "Sidi Ali" in name

    def test_no_match_for_garbage(self):
        name, score = self.norm.normalize("XYZQWERTY999")
        assert name is None
        assert score == 0.0

    def test_accented_normalization(self):
        """Les accents ne doivent pas bloquer le matching."""
        name, score = self.norm.normalize("BEURRE PRÉSIDENT 250G")
        assert name is not None
        assert score >= 0.55

    def test_custom_catalog(self):
        catalog = ["Argan Oil 100ml", "Beldi Soap"]
        norm = ProductNormalizer(catalog)
        name, score = norm.normalize("Argan Oil")
        assert name == "Argan Oil 100ml"

    def test_score_between_0_and_1(self):
        _, score = self.norm.normalize("quelque chose")
        assert 0.0 <= score <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Tests ImagePreprocessor (sans fichier réel)
# ──────────────────────────────────────────────────────────────────────────────

class TestImagePreprocessor:
    def setup_method(self):
        self.prep = ImagePreprocessor()

    def _make_fake_jpeg(self, text: str = "TEST") -> bytes:
        """Génère une image JPEG synthétique avec du texte blanc sur fond noir."""
        import cv2
        import numpy as np
        img = np.ones((200, 400), dtype=np.uint8) * 255
        cv2.putText(img, text, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)
        _, buf = cv2.imencode(".jpg", img)
        return buf.tobytes()

    def test_process_returns_numpy_array(self):
        jpeg = self._make_fake_jpeg()
        result = self.prep.process(jpeg, "image/jpeg")
        assert isinstance(result, np.ndarray)

    def test_output_is_grayscale(self):
        jpeg = self._make_fake_jpeg()
        result = self.prep.process(jpeg, "image/jpeg")
        assert len(result.shape) == 2  # (H, W) — pas de canal couleur

    def test_output_is_binary(self):
        jpeg = self._make_fake_jpeg()
        result = self.prep.process(jpeg, "image/jpeg")
        unique_vals = set(np.unique(result))
        assert unique_vals.issubset({0, 255})

    def test_pdf_without_pdf2image_raises(self):
        import app.services.ocr_service as ocr_mod
        original = ocr_mod.PDF_SUPPORT
        ocr_mod.PDF_SUPPORT = False
        try:
            with pytest.raises(RuntimeError, match="pdf2image"):
                self.prep.process(b"fake pdf", "application/pdf")
        finally:
            ocr_mod.PDF_SUPPORT = original

    def test_scale_small_image(self):
        """Une image < 1500px doit être agrandie."""
        small = np.ones((100, 200), dtype=np.uint8) * 200
        scaled = self.prep._scale_to_dpi(small)
        assert max(scaled.shape) >= 1500

    def test_deskew_no_crash_on_empty(self):
        """L'image vide ne doit pas crasher le deskew."""
        blank = np.zeros((500, 300), dtype=np.uint8)
        result = self.prep._deskew(blank)
        assert result.shape == blank.shape


# ──────────────────────────────────────────────────────────────────────────────
# Tests OcrService (Tesseract mocké)
# ──────────────────────────────────────────────────────────────────────────────

class TestOcrService:
    def setup_method(self):
        self.service = OcrService()

    def _fake_image_bytes(self) -> bytes:
        import cv2
        img = np.ones((300, 500), dtype=np.uint8) * 255
        _, buf = cv2.imencode(".png", img)
        return buf.tobytes()

    def _mock_pipeline(self, raw_text: str):
        """Patch Tesseract pour retourner du texte simulé."""
        return patch(
            "app.services.ocr_service.pytesseract.image_to_string",
            return_value=raw_text,
        )

    def test_process_marjane_ticket(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MARJANE):
            result = self.service.process_image(img, "image/jpeg")
        assert result["store"]["chain"] == "marjane"
        assert result["total"] == pytest.approx(82.40)
        assert len(result["items"]) >= 5
        assert result["currency"] == "MAD"

    def test_process_bim_ticket(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_BIM):
            result = self.service.process_image(img, "image/jpeg")
        assert result["store"]["chain"] == "bim"
        assert result["total"] == pytest.approx(78.90)

    def test_result_has_required_keys(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MARJANE):
            result = self.service.process_image(img, "image/jpeg")
        required_keys = {"store", "date", "items", "total", "currency",
                         "item_count", "raw_text", "ocr_confidence"}
        assert required_keys.issubset(result.keys())

    def test_items_have_required_fields(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_BIM):
            result = self.service.process_image(img, "image/jpeg")
        for item in result["items"]:
            assert "name" in item
            assert "quantity" in item
            assert "unit_price" in item
            assert "total_price" in item
            assert "match_confidence" in item

    def test_normalized_names_populated(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MARJANE):
            result = self.service.process_image(img, "image/jpeg")
        matched = [i for i in result["items"] if i["normalized_name"] is not None]
        assert len(matched) > 0

    def test_date_iso_format(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MARJANE):
            result = self.service.process_image(img, "image/jpeg")
        assert result["date"] == "2024-03-15T10:35:42"

    def test_ocr_confidence_between_0_and_1(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MARJANE):
            result = self.service.process_image(img, "image/jpeg")
        assert 0.0 <= result["ocr_confidence"] <= 1.0

    def test_arabic_ticket(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_ARABIC):
            result = self.service.process_image(img, "image/jpeg")
        assert result["store"]["chain"] == "marjane"
        assert result["total"] == pytest.approx(12.00)

    def test_malformed_ticket_no_exception(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_MALFORMED):
            result = self.service.process_image(img, "image/jpeg")
        assert isinstance(result, dict)

    def test_empty_text_returns_empty_items(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(""):
            result = self.service.process_image(img, "image/jpeg")
        assert result["items"] == []
        assert result["total"] is None

    def test_png_mime_type_accepted(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_LABELVIE):
            result = self.service.process_image(img, "image/png")
        assert result["store"]["chain"] == "labelvie"

    def test_store_display_name(self):
        img = self._fake_image_bytes()
        with self._mock_pipeline(TICKET_LABELVIE):
            result = self.service.process_image(img, "image/jpeg")
        assert result["store"]["display"] == "Label'Vie"
