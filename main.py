from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn
import os

from utils import (
    geocode_city, 
    search_coaches_mock, 
    get_coach_by_id_mock, 
    get_transformations_by_coach_mock,
    get_supabase_client
)

app = FastAPI()

# Configuration des templates et fichiers statiques
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Client Supabase (si disponible)
supabase = get_supabase_client()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Page d'accueil avec formulaire de recherche."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_coaches(
    request: Request,
    specialty: Optional[str] = None,
    city: str = "",
    radius_km: int = 25
):
    """Recherche de coachs avec géolocalisation."""
    
    # Géocoder la ville
    coords = geocode_city(city) if city else None
    user_lat, user_lng = coords if coords else (None, None)
    
    # Rechercher les coachs
    if supabase:
        # TODO: Utiliser Supabase quand configuré
        coaches = search_coaches_mock(specialty, user_lat, user_lng, radius_km)
    else:
        coaches = search_coaches_mock(specialty, user_lat, user_lng, radius_km)
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "coaches": coaches,
        "specialty": specialty,
        "city": city,
        "radius_km": radius_km
    })

@app.get("/coach/{coach_id}", response_class=HTMLResponse)
async def coach_profile(request: Request, coach_id: int):
    """Affichage du profil d'un coach."""
    
    # Récupérer le coach
    if supabase:
        # TODO: Utiliser Supabase quand configuré
        coach = get_coach_by_id_mock(coach_id)
        transformations = get_transformations_by_coach_mock(coach_id)
    else:
        coach = get_coach_by_id_mock(coach_id)
        transformations = get_transformations_by_coach_mock(coach_id)
    
    if not coach:
        raise HTTPException(status_code=404, detail="Coach non trouvé")
    
    return templates.TemplateResponse("coach.html", {
        "request": request,
        "coach": coach,
        "transformations": transformations
    })

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    """Formulaire d'inscription."""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    """Traitement de l'inscription."""
    # TODO: Implémenter l'enregistrement en base
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Formulaire de connexion."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Traitement de la connexion."""
    # TODO: Implémenter l'authentification
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.get("/logout")
async def logout():
    """Déconnexion."""
    # TODO: Implémenter la déconnexion
    return RedirectResponse(url="/", status_code=303)

@app.get("/coach/portal", response_class=HTMLResponse)
async def coach_portal(request: Request):
    """Espace coach - gestion du profil."""
    # TODO: Vérifier l'authentification et le role='coach'
    
    # Pour la démo, utiliser le premier coach mock
    coach = get_coach_by_id_mock(1)
    transformations = get_transformations_by_coach_mock(1)
    
    return templates.TemplateResponse("coach_portal.html", {
        "request": request,
        "coach": coach,
        "transformations": transformations
    })

@app.post("/coach/portal")
async def coach_portal_update(
    request: Request,
    full_name: str = Form(...),
    bio: str = Form(""),
    city: str = Form(""),
    instagram_url: str = Form(""),
    price_from: Optional[int] = Form(None),
    radius_km: int = Form(25)
):
    """Mise à jour du profil coach."""
    # TODO: Implémenter la mise à jour en base
    
    # Géocoder la nouvelle ville si fournie
    if city:
        coords = geocode_city(city)
        # TODO: Sauvegarder les coordonnées
    
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.post("/coach/specialties")
async def coach_specialties_update(
    request: Request,
    specialties: list = Form([])
):
    """Mise à jour des spécialités du coach."""
    # TODO: Implémenter la mise à jour en base
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.post("/coach/transformations")
async def coach_transformations_add(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    duration_weeks: Optional[int] = Form(None),
    consent: bool = Form(False)
):
    """Ajout d'une transformation."""
    # TODO: Implémenter l'ajout en base
    if not consent:
        raise HTTPException(status_code=400, detail="Consentement requis")
    
    return RedirectResponse(url="/coach/portal", status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)