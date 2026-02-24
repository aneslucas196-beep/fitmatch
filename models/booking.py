"""Modèles Pydantic pour les réservations."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class ConfirmBookingRequest(BaseModel):
    """Demande de confirmation de réservation."""
    client_name: str = Field(..., min_length=1, max_length=200)
    client_email: EmailStr
    coach_name: str = Field(..., min_length=1, max_length=200)
    coach_email: Optional[EmailStr] = None
    gym_name: str = Field(..., min_length=1, max_length=300)
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str = Field(..., min_length=8, max_length=20)
    time: str = Field(..., min_length=1, max_length=20)
    service: str = Field(..., min_length=1, max_length=200)
    duration: str = Field(..., min_length=1, max_length=20)
    price: str = Field(..., min_length=1, max_length=20)
    coach_photo: Optional[str] = None
    lang: Optional[str] = "fr"


class CancelBookingRequest(BaseModel):
    """Demande d'annulation de réservation."""
    client_name: str = Field(..., min_length=1, max_length=200)
    client_email: EmailStr
    coach_name: str = Field(..., min_length=1, max_length=200)
    coach_email: Optional[EmailStr] = None
    gym_name: str = Field(..., min_length=1, max_length=300)
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str = Field(..., min_length=8, max_length=20)
    time: str = Field(..., min_length=1, max_length=20)
    service: str = Field(..., min_length=1, max_length=200)
    duration: str = Field(..., min_length=1, max_length=20)
    price: str = Field(..., min_length=1, max_length=20)
    coach_photo: Optional[str] = None
    booking_url: Optional[str] = None
    booking_id: Optional[str] = None
    lang: Optional[str] = "fr"


class CoachBookingRequest(BaseModel):
    """Demande du coach (confirmer/refuser réservation)."""
    coach_email: EmailStr
    booking_id: str = Field(..., min_length=1, max_length=50)
    action: str  # "confirm" ou "reject"


class DeleteBookingRequest(BaseModel):
    """Demande de suppression de réservation par le coach."""
    coach_email: EmailStr
    booking_id: str = Field(..., min_length=1, max_length=50)
