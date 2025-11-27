# Service email avec Resend API
import os
import requests
from typing import Optional

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
        
        # Contenu HTML de l'email
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); padding: 40px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Fitmatch</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Votre plateforme fitness</p>
            </div>
            
            <div style="padding: 40px; background: white;">
                <h2 style="color: #333; margin-bottom: 20px;">Bonjour {first_name} !</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Voici votre code de vérification pour finaliser votre inscription :
                </p>
                
                <div style="background: #f8fafc; border: 2px dashed #3b82f6; border-radius: 10px; padding: 30px; text-align: center; margin: 30px 0;">
                    <span style="font-size: 36px; font-weight: bold; color: #3b82f6; letter-spacing: 8px;">{otp_code}</span>
                </div>
                
                <p style="color: #666; font-size: 14px; line-height: 1.6;">
                    • Ce code expire dans <strong>10 minutes</strong><br>
                    • Saisissez-le sur la page de vérification pour activer votre compte<br>
                    • Si vous n'avez pas demandé ce code, ignorez cet email
                </p>
                
                <div style="margin-top: 40px; padding: 20px; background: #f8fafc; border-radius: 8px;">
                    <p style="color: #666; font-size: 12px; margin: 0; text-align: center;">
                        Cet email a été envoyé par Fitmatch.<br>
                        Si vous avez des questions, contactez notre support.
                    </p>
                </div>
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
                
                <!-- Footer -->
                <div style="padding:25px; background:#f9f9f9; border-top:1px solid #eee; text-align:center;">
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