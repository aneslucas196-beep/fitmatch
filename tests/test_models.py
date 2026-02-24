"""Tests des modèles Pydantic."""
import pytest
from pydantic import ValidationError

from models.booking import (
    ConfirmBookingRequest,
    CancelBookingRequest,
    CoachBookingRequest,
    DeleteBookingRequest,
)
from models.auth import LoginRequest, SignupRequest


def test_confirm_booking_request_valid():
    """ConfirmBookingRequest accepte des données valides."""
    data = {
        "client_name": "Jean Dupont",
        "client_email": "jean@example.com",
        "coach_name": "Marie Martin",
        "gym_name": "Basic-Fit Paris",
        "date": "2026-03-15",
        "time": "10:00",
        "service": "Séance coaching",
        "duration": "60 min",
        "price": "50€",
    }
    req = ConfirmBookingRequest(**data)
    assert req.client_email == "jean@example.com"
    assert req.coach_name == "Marie Martin"


def test_confirm_booking_request_invalid_email():
    """ConfirmBookingRequest rejette un email invalide."""
    with pytest.raises(ValidationError):
        ConfirmBookingRequest(
            client_name="Jean",
            client_email="invalid-email",
            coach_name="Marie",
            gym_name="Salle",
            date="2026-03-15",
            time="10:00",
            service="Coaching",
            duration="60",
            price="50",
        )


def test_coach_booking_request_valid():
    """CoachBookingRequest accepte confirm et reject."""
    req = CoachBookingRequest(
        coach_email="coach@example.com",
        booking_id="abc123",
        action="confirm",
    )
    assert req.action == "confirm"
    req2 = CoachBookingRequest(
        coach_email="coach@example.com",
        booking_id="abc123",
        action="reject",
    )
    assert req2.action == "reject"


def test_delete_booking_request_valid():
    """DeleteBookingRequest valide."""
    req = DeleteBookingRequest(
        coach_email="coach@example.com",
        booking_id="abc123",
    )
    assert req.booking_id == "abc123"


def test_login_request_valid():
    """LoginRequest valide."""
    req = LoginRequest(email="user@example.com", password="secret123")
    assert req.email == "user@example.com"


def test_login_request_empty_password():
    """LoginRequest rejette un mot de passe vide."""
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="")


def test_signup_request_valid():
    """SignupRequest valide."""
    req = SignupRequest(
        email="new@example.com",
        password="password123",
        full_name="New User",
        role="client",
    )
    assert req.role == "client"


def test_signup_request_password_too_short():
    """SignupRequest exige au moins 8 caractères pour le mot de passe."""
    with pytest.raises(ValidationError):
        SignupRequest(
            email="new@example.com",
            password="short",
            full_name="New User",
        )
