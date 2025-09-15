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
    mail_from = os.environ.get('MAIL_FROM', 'Coach Fitness <onboarding@resend.dev>')
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
                <h1 style="color: white; margin: 0; font-size: 28px;">Coach Fitness</h1>
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
                        Cet email a été envoyé par Coach Fitness.<br>
                        Si vous avez des questions, contactez notre support.
                    </p>
                </div>
            </div>
        </div>
        """
        
        # Contenu texte alternatif
        text_content = f"""
        Bonjour {first_name} !
        
        Voici votre code de vérification Coach Fitness : {otp_code}
        
        Ce code expire dans 10 minutes.
        Saisissez-le sur la page de vérification pour activer votre compte.
        
        Si vous n'avez pas demandé ce code, ignorez cet email.
        
        L'équipe Coach Fitness
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