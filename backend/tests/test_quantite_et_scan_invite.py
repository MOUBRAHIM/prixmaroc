"""
Trois défauts signalés depuis l'application, et leurs gardes.

1. « Input should be a valid integer, got a number with a fractional part »
   à l'enregistrement d'une liste IA : le générateur raisonne en poids pour
   ce qui se vend au poids, et la quantité n'acceptait que des entiers.

2. « Field required » au scan d'un ticket : le corps était bien un multipart
   mais l'en-tête annonçait du JSON, donc le serveur ne voyait aucun fichier.
   Côté serveur, la garde est simplement que le champ s'appelle « file ».

3. Erreur 500 pour un invité qui scanne : la ligne était écrite avec un
   user_id nul que la colonne refuse, alors que le scan d'un invité n'a pas
   à être conservé.
"""
import pytest

from app.schemas.ocr_scan import OcrScanRead
from app.schemas.shopping_list import ShoppingListItemCreate, ShoppingListItemUpdate


class TestQuantiteDecimale:
    @pytest.mark.parametrize("quantite", [0.5, 1.5, 2.25, 3])
    def test_accepte_une_quantite_au_poids(self, quantite):
        """« 1,5 kg de viande » est une quantité ordinaire au souk."""
        item = ShoppingListItemCreate(custom_name="Viande hachée", quantity=quantite)
        assert item.quantity == pytest.approx(quantite)

    def test_accepte_une_quantite_decimale_en_modification(self):
        assert ShoppingListItemUpdate(quantity=1.5).quantity == pytest.approx(1.5)

    def test_quantite_par_defaut(self):
        assert ShoppingListItemCreate(custom_name="Pain").quantity == 1


class TestScanInvite:
    def test_un_scan_sans_compte_se_valide(self):
        """
        Sans compte, le scan n'est pas enregistré : il n'a donc ni identifiant
        ni propriétaire. Les exiger faisait échouer la réponse après une
        lecture pourtant réussie.
        """
        lu = OcrScanRead.model_validate({
            "id": None,
            "user_id": None,
            "image_url": "ticket.jpg",
            "status": "done",
            "created_at": "2026-10-02T12:00:00Z",
            "parsed_data": {"items": [], "moteur": "vision"},
        })
        assert lu.id is None
        assert lu.user_id is None
        assert lu.status == "done"

    def test_un_scan_enregistre_garde_ses_identifiants(self):
        lu = OcrScanRead.model_validate({
            "id": 42,
            "user_id": 7,
            "image_url": "ticket.jpg",
            "status": "done",
            "created_at": "2026-10-02T12:00:00Z",
        })
        assert (lu.id, lu.user_id) == (42, 7)


class TestEndpointScan:
    """Le champ du fichier doit rester « file » : c'est lui que l'app envoie."""

    def test_le_champ_attendu_sappelle_file(self):
        from app.routers.ocr import scan_receipt
        import inspect

        parametres = inspect.signature(scan_receipt).parameters
        assert "file" in parametres
