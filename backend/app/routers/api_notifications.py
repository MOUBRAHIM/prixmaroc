"""
Router /api/notifications

POST   /api/notifications/register   Enregistre le token FCM
DELETE /api/notifications/register   Supprime le token (déconnexion)
POST   /api/notifications/test       Notification de test (dev)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.services.notification_service import PushNotification, notification_service
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class RegisterTokenPayload(BaseModel):
    fcm_token: str = Field(..., min_length=10)
    platform: str = Field(default="unknown", description="ios | android | web")


class TestNotifPayload(BaseModel):
    title: str = Field(default="Test PrixMaroc 🇲🇦")
    body: str = Field(default="Votre application fonctionne correctement !")


@router.post(
    "/register",
    status_code=status.HTTP_200_OK,
    summary="Enregistrer le token FCM",
)
async def register_token(
    payload: RegisterTokenPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.fcm_token = payload.fcm_token
    db.add(current_user)
    await db.commit()
    return {
        "status": "registered",
        "user_id": current_user.id,
        "platform": payload.platform,
        "message": "Token FCM enregistré avec succès",
    }


@router.delete(
    "/register",
    status_code=status.HTTP_200_OK,
    summary="Supprimer le token FCM",
)
async def unregister_token(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.fcm_token = None
    db.add(current_user)
    await db.commit()
    return {
        "status": "unregistered",
        "user_id": current_user.id,
        "message": "Token FCM supprimé",
    }


@router.post(
    "/test",
    status_code=status.HTTP_200_OK,
    summary="Notification de test (développement)",
)
async def send_test_notification(
    payload: TestNotifPayload,
    current_user: User = Depends(get_current_user),
):
    notif = PushNotification(
        title=payload.title,
        body=payload.body,
        notif_type="LISTE_RAPPEL",
    )
    sent = await notification_service.send_to_token("MOCK_TOKEN_DEV", notif)
    return {
        "sent": sent,
        "user_id": current_user.id,
        "title": payload.title,
        "body": payload.body,
        "note": "En production, utilisez le token FCM réel de l'appareil.",
    }
