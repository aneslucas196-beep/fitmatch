# Service email avec Resend API
import os
import requests
from typing import Optional

def send_otp_email_resend(to_email: str, otp_code: str, full_name: Optional[str] = None) -> bool:
    """
    Envoie un code OTP par email via Resend API
    """
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = os.environ.get('MAIL_FROM', 'Coach Fitness <no-reply@coachfitness.app>')
    
    if not resend_key:
        print("⚠️ RESEND_API_KEY non configuré, simulation d'envoi d'email")
        print(f"📧 Email simulé envoyé à {to_email}: Code OTP = {otp_code}")
        return True
    
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
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Email OTP envoyé via Resend à {to_email}")
            return True
        else:
            print(f"❌ Erreur Resend (Status {response.status_code}): {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Erreur envoi email Resend: {e}")
        return False