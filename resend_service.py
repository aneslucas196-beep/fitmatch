# Service email avec Resend API
import os
import requests
from typing import Optional

# Liens réseaux sociaux FitMatch
INSTAGRAM_URL = "https://www.instagram.com/fitmatch__?igsh=MXkwcTE5dmFhaDQ3OQ%3D%3D&utm_source=qr"
FACEBOOK_URL = "https://www.facebook.com/share/17f5yGSk86/?mibextid=wwXIfr"

# Footer social commun à tous les emails (utilise images PNG pour compatibilité Gmail)
SOCIAL_FOOTER_HTML = f'''
<!-- Suivez-nous -->
<div style="padding:25px; background:#f9f9f9; border-top:1px solid #eee; text-align:center;">
    <p style="margin:0 0 15px 0; font-size:15px; color:#374151; font-weight:500;">Suivez-nous</p>
    <table align="center" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="padding:0 8px;">
                <a href="{FACEBOOK_URL}" target="_blank" style="text-decoration:none;">
                    <img src="https://cdn-icons-png.flaticon.com/512/733/733547.png" alt="Facebook" width="36" height="36" style="display:block; border:0;">
                </a>
            </td>
            <td style="padding:0 8px;">
                <a href="{INSTAGRAM_URL}" target="_blank" style="text-decoration:none;">
                    <img src="https://cdn-icons-png.flaticon.com/512/2111/2111463.png" alt="Instagram" width="36" height="36" style="display:block; border:0;">
                </a>
            </td>
        </tr>
    </table>
</div>
'''

