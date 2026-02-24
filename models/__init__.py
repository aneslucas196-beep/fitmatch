"""
Modèles Pydantic partagés pour FitMatch.
Centralise les schémas de validation des requêtes/réponses API.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr


class ConfirmBookingRequest(BaseModel):
    """Schéma de confirmation de réservation."""
    client_name: str
    client_email: EmailStr
    coach_name: str
    coach_email: Optional[EmailStr] = None
    gym_name: str
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str
    time: str
    service: str
    duration: str
    price: str
    coach_photo: Optional[str] = None
    lang: Optional[str] = "fr"


class CancelBookingRequest(BaseModel):
    """Schéma d'annulation de réservation."""
    client_name: str
    client_email: EmailStr
    coach_name: str
    coach_email: Optional[EmailStr] = None
    gym_name: str
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str
    time: str
    service: str
    duration: str
    price: str
    coach_photo: Optional[str] = None
    booking_url: Optional[str] = None
    booking_id: Optional[str] = None
    lang: Optional[str] = "fr"


class CoachBookingRequest(BaseModel):
    """Schéma de réponse coach (confirmer/refuser)."""
    coach_email: EmailStr
    booking_id: str
    action: str  # "confirm" ou "reject"


class DeleteBookingRequest(BaseModel):
    """Schéma de suppression de réservation."""
    coach_email: EmailStr
    booking_id: str
