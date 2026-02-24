"""Modèles Pydantic pour l'authentification."""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Demande de connexion API."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class SignupRequest(BaseModel):
    """Demande d'inscription."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: str = Field(default="client", pattern="^(client|coach)$")