def send_otp_email_resend(to_email: str, otp_code: str, full_name: Optional[str] = None) -> dict:
    """
    Envoie un code OTP par email via Resend API
    Retourne un dictionnaire avec success (bool) et des détails pour le debugging
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    # Utiliser domaine vérifié fitmatch.fr par défaut
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('SITE_URL', 'http://localhost:5000')
    
    print(f"🔧 Configuration email:")
    print(f"  - RESEND_API_KEY: {'✅ Configuré' if resend_key else '❌ Manquant'}")
    print(f"  - MAIL_FROM: {mail_from}")
    print(f"  - SITE_URL: {site_url}")
    print(f"  - Destinataire: {to_email}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        print(f"📧 Email simulé envoyé à {to_email}: Code OTP = {otp_code}")
        return {"success": True, "mode": "demo", "message": "Email simulé"}
    
    try:
        # Prénom pour personnaliser l'email
        first_name = full_name.split()[0] if full_name else "utilisateur"
        
        # Contenu HTML de l'email - Style FitMatch
        html_content = f"""
        <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc;">
            <div style="background: linear-gradient(135deg, #008f57 0%, #00b36b 100%); padding: 40px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 32px; font-weight: 700;">FitMatch</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">Votre plateforme de coaching fitness</p>
            </div>
            
            <div style="padding: 40px; background: white;">
                <h2 style="color: #1e293b; margin-bottom: 20px; font-size: 22px;">Bonjour {first_name} !</h2>
                
                <p style="color: #64748b; font-size: 16px; line-height: 1.6;">
                    Bienvenue sur FitMatch ! Voici votre code de vérification pour activer votre compte :
                </p>
                
                <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 2px solid #008f57; border-radius: 12px; padding: 30px; text-align: center; margin: 30px 0;">
                    <p style="margin: 0 0 10px 0; color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Votre code</p>
                    <span style="font-size: 42px; font-weight: 700; color: #008f57; letter-spacing: 10px;">{otp_code}</span>
                </div>
                
                <div style="background: #fef3c7; border-radius: 8px; padding: 15px; margin-bottom: 25px;">
                    <p style="color: #92400e; font-size: 14px; margin: 0;">
                        ⏱️ Ce code expire dans <strong>10 minutes</strong>
                    </p>
                </div>
                
                <p style="color: #64748b; font-size: 14px; line-height: 1.8;">
                    Saisissez ce code sur la page de vérification pour activer votre compte et commencer à utiliser FitMatch.
                </p>
                
                <p style="color: #94a3b8; font-size: 13px; line-height: 1.6; margin-top: 30px;">
                    Si vous n'avez pas créé de compte sur FitMatch, ignorez simplement cet email.
                </p>
            </div>
            
            {SOCIAL_FOOTER_HTML}
            
            <div style="padding: 20px; background: #f8fafc; text-align: center;">
                <p style="color: #008f57; font-size: 16px; font-weight: 600; margin: 0 0 5px 0;">FitMatch</p>
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    La plateforme qui connecte coachs et clients
                </p>
            </div>
        </div>
        """
        
        # Contenu texte alternatif
        text_content = f"""
        Bonjour {first_name} !
        
        Voici votre code de vérification Fitmatch : {otp_code}
        
        Ce code expire dans 10 minutes.
        Saisissez-le sur la page de vérification pour activer votre compte.
        
        Si vous n'avez pas demandé ce code, ignorez cet email.
        
        L'équipe Fitmatch
        """
        
        # Préparer la requête vers l'API Resend
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"Votre code de vérification : {otp_code}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi requête Resend...")
        print(f"  - URL: {url}")
        print(f"  - Headers: Authorization présent, Content-Type: {headers['Content-Type']}")
        print(f"  - Payload: from={data['from']}, to={data['to']}, subject={data['subject']}")
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        print(f"📥 Réponse Resend:")
        print(f"  - Status: {response.status_code}")
        print(f"  - Headers: {dict(response.headers)}")
        print(f"  - Body: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email OTP envoyé via Resend à {to_email} (ID: {email_id})")
            return {
                "success": True, 
                "mode": "resend", 
                "email_id": email_id,
                "message": "Email envoyé avec succès"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False, 
                "mode": "resend", 
                "error": error_msg,
                "status_code": response.status_code,
                "response_body": response.text
            }
        
    except Exception as e:
        error_msg = f"Erreur envoi email Resend: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False, 
            "mode": "error", 
            "error": error_msg
        }


def send_booking_confirmation_email(
    to_email: str,
    client_name: str,
    coach_name: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str,
    duration: str,
    price: str,
    coach_photo: Optional[str] = None,
    reservation_id: Optional[str] = None
) -> dict:
    """
    Envoie un email de confirmation de réservation style Planity via Resend API
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    
    # Ajouter https:// si nécessaire
    if site_url and not site_url.startswith('http'):
        site_url = f"https://{site_url}"
    
    reservation_url = f"{site_url}/account"
    
    print(f"📧 Préparation email confirmation réservation:")
    print(f"  - Client: {client_name} ({to_email})")
    print(f"  - Coach: {coach_name}")
    print(f"  - Salle: {gym_name}")
    print(f"  - Date: {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email confirmation simulé"}
    
    # Image de couverture - convertir le chemin relatif en URL complète
    default_image = "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&h=300&fit=crop"
    if coach_photo and coach_photo.startswith('/'):
        # C'est un chemin relatif, le convertir en URL complète
        cover_image = f"{site_url}{coach_photo}"
    elif coach_photo and coach_photo.startswith('http'):
        cover_image = coach_photo
    else:
        cover_image = default_image
    
    print(f"  - Photo coach: {cover_image}")
    
    # Prénom du client
    first_name = client_name.split()[0] if client_name else "Client"
    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0; padding:0; font-family: 'Inter', Arial, sans-serif; background-color:#f5f5f5;">
            <div style="max-width:600px; margin:0 auto; background:white;">
                
                <!-- Header avec confirmation -->
                <div style="background:#111; padding:30px; text-align:center;">
                    <div style="display:inline-block; background:#22c55e; color:white; padding:8px 20px; border-radius:50px; font-size:14px; font-weight:600;">
                        ✓ Réservation confirmée
                    </div>
                </div>
                
                <!-- Bouton principal -->
                <div style="padding:25px; text-align:center; background:#fafafa; border-bottom:1px solid #eee;">
                    <a href="{reservation_url}" 
                       style="display:inline-block; background:#111; color:white; padding:14px 40px; text-decoration:none; border-radius:8px; font-weight:600; font-size:15px;">
                        Voir ma réservation
                    </a>
                </div>
                
                <!-- Image de couverture -->
                <div style="padding:0;">
                    <img src="{cover_image}" alt="Photo" style="width:100%; height:200px; object-fit:cover; display:block;"/>
                </div>
                
                <!-- Détails de la réservation -->
                <div style="padding:30px;">
                    
                    <!-- Nom de la salle -->
                    <h2 style="margin:0 0 5px 0; font-size:22px; font-weight:700; color:#111;">
                        {gym_name}
                    </h2>
                    
                    <!-- Date et coach -->
                    <p style="margin:0 0 25px 0; font-size:16px; color:#111;">
                        <strong>{date_str}</strong> à <strong>{time_str}</strong><br>
                        <span style="color:#666;">Avec {coach_name}</span>
                    </p>
                    
                    <!-- Séparateur -->
                    <hr style="border:none; border-top:1px solid #eee; margin:25px 0;">
                    
                    <!-- Adresse -->
                    <div style="margin-bottom:25px;">
                        <h3 style="margin:0 0 8px 0; font-size:13px; text-transform:uppercase; color:#888; letter-spacing:1px;">
                            📍 Adresse
                        </h3>
                        <p style="margin:0; font-size:15px; color:#333; line-height:1.5;">
                            {gym_address}
                        </p>
                    </div>
                    
                    <!-- Prestation -->
                    <div style="margin-bottom:25px;">
                        <h3 style="margin:0 0 8px 0; font-size:13px; text-transform:uppercase; color:#888; letter-spacing:1px;">
                            💪 Prestation
                        </h3>
                        <p style="margin:0; font-size:15px; color:#333;">
                            {service_name}<br>
                            <span style="color:#666;">{duration} • {price}</span>
                        </p>
                    </div>
                    
                    <!-- Séparateur -->
                    <hr style="border:none; border-top:1px solid #eee; margin:25px 0;">
                    
                    <!-- Boutons d'action -->
                    <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px;">
                        <tr>
                            <td width="32%" style="text-align:center; padding:5px;">
                                <a href="{reservation_url}" style="display:block; background:#f5f5f5; color:#333; padding:12px 0; text-decoration:none; border-radius:8px; font-size:13px;">
                                    📅 Calendrier
                                </a>
                            </td>
                            <td width="32%" style="text-align:center; padding:5px;">
                                <a href="{reservation_url}" style="display:block; background:#f5f5f5; color:#333; padding:12px 0; text-decoration:none; border-radius:8px; font-size:13px;">
                                    ✏️ Modifier
                                </a>
                            </td>
                            <td width="32%" style="text-align:center; padding:5px;">
                                <a href="{reservation_url}" style="display:block; background:#fee2e2; color:#dc2626; padding:12px 0; text-decoration:none; border-radius:8px; font-size:13px;">
                                    ❌ Annuler
                                </a>
                            </td>
                        </tr>
                    </table>
                </div>
                
                {SOCIAL_FOOTER_HTML}
                
                <!-- Footer -->
                <div style="padding:20px; background:#f9f9f9; text-align:center;">
                    <p style="margin:0 0 10px 0; font-size:18px; font-weight:700; color:#111;">
                        Fitmatch
                    </p>
                    <p style="margin:0; font-size:12px; color:#888;">
                        Votre plateforme de coaching fitness<br>
                        <a href="{site_url}" style="color:#3b82f6; text-decoration:none;">fitmatch.fr</a>
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        ✓ Réservation confirmée
        
        Bonjour {first_name} !
        
        Votre réservation est confirmée :
        
        📍 {gym_name}
        📅 {date_str} à {time_str}
        👤 Avec {coach_name}
        
        Adresse : {gym_address}
        
        Prestation : {service_name}
        Durée : {duration}
        Prix : {price}
        
        Voir votre réservation : {reservation_url}
        
        L'équipe Fitmatch
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"✓ Réservation confirmée - {gym_name} le {date_str}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi email confirmation via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email confirmation envoyé à {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Email de confirmation envoyé"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi email confirmation: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_cancellation_email(
    to_email: str,
    client_name: str,
    coach_name: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str,
    duration: str,
    price: str,
    coach_photo: Optional[str] = None,
    booking_url: Optional[str] = None
) -> dict:
    """
    Envoie un email d'annulation de réservation style Planity via Resend API
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    
    if site_url and not site_url.startswith('http'):
        site_url = f"https://{site_url}"
    
    if not booking_url:
        booking_url = f"{site_url}/"
    
    print(f"📧 Préparation email annulation:")
    print(f"  - Client: {client_name} ({to_email})")
    print(f"  - Coach: {coach_name}")
    print(f"  - Salle: {gym_name}")
    print(f"  - Date: {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email annulation simulé"}
    
    # Image de couverture
    default_image = "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&h=300&fit=crop"
    if coach_photo and coach_photo.startswith('/'):
        cover_image = f"{site_url}{coach_photo}"
    elif coach_photo and coach_photo.startswith('http'):
        cover_image = coach_photo
    else:
        cover_image = default_image
    
    first_name = client_name.split()[0] if client_name else "Client"
    
    # Lien Google Maps
    maps_url = f"https://www.google.com/maps/search/?api=1&query={gym_address.replace(' ', '+')}" if gym_address else "#"
    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0; padding:0; font-family: 'Inter', Arial, sans-serif; background-color:#f5f5f5;">
            <div style="max-width:600px; margin:0 auto; background:white;">
                
                <!-- Header annulation -->
                <div style="background:#111; padding:30px; text-align:center;">
                    <div style="display:inline-block; background:#ef4444; color:white; padding:8px 20px; border-radius:50px; font-size:14px; font-weight:600;">
                        ✕ Rendez-vous annulé
                    </div>
                </div>
                
                <!-- Message principal -->
                <div style="padding:25px; text-align:center; background:#fef2f2; border-bottom:1px solid #fecaca;">
                    <p style="margin:0; color:#991b1b; font-size:15px;">
                        Votre rendez-vous a été annulé avec succès.
                    </p>
                </div>
                
                <!-- Image de couverture -->
                <div style="padding:0;">
                    <img src="{cover_image}" alt="Photo" style="width:100%; height:200px; object-fit:cover; display:block;"/>
                </div>
                
                <!-- Infos du RDV annulé -->
                <div style="padding:25px;">
                    <h2 style="margin:0 0 8px 0; font-size:20px; color:#111;">{gym_name}</h2>
                    <p style="margin:0; color:#666; font-size:14px;">{gym_address}</p>
                    
                    <div style="margin:20px 0; padding:15px; background:#fafafa; border-radius:8px; border:1px solid #e5e5e5;">
                        <p style="margin:0 0 8px 0; font-size:15px; color:#111;">
                            <strong style="color:#ef4444; text-decoration:line-through;">{date_str} à {time_str}</strong>
                        </p>
                        <p style="margin:0; color:#666; font-size:14px;">
                            Coach: {coach_name}
                        </p>
                    </div>
                    
                    <div style="padding:15px 0; border-top:1px solid #eee;">
                        <p style="margin:0 0 5px 0; font-size:14px; color:#111; font-weight:500;">Prestation annulée</p>
                        <p style="margin:0; color:#666; font-size:14px;">{service_name} · {duration} · {price}</p>
                    </div>
                </div>
                
                <!-- CTA Reprendre RDV -->
                <div style="padding:0 25px 25px;">
                    <a href="{booking_url}" 
                       style="display:block; background:#111; color:white; padding:14px 40px; text-decoration:none; border-radius:8px; font-weight:600; font-size:15px; text-align:center;">
                        Reprendre rendez-vous
                    </a>
                </div>
                
                <!-- Adresse avec lien Maps -->
                <div style="padding:20px 25px; background:#fafafa; border-top:1px solid #eee;">
                    <p style="margin:0 0 5px 0; font-size:12px; color:#999; text-transform:uppercase;">Adresse</p>
                    <a href="{maps_url}" style="color:#3b82f6; text-decoration:none; font-size:14px;">
                        📍 {gym_address}
                    </a>
                </div>
                
                {SOCIAL_FOOTER_HTML}
                
                <!-- Footer -->
                <div style="padding:20px 25px; text-align:center;">
                    <p style="margin:0; color:#999; font-size:12px;">
                        Fitmatch - Votre plateforme fitness
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Rendez-vous annulé

Votre rendez-vous a été annulé avec succès.

{gym_name}
{gym_address}

Date: {date_str} à {time_str}
Coach: {coach_name}

Prestation: {service_name} · {duration} · {price}

Pour reprendre rendez-vous: {booking_url}

---
Fitmatch - Votre plateforme fitness
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"✕ Rendez-vous annulé - {gym_name}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi email annulation via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email annulation envoyé à {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Email d'annulation envoyé"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi email annulation: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_coach_notification_email(
    to_email: str,
    coach_name: str,
    client_name: str,
    client_email: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str = "Séance de coaching",
    duration: str = "60 min",
    price: str = "40€",
    booking_id: str = "",
    dashboard_url: Optional[str] = None
) -> dict:
    """
    Envoie une notification email au coach quand un client fait une réservation.
    Le coach peut confirmer ou refuser la séance depuis son dashboard.
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    
    # URL du dashboard coach
    if not dashboard_url:
        site_url = os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000')
        if not site_url.startswith('http'):
            site_url = f"https://{site_url}"
        dashboard_url = f"{site_url}/coach/portal"
    
    print(f"📧 Notification nouvelle réservation pour coach {coach_name} ({to_email})")
    print(f"   Client: {client_name}, Date: {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email simulé"}
    
    try:
        first_name = coach_name.split()[0] if coach_name else "Coach"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .badge {{ display: inline-block; background: rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 20px; margin-top: 10px; font-size: 14px; }}
        .content {{ padding: 30px; }}
        .alert-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px 20px; border-radius: 0 8px 8px 0; margin-bottom: 25px; }}
        .alert-box p {{ margin: 0; color: #92400e; font-size: 14px; }}
        .booking-card {{ background: #f9fafb; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .booking-card h3 {{ margin: 0 0 15px 0; color: #111; font-size: 18px; }}
        .info-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #6b7280; font-size: 14px; }}
        .info-value {{ color: #111; font-size: 14px; font-weight: 500; }}
        .client-box {{ background: #eff6ff; border-radius: 8px; padding: 15px; margin-top: 15px; }}
        .client-box p {{ margin: 5px 0; color: #1e40af; font-size: 14px; }}
        .btn {{ display: inline-block; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px; text-align: center; }}
        .btn-primary {{ background: #10b981; color: white; }}
        .btn-container {{ text-align: center; margin: 25px 0; }}
        .footer {{ background: #f9fafb; padding: 20px; text-align: center; }}
        .footer p {{ color: #6b7280; font-size: 12px; margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔔 Nouvelle demande de réservation</h1>
            <div class="badge">Action requise</div>
        </div>
        
        <div class="content">
            <p style="font-size: 16px; color: #374151;">Bonjour {first_name},</p>
            
            <div class="alert-box">
                <p><strong>Un client souhaite réserver une séance avec vous !</strong><br>
                Connectez-vous à votre dashboard pour confirmer ou refuser cette demande.</p>
            </div>
            
            <div class="booking-card">
                <h3>📅 Détails de la réservation</h3>
                <div class="info-row">
                    <span class="info-label">Date</span>
                    <span class="info-value">{date_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Heure</span>
                    <span class="info-value">{time_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Salle</span>
                    <span class="info-value">{gym_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Prestation</span>
                    <span class="info-value">{service_name} · {duration}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tarif</span>
                    <span class="info-value">{price}</span>
                </div>
                
                <div class="client-box">
                    <p><strong>👤 Client :</strong> {client_name}</p>
                    <p><strong>📧 Email :</strong> {client_email}</p>
                </div>
            </div>
            
            <div class="btn-container">
                <a href="{dashboard_url}" class="btn btn-primary">Voir mon dashboard</a>
            </div>
            
            <p style="font-size: 13px; color: #6b7280; text-align: center;">
                Vous pouvez confirmer ou refuser cette demande depuis votre espace coach.
            </p>
        </div>
        
        {SOCIAL_FOOTER_HTML}
        
        <div class="footer">
            <p>Fitmatch - Votre plateforme fitness</p>
            <p>Cet email a été envoyé suite à une demande de réservation.</p>
        </div>
    </div>
</body>
</html>
        """
        
        text_content = f"""
🔔 Nouvelle demande de réservation

Bonjour {first_name},

Un client souhaite réserver une séance avec vous !

📅 Détails de la réservation:
- Date: {date_str}
- Heure: {time_str}
- Salle: {gym_name}
- Prestation: {service_name} · {duration}
- Tarif: {price}

👤 Client: {client_name}
📧 Email: {client_email}

Connectez-vous à votre dashboard pour confirmer ou refuser:
{dashboard_url}

---
Fitmatch - Votre plateforme fitness
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"🔔 Nouvelle réservation - {client_name} · {date_str}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi notification coach via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Notification envoyée au coach {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Notification coach envoyée"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi notification coach: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_cancellation_to_coach_email(
    to_email: str,
    coach_name: str,
    client_name: str,
    client_email: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str = "Séance de coaching",
    duration: str = "60 min",
    price: str = "40€"
) -> dict:
    """
    Envoie une notification email au coach quand un client annule sa réservation.
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    
    print(f"📧 Notification annulation pour coach {coach_name} ({to_email})")
    print(f"   Client: {client_name} a annulé sa séance du {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email simulé"}
    
    try:
        first_name = coach_name.split()[0] if coach_name else "Coach"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .badge {{ display: inline-block; background: rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 20px; margin-top: 10px; font-size: 14px; }}
        .content {{ padding: 30px; }}
        .alert-box {{ background: #fef2f2; border-left: 4px solid #ef4444; padding: 15px 20px; border-radius: 0 8px 8px 0; margin-bottom: 25px; }}
        .alert-box p {{ margin: 0; color: #991b1b; font-size: 14px; }}
        .booking-card {{ background: #f9fafb; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .booking-card h3 {{ margin: 0 0 15px 0; color: #111; font-size: 18px; }}
        .info-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #6b7280; font-size: 14px; }}
        .info-value {{ color: #111; font-size: 14px; font-weight: 500; text-decoration: line-through; color: #9ca3af; }}
        .client-box {{ background: #fef2f2; border-radius: 8px; padding: 15px; margin-top: 15px; }}
        .client-box p {{ margin: 5px 0; color: #991b1b; font-size: 14px; }}
        .footer {{ background: #f9fafb; padding: 20px; text-align: center; }}
        .footer p {{ color: #6b7280; font-size: 12px; margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❌ Séance annulée</h1>
            <div class="badge">Information</div>
        </div>
        
        <div class="content">
            <p style="font-size: 16px; color: #374151;">Bonjour {first_name},</p>
            
            <div class="alert-box">
                <p><strong>{client_name} a annulé sa séance avec vous.</strong><br>
                Ce créneau est maintenant de nouveau disponible dans votre calendrier.</p>
            </div>
            
            <div class="booking-card">
                <h3>📅 Séance annulée</h3>
                <div class="info-row">
                    <span class="info-label">Date</span>
                    <span class="info-value">{date_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Heure</span>
                    <span class="info-value">{time_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Salle</span>
                    <span class="info-value">{gym_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Prestation</span>
                    <span class="info-value">{service_name} · {duration}</span>
                </div>
                
                <div class="client-box">
                    <p><strong>👤 Client :</strong> {client_name}</p>
                    <p><strong>📧 Email :</strong> {client_email}</p>
                </div>
            </div>
            
            <p style="font-size: 13px; color: #6b7280; text-align: center;">
                Le créneau du {date_str} à {time_str} est de nouveau libre pour d'autres réservations.
            </p>
        </div>
        
        {SOCIAL_FOOTER_HTML}
        
        <div class="footer">
            <p>Fitmatch - Votre plateforme fitness</p>
            <p>Cet email a été envoyé suite à une annulation de réservation.</p>
        </div>
    </div>
</body>
</html>
        """
        
        text_content = f"""
❌ Séance annulée

Bonjour {first_name},

{client_name} a annulé sa séance avec vous.

📅 Séance annulée:
- Date: {date_str}
- Heure: {time_str}
- Salle: {gym_name}
- Prestation: {service_name} · {duration}

👤 Client: {client_name}
📧 Email: {client_email}

Le créneau du {date_str} à {time_str} est de nouveau libre pour d'autres réservations.

---
Fitmatch - Votre plateforme fitness
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"❌ Séance annulée - {client_name} · {date_str}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi notification annulation au coach via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Notification annulation envoyée au coach {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Notification annulation coach envoyée"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi notification annulation coach: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_rejection_email_to_client(
    to_email: str,
    client_name: str,
    coach_name: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str = "Séance de coaching",
    duration: str = "60 min",
    price: str = "40€",
    booking_url: Optional[str] = None
) -> dict:
    """
    Envoie un email au client quand le coach annule/rejette sa réservation.
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    
    print(f"📧 Email annulation par coach pour client {client_name} ({to_email})")
    print(f"   Coach {coach_name} a annulé la séance du {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email simulé"}
    
    try:
        first_name = client_name.split()[0] if client_name else "Client"
        
        # URL de réservation pour reprendre rdv
        if not booking_url:
            site_url = os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000')
            if not site_url.startswith('http'):
                site_url = f"https://{site_url}"
            booking_url = site_url
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; }}
        .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .badge {{ display: inline-block; background: rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 20px; margin-top: 10px; font-size: 14px; }}
        .content {{ padding: 30px; }}
        .alert-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px 20px; border-radius: 0 8px 8px 0; margin-bottom: 25px; }}
        .alert-box p {{ margin: 0; color: #92400e; font-size: 14px; }}
        .booking-card {{ background: #f9fafb; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .booking-card h3 {{ margin: 0 0 15px 0; color: #111; font-size: 18px; }}
        .info-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #6b7280; font-size: 14px; }}
        .info-value {{ color: #9ca3af; font-size: 14px; font-weight: 500; text-decoration: line-through; }}
        .btn {{ display: inline-block; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px; text-align: center; }}
        .btn-primary {{ background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color: white; }}
        .btn-container {{ text-align: center; margin: 25px 0; }}
        .footer {{ background: #f9fafb; padding: 20px; text-align: center; }}
        .footer p {{ color: #6b7280; font-size: 12px; margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Séance non disponible</h1>
            <div class="badge">Information</div>
        </div>
        
        <div class="content">
            <p style="font-size: 16px; color: #374151;">Bonjour {first_name},</p>
            
            <div class="alert-box">
                <p><strong>{coach_name} n'est malheureusement pas disponible</strong> pour la séance demandée.<br>
                Nous vous invitons à choisir un autre créneau.</p>
            </div>
            
            <div class="booking-card">
                <h3>📅 Séance annulée</h3>
                <div class="info-row">
                    <span class="info-label">Date</span>
                    <span class="info-value">{date_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Heure</span>
                    <span class="info-value">{time_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Coach</span>
                    <span class="info-value">{coach_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Salle</span>
                    <span class="info-value">{gym_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Prestation</span>
                    <span class="info-value">{service_name} · {duration}</span>
                </div>
            </div>
            
            <div class="btn-container">
                <a href="{booking_url}" class="btn btn-primary">Réserver un autre créneau</a>
            </div>
            
            <p style="font-size: 13px; color: #6b7280; text-align: center;">
                D'autres créneaux sont disponibles. N'hésitez pas à réserver à nouveau !
            </p>
        </div>
        
        {SOCIAL_FOOTER_HTML}
        
        <div class="footer">
            <p>Fitmatch - Votre plateforme fitness</p>
            <p>Cet email a été envoyé suite à l'indisponibilité de votre coach.</p>
        </div>
    </div>
</body>
</html>
        """
        
        text_content = f"""
Séance non disponible

Bonjour {first_name},

{coach_name} n'est malheureusement pas disponible pour la séance demandée.

📅 Séance annulée:
- Date: {date_str}
- Heure: {time_str}
- Coach: {coach_name}
- Salle: {gym_name}
- Prestation: {service_name} · {duration}

Réservez un autre créneau: {booking_url}

D'autres créneaux sont disponibles. N'hésitez pas à réserver à nouveau !

---
Fitmatch - Votre plateforme fitness
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"Séance non disponible - {coach_name} · {date_str}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi email rejet au client via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email rejet envoyé au client {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Email rejet client envoyé"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi email rejet client: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_coach_cancelled_email(
    client_email: str,
    client_name: str,
    coach_name: str,
    gym_name: str,
    date: str
) -> dict:
    """
    Envoie un email au client quand le coach annule/supprime une séance confirmée
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    
    if site_url and not site_url.startswith('http'):
        site_url = f"https://{site_url}"
    
    booking_url = f"{site_url}/"
    
    print(f"📧 Préparation email annulation par coach:")
    print(f"  - Client: {client_name} ({client_email})")
    print(f"  - Coach: {coach_name}")
    print(f"  - Salle: {gym_name}")
    print(f"  - Date: {date}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email annulation simulé"}
    
    first_name = client_name.split()[0] if client_name else "Client"
    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0; padding:0; font-family: 'Inter', Arial, sans-serif; background-color:#f5f5f5;">
            <div style="max-width:600px; margin:0 auto; background:white;">
                
                <!-- Header -->
                <div style="background:#111; padding:30px; text-align:center;">
                    <div style="display:inline-block; background:#ef4444; color:white; padding:8px 20px; border-radius:50px; font-size:14px; font-weight:600;">
                        ✕ Séance annulée par le coach
                    </div>
                </div>
                
                <!-- Message principal -->
                <div style="padding:30px;">
                    <h2 style="margin:0 0 15px 0; font-size:22px; color:#111;">
                        Bonjour {first_name},
                    </h2>
                    
                    <p style="margin:0 0 25px 0; font-size:16px; color:#666; line-height:1.6;">
                        Nous sommes désolés de vous informer que votre séance avec <strong>{coach_name}</strong> 
                        a été annulée par le coach.
                    </p>
                    
                    <!-- Détails de la séance annulée -->
                    <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:12px; padding:20px; margin-bottom:25px;">
                        <h3 style="margin:0 0 15px 0; font-size:14px; text-transform:uppercase; color:#991b1b; letter-spacing:1px;">
                            Séance annulée
                        </h3>
                        <p style="margin:0 0 8px 0; font-size:16px; color:#111;">
                            <strong style="text-decoration:line-through;">{date}</strong>
                        </p>
                        <p style="margin:0 0 8px 0; font-size:15px; color:#666;">
                            📍 {gym_name}
                        </p>
                        <p style="margin:0; font-size:15px; color:#666;">
                            👤 Coach: {coach_name}
                        </p>
                    </div>
                    
                    <!-- Message de réconfort -->
                    <p style="margin:0 0 25px 0; font-size:15px; color:#666; line-height:1.6;">
                        Nous comprenons que cela puisse être décevant. N'hésitez pas à réserver 
                        une nouvelle séance avec un autre coach ou à un autre créneau.
                    </p>
                    
                    <!-- Bouton -->
                    <div style="text-align:center;">
                        <a href="{booking_url}" 
                           style="display:inline-block; background:#3b82f6; color:white; padding:14px 40px; text-decoration:none; border-radius:8px; font-weight:600; font-size:15px;">
                            Réserver une nouvelle séance
                        </a>
                    </div>
                </div>
                
                {SOCIAL_FOOTER_HTML}
                
                <!-- Footer -->
                <div style="padding:20px; background:#f9f9f9; text-align:center;">
                    <p style="margin:0 0 10px 0; font-size:18px; font-weight:700; color:#111;">
                        Fitmatch
                    </p>
                    <p style="margin:0; font-size:12px; color:#888;">
                        Votre plateforme de coaching fitness<br>
                        <a href="{site_url}" style="color:#3b82f6; text-decoration:none;">fitmatch.fr</a>
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Bonjour {first_name},

Nous sommes désolés de vous informer que votre séance avec {coach_name} a été annulée par le coach.

SÉANCE ANNULÉE:
- Date: {date}
- Salle: {gym_name}
- Coach: {coach_name}

Nous comprenons que cela puisse être décevant. N'hésitez pas à réserver une nouvelle séance.

Réserver une nouvelle séance: {booking_url}

---
Fitmatch - Votre plateforme fitness
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [client_email],
            "subject": f"😔 Séance annulée - {coach_name} · {date}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi email annulation coach au client via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email annulation envoyé au client {client_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": "Email annulation coach envoyé au client"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi email annulation coach: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }


def send_reminder_email(
    to_email: str,
    client_name: str,
    coach_name: str,
    gym_name: str,
    gym_address: str,
    date_str: str,
    time_str: str,
    service_name: str,
    duration: str,
    price: str,
    reminder_type: str = "24h",
    booking_id: Optional[str] = None,
    locale: str = "fr"
) -> dict:
    """
    Envoie un email de rappel de rendez-vous au client
    reminder_type: "24h" ou "2h" pour indiquer le type de rappel
    locale: code langue pour les traductions (fr, en, es, ar, de, it, pt)
    """
    from i18n_service import load_translations
    
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    
    if site_url and not site_url.startswith('http'):
        site_url = f"https://{site_url}"
    
    account_url = f"{site_url}/account"
    
    # Charger les traductions
    t = load_translations(locale)
    emails = t.get('emails', {})
    
    print(f"📧 Préparation email rappel ({reminder_type}) - Langue: {locale}:")
    print(f"  - Client: {client_name} ({to_email})")
    print(f"  - Coach: {coach_name}")
    print(f"  - Date: {date_str} à {time_str}")
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        return {"success": True, "mode": "demo", "message": "Email rappel simulé"}
    
    first_name = client_name.split()[0] if client_name else "Client"
    
    if reminder_type == "24h":
        reminder_text = emails.get('tomorrow', "C'est demain !")
        emoji = "📅"
        subject_prefix = emails.get('reminder_24h', 'Rappel J-1')
        header_color = "#3b82f6"
    else:
        reminder_text = emails.get('in_2_hours', "C'est dans 2 heures !")
        emoji = "⏰"
        subject_prefix = emails.get('reminder_2h', 'Rappel')
        header_color = "#f59e0b"
    
    # Textes traduits
    dont_forget = emails.get('dont_forget', "N'oublie pas ta séance de coaching")
    date_time_label = emails.get('date_time', 'Date & Heure')
    with_coach = emails.get('with_coach', 'Avec')
    your_session = emails.get('your_session', 'Votre séance')
    address_label = emails.get('address', 'Adresse')
    view_on_maps = emails.get('view_on_maps', 'Voir sur Google Maps')
    view_booking = emails.get('view_booking', 'Voir ma réservation')
    tips_title = emails.get('tips_title', 'Conseils')
    tip_arrive = emails.get('tip_arrive_early', 'Arrive 5 minutes en avance')
    tip_sportswear = emails.get('tip_sportswear', 'Prévois une tenue de sport confortable')
    tip_water = emails.get('tip_water', "N'oublie pas ta bouteille d'eau !")
    your_platform = emails.get('your_platform', 'Votre plateforme de coaching fitness')
    your_session_with = emails.get('your_session_with', 'Ta séance avec')
    
    maps_url = f"https://www.google.com/maps/search/?api=1&query={gym_address.replace(' ', '+')}" if gym_address else "#"
    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0; padding:0; font-family: 'Inter', Arial, sans-serif; background-color:#f5f5f5;">
            <div style="max-width:600px; margin:0 auto; background:white;">
                
                <!-- Header avec rappel -->
                <div style="background:{header_color}; padding:30px; text-align:center;">
                    <div style="font-size:40px; margin-bottom:10px;">{emoji}</div>
                    <h1 style="margin:0; color:white; font-size:24px; font-weight:700;">
                        {reminder_text}
                    </h1>
                    <p style="margin:10px 0 0 0; color:rgba(255,255,255,0.9); font-size:15px;">
                        {dont_forget}
                    </p>
                </div>
                
                <!-- Détails du rendez-vous -->
                <div style="padding:30px;">
                    
                    <div style="background:#f8fafc; border-radius:12px; padding:25px; margin-bottom:25px;">
                        <h2 style="margin:0 0 20px 0; font-size:20px; color:#111; text-align:center;">
                            {gym_name}
                        </h2>
                        
                        <div style="display:flex; justify-content:center; margin-bottom:15px;">
                            <div style="background:white; border:2px solid {header_color}; border-radius:10px; padding:15px 25px; text-align:center;">
                                <p style="margin:0 0 5px 0; font-size:13px; color:#666; text-transform:uppercase;">{date_time_label}</p>
                                <p style="margin:0; font-size:18px; font-weight:700; color:#111;">
                                    {date_str}
                                </p>
                                <p style="margin:5px 0 0 0; font-size:22px; font-weight:700; color:{header_color};">
                                    {time_str}
                                </p>
                            </div>
                        </div>
                        
                        <p style="margin:0; text-align:center; font-size:15px; color:#666;">
                            {with_coach} <strong style="color:#111;">{coach_name}</strong>
                        </p>
                    </div>
                    
                    <!-- Infos prestation -->
                    <div style="border-top:1px solid #eee; padding-top:20px; margin-bottom:20px;">
                        <h3 style="margin:0 0 10px 0; font-size:13px; text-transform:uppercase; color:#888; letter-spacing:1px;">
                            💪 {your_session}
                        </h3>
                        <p style="margin:0; font-size:15px; color:#333;">
                            {service_name}<br>
                            <span style="color:#666;">{duration} • {price}</span>
                        </p>
                    </div>
                    
                    <!-- Adresse avec Maps -->
                    <div style="border-top:1px solid #eee; padding-top:20px; margin-bottom:25px;">
                        <h3 style="margin:0 0 10px 0; font-size:13px; text-transform:uppercase; color:#888; letter-spacing:1px;">
                            📍 {address_label}
                        </h3>
                        <a href="{maps_url}" style="color:#3b82f6; text-decoration:none; font-size:15px;">
                            {gym_address}
                        </a>
                    </div>
                    
                    <!-- Boutons -->
                    <table width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="padding:5px;">
                                <a href="{maps_url}" 
                                   style="display:block; background:#111; color:white; padding:14px; text-decoration:none; border-radius:8px; font-weight:600; font-size:14px; text-align:center;">
                                    🗺️ {view_on_maps}
                                </a>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:5px;">
                                <a href="{account_url}" 
                                   style="display:block; background:#f5f5f5; color:#333; padding:14px; text-decoration:none; border-radius:8px; font-weight:500; font-size:14px; text-align:center;">
                                    📋 {view_booking}
                                </a>
                            </td>
                        </tr>
                    </table>
                </div>
                
                <!-- Conseils -->
                <div style="padding:20px 30px; background:#f0fdf4; border-top:1px solid #bbf7d0;">
                    <p style="margin:0; font-size:14px; color:#166534; line-height:1.6;">
                        <strong>💡 {tips_title} :</strong><br>
                        • {tip_arrive}<br>
                        • {tip_sportswear}<br>
                        • {tip_water}
                    </p>
                </div>
                
                {SOCIAL_FOOTER_HTML}
                
                <!-- Footer -->
                <div style="padding:20px; background:#f9f9f9; text-align:center;">
                    <p style="margin:0 0 10px 0; font-size:18px; font-weight:700; color:#111;">
                        Fitmatch
                    </p>
                    <p style="margin:0; font-size:12px; color:#888;">
                        {your_platform}<br>
                        <a href="{site_url}" style="color:#3b82f6; text-decoration:none;">fitmatch.fr</a>
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
{emoji} {reminder_text}

{dont_forget}

📍 {gym_name}
📅 {date_str} - {time_str}
👤 {with_coach} {coach_name}

{your_session}: {service_name}
{duration} • {price}

{address_label}: {gym_address}
Google Maps: {maps_url}

💡 {tips_title}:
• {tip_arrive}
• {tip_sportswear}
• {tip_water}

{view_booking}: {account_url}

---
Fitmatch - {your_platform}
        """
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": mail_from,
            "to": [to_email],
            "subject": f"{emoji} {subject_prefix} : {your_session_with} {coach_name} - {time_str}",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📤 Envoi email rappel ({reminder_type}) via Resend...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('id', 'N/A')
            print(f"✅ Email rappel ({reminder_type}) envoyé à {to_email} (ID: {email_id})")
            return {
                "success": True,
                "mode": "resend",
                "email_id": email_id,
                "message": f"Email rappel {reminder_type} envoyé"
            }
        else:
            error_msg = f"Erreur Resend (Status {response.status_code}): {response.text}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "mode": "resend",
                "error": error_msg
            }
            
    except Exception as e:
        error_msg = f"Erreur envoi email rappel: {e}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "mode": "error",
            "error": error_msg
        }