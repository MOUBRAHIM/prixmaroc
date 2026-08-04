"""
Service de notifications push — PrixMaroc
Utilise Firebase Cloud Messaging (FCM) via firebase-admin.

Configuration .env :
  FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json
  ou
  FIREBASE_CREDENTIALS_JSON='{...}'  (pour CI/CD)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

NotifType = Literal["PROMO_ALERTE", "LISTE_RAPPEL", "ECONOMIE_HEBDO", "PRIX_BAISSE"]


@dataclass
class PushNotification:
    title: str
    body: str
    notif_type: NotifType
    data: dict | None = None


class NotificationService:
    """
    Service FCM avec lazy-init et mode dégradé (log) si Firebase absent.
    Max 2 notifications/jour/utilisateur (à implémenter côté scheduler).
    """

    def __init__(self) -> None:
        self._app = None
        self._initialized = False

    def _try_init(self) -> bool:
        if self._initialized:
            return self._app is not None
        self._initialized = True

        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "")

        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials  # type: ignore

            if cred_json:
                cred = credentials.Certificate(json.loads(cred_json))
            elif cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                logger.warning(
                    "Firebase non configuré — notifications désactivées. "
                    "Définissez FIREBASE_CREDENTIALS_PATH ou FIREBASE_CREDENTIALS_JSON."
                )
                return False

            if not firebase_admin._apps:  # type: ignore
                self._app = firebase_admin.initialize_app(cred)
            else:
                self._app = firebase_admin.get_app()

            logger.info("Firebase Admin SDK initialisé.")
            return True

        except ImportError:
            logger.warning("firebase-admin non installé — notifications désactivées.")
            return False
        except Exception as exc:
            logger.error(f"Erreur init Firebase : {exc}")
            return False

    async def send_to_token(self, token: str, notif: PushNotification) -> bool:
        if not self._try_init():
            logger.info(f"[NOTIF MOCK] {token[:20]}… | {notif.title} | {notif.body}")
            return False
        try:
            from firebase_admin import messaging  # type: ignore
            msg = messaging.Message(
                notification=messaging.Notification(title=notif.title, body=notif.body),
                data={"type": notif.notif_type, **(notif.data or {})},
                token=token,
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        icon="ic_notification",
                        color="#16a34a",
                        channel_id="prixmaroc_main",
                    ),
                    priority="high",
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1)
                    )
                ),
            )
            response = messaging.send(msg)
            logger.info(f"Notification envoyée : {response}")
            return True
        except Exception as exc:
            logger.error(f"Erreur envoi notification : {exc}")
            return False

    async def send_to_multiple(self, tokens: list[str], notif: PushNotification) -> dict:
        if not tokens:
            return {"sent": 0, "failed": 0}
        if not self._try_init():
            logger.info(f"[NOTIF MOCK] Broadcast → {len(tokens)} tokens | {notif.title}")
            return {"sent": 0, "failed": len(tokens)}
        try:
            from firebase_admin import messaging  # type: ignore
            messages = [
                messaging.Message(
                    notification=messaging.Notification(title=notif.title, body=notif.body),
                    data={"type": notif.notif_type, **(notif.data or {})},
                    token=t,
                )
                for t in tokens
            ]
            sent = failed = 0
            for i in range(0, len(messages), 500):
                resp = messaging.send_each(messages[i:i + 500])
                sent += resp.success_count
                failed += resp.failure_count
            logger.info(f"Broadcast : {sent} envoyés, {failed} échoués")
            return {"sent": sent, "failed": failed}
        except Exception as exc:
            logger.error(f"Erreur broadcast : {exc}")
            return {"sent": 0, "failed": len(tokens)}

    # ── Helpers métier ──────────────────────────────────────────────────────────

    def make_promo_alert(self, product_name: str, store_name: str, promo_price: float, regular_price: float) -> PushNotification:
        discount = round((1 - promo_price / regular_price) * 100)
        return PushNotification(
            title=f"🏷️ Promo -{discount}% — {product_name}",
            body=f"{promo_price:.2f} MAD chez {store_name} (au lieu de {regular_price:.2f} MAD)",
            notif_type="PROMO_ALERTE",
            data={"product_name": product_name, "store_name": store_name},
        )

    def make_liste_rappel(self, budget: float | None = None) -> PushNotification:
        body = "N'oubliez pas vos courses de la semaine !"
        if budget:
            body += f" Budget suggéré : {budget:.0f} MAD"
        return PushNotification(
            title="🛒 Rappel — Vos courses de la semaine",
            body=body,
            notif_type="LISTE_RAPPEL",
        )

    def make_economie_hebdo(self, montant: float) -> PushNotification:
        return PushNotification(
            title="💰 Bravo ! Économies de la semaine",
            body=f"Vous avez économisé {montant:.2f} MAD grâce à PrixMaroc 🎉",
            notif_type="ECONOMIE_HEBDO",
            data={"montant": str(montant)},
        )

    def make_prix_baisse(self, product_name: str, store_name: str, new_price: float) -> PushNotification:
        return PushNotification(
            title=f"📉 Baisse de prix — {product_name}",
            body=f"Maintenant à {new_price:.2f} MAD chez {store_name}",
            notif_type="PRIX_BAISSE",
            data={"product_name": product_name, "store_name": store_name},
        )


notification_service = NotificationService()
