# Email service using SendGrid integration
import os
import sys
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

def send_otp_email(to_email: str, otp_code: str, full_name: Optional[str] = None) -> bool:
    """
    Envoie un code OTP par email via SendGrid
    """
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    if not sendgrid_key:
        from logger import get_logger
        log = get_logger()
        log.warning("SENDGRID_API_KEY non configuré, simulation d'envoi d'email")
        log.info(f"Email simulé envoyé à {to_email[:3]}...: Code OTP = {otp_code}")
        return True
    
    try:
        sg = SendGridAPIClient(api_key=sendgrid_key)
        
        # Adresse d'expéditeur (à ajuster selon votre configuration SendGrid)
        from_email = "noreply@coachfitness.app"
        
        # Prénom pour personnaliser l'email
        first_name = full_name.split()[0] if full_name else "utilisateur"
        
        # Sujet et contenu de l'email
        subject = f"Votre code de vérification Coach Fitness: {otp_code}"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Coach Fitness</h1>
                <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">Votre plateforme fitness</p>
            </div>
            
            <div style="padding: 40px; background: white;">
                <h2 style="color: #333; margin-bottom: 20px;">Bonjour {first_name} !</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Voici votre code de vérification pour finaliser votre inscription :
                </p>
                
                <div style="background: #f8f9fa; border: 2px dashed #667eea; border-radius: 10px; padding: 30px; text-align: center; margin: 30px 0;">
                    <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">{otp_code}</span>
                </div>
                
                <p style="color: #666; font-size: 14px; line-height: 1.6;">
                    • Ce code expire dans <strong>10 minutes</strong><br>
                    • Saisissez-le sur la page de vérification pour activer votre compte<br>
                    • Si vous n'avez pas demandé ce code, ignorez cet email
                </p>
                
                <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
                    <p style="color: #666; font-size: 12px; margin: 0; text-align: center;">
                        Cet email a été envoyé par Coach Fitness.<br>
                        Si vous avez des questions, contactez notre support.
                    </p>
                </div>
            </div>
        </div>
        """
        
        text_content = f"""
        Bonjour {first_name} !
        
        Voici votre code de vérification Coach Fitness : {otp_code}
        
        Ce code expire dans 10 minutes.
        Saisissez-le sur la page de vérification pour activer votre compte.
        
        Si vous n'avez pas demandé ce code, ignorez cet email.
        
        L'équipe Coach Fitness
        """
        
        message = Mail(
            from_email=Email(from_email),
            to_emails=To(to_email),
            subject=subject
        )
        message.content = Content("text/html", html_content)
        
        # Ajouter aussi le contenu texte comme alternative
        message.add_content(Content("text/plain", text_content))
        
        response = sg.send(message)
        from logger import get_logger
        get_logger().info(f"Email OTP envoyé à {to_email[:3]}... (Status: {response.status_code})")
        return True
        
    except Exception as e:
        from logger import get_logger
        get_logger().error(f"Erreur envoi email: {e}")
        return False