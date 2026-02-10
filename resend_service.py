# Service email avec Resend API
import os
import json
import requests
from typing import Optional

# Liens réseaux sociaux FitMatch
INSTAGRAM_URL = "https://www.instagram.com/fitmatch__?igsh=MXkwcTE5dmFhaDQ3OQ%3D%3D&utm_source=qr"
FACEBOOK_URL = "https://www.facebook.com/share/17f5yGSk86/?mibextid=wwXIfr"

# Cache pour les traductions des emails
_email_translations_cache = {}

def get_email_translations(lang: str = 'fr') -> dict:
    """Charge les traductions pour les emails"""
    global _email_translations_cache
    if lang in _email_translations_cache:
        return _email_translations_cache[lang]
    
    try:
        translations_path = f'translations/{lang}.json'
        with open(translations_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _email_translations_cache[lang] = data.get('emails', {})
            return _email_translations_cache[lang]
    except Exception as e:
        print(f"Error loading translations for {lang}: {e}")
        return {}

def get_social_footer(lang: str = 'fr') -> str:
    """Génère le footer social traduit"""
    t = get_email_translations(lang)
    follow_us = t.get('follow_us', 'Suivez-nous' if lang == 'fr' else 'Follow us')
    return f'''
<div style="padding:25px; background:#f9f9f9; border-top:1px solid #eee; text-align:center;">
    <p style="margin:0 0 15px 0; font-size:15px; color:#374151; font-weight:500;">{follow_us}</p>
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

def send_otp_email_resend(to_email: str, otp_code: str, full_name: Optional[str] = None, lang: str = 'fr') -> dict:
    """Envoie un code OTP par email via Resend API"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('SITE_URL', 'http://localhost:5000')
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] OTP Email to {to_email}: {otp_code} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        first_name = full_name.split()[0] if full_name else ("user" if lang == 'en' else "utilisateur")
        platform_tagline = t.get('platform_tagline', 'Votre plateforme de coaching fitness')
        otp_title = t.get('otp_title', 'Bonjour')
        otp_welcome = t.get('otp_welcome', 'Bienvenue sur FitMatch ! Voici votre code de vérification :')
        otp_your_code = t.get('otp_your_code', 'Votre code')
        otp_expires = t.get('otp_expires', 'Ce code expire dans')
        otp_minutes = t.get('otp_minutes', '10 minutes')
        otp_instruction = t.get('otp_instruction', 'Saisissez ce code pour activer votre compte.')
        otp_ignore = t.get('otp_ignore', "Si vous n'avez pas créé de compte, ignorez cet email.")
        platform_connects = t.get('platform_connects', 'La plateforme qui connecte coachs et clients')
        otp_subject = t.get('otp_subject', 'Votre code de vérification FitMatch')

        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc;">
            <div style="background: #008f57; padding: 40px; text-align: center; color: white;">
                <h1>FitMatch</h1>
                <p>{platform_tagline}</p>
            </div>
            <div style="padding: 40px; background: white;">
                <h2>{otp_title} {first_name} !</h2>
                <p>{otp_welcome}</p>
                <div style="border: 2px solid #008f57; padding: 20px; text-align: center; margin: 20px 0; font-size: 32px; font-weight: bold; color: #008f57;">
                    {otp_code}
                </div>
                <p style="font-size: 14px; color: #64748b;">⏱️ {otp_expires} {otp_minutes}</p>
                <p>{otp_instruction}</p>
            </div>
            {get_social_footer(lang)}
            <div style="padding: 20px; text-align: center; font-size: 12px; color: #94a3b8;">
                <p>{platform_connects}</p>
            </div>
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": f"{otp_subject}: {otp_code}",
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return {"success": False}

def send_booking_confirmation_email(to_email: str, client_name: str, coach_name: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, coach_photo: Optional[str] = None, reservation_id: Optional[str] = None, lang: str = 'fr') -> dict:
    """Envoie un email de confirmation de réservation"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    if site_url and not site_url.startswith('http'): site_url = f"https://{site_url}"
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Booking Confirmation to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('confirmation_subject', 'Réservation confirmée - FitMatch')
        title = t.get('confirmation_title', 'Réservation confirmée')
        view_booking = t.get('confirmation_view_booking', 'Voir ma réservation')
        addr_label = t.get('confirmation_location', 'Adresse')
        service_label = t.get('confirmation_service', 'Prestation')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 20px; text-align: center; color: white;">
                <div style="background: #22c55e; display: inline-block; padding: 5px 15px; border-radius: 20px;">{title}</div>
            </div>
            <div style="padding: 30px;">
                <h2>{gym_name}</h2>
                <p><strong>{date_str}</strong> à <strong>{time_str}</strong></p>
                <p>Avec {coach_name}</p>
                <hr>
                <p><strong>{addr_label}:</strong> {gym_address}</p>
                <p><strong>{service_label}:</strong> {service_name} ({duration}, {price})</p>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{site_url}/account" style="background: #111; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{view_booking}</a>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": f"{subject} - {gym_name}",
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending booking email: {e}")
        return {"success": False}

def send_subscription_success_email(to_email: str, coach_name: str, subscription_url: str, lang: str = 'fr') -> dict:
    """Envoie un email de succès d'abonnement au coach"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Subscription Success to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('sub_success_subject', 'Bienvenue sur FitMatch Pro !')
        title = t.get('sub_success_title', 'Félicitations !')
        body = t.get('sub_success_body', 'Votre abonnement est désormais actif. Vous avez accès à toutes les fonctionnalités.')
        cta = t.get('sub_success_cta', 'Accéder à mon portail')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #008f57; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{subscription_url}" style="background: #008f57; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">{cta}</a>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending sub success email: {e}")
        return {"success": False}

def send_payment_failed_email(to_email: str, coach_name: str, retry_url: str, lang: str = 'fr') -> dict:
    """Envoie un email d'échec de paiement de l'abonnement"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Payment Failed to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('pay_failed_subject', 'Attention : Échec du paiement FitMatch')
        title = t.get('pay_failed_title', 'Problème de paiement')
        body = t.get('pay_failed_body', 'Nous n\'avons pas pu prélever votre abonnement mensuel. Vous avez 24h pour régulariser avant le blocage de votre compte.')
        cta = t.get('pay_failed_cta', 'Mettre à jour mon paiement')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #ef4444; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{retry_url}" style="background: #ef4444; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">{cta}</a>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending pay failed email: {e}")
        return {"success": False}

def send_session_payment_receipt(to_email: str, client_name: str, coach_name: str, gym_name: str, gym_address: str, session_date: str, session_time: str, service_name: str, duration: str, amount: str, lang: str = 'fr') -> dict:
    """Envoie un reçu de paiement pour une séance au client"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Session Receipt to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('receipt_subject', 'Reçu de paiement - FitMatch')
        title = t.get('receipt_title', 'Merci pour votre paiement !')
        body = t.get('receipt_body', 'Voici le récapitulatif de votre paiement pour votre séance de coaching.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #008f57; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {client_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Coach :</strong> {coach_name}</p>
                    <p><strong>Séance :</strong> {service_name} ({duration})</p>
                    <p><strong>Lieu :</strong> {gym_name}</p>
                    <p><strong>Date :</strong> {session_date} à {session_time}</p>
                    <hr style="border: none; border-top: 1px solid #cbd5e1; margin: 15px 0;">
                    <p style="font-size: 20px; font-weight: bold; color: #008f57;">Montant payé : {amount}</p>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending session receipt: {e}")
        return {"success": False}

def send_account_blocked_email(to_email: str, coach_name: str, retry_url: str, lang: str = 'fr') -> dict:
    """Envoie un email de compte bloqué pour non-paiement"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Account Blocked to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('blocked_subject', 'Compte FitMatch suspendu')
        title = t.get('blocked_title', 'Accès suspendu')
        body = t.get('blocked_body', 'Votre compte a été suspendu suite à l\'échec répété du paiement de votre abonnement. Votre profil n\'est plus visible par les clients.')
        cta = t.get('blocked_cta', 'Réactiver mon compte')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{retry_url}" style="background: #111; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">{cta}</a>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending blocked email: {e}")
        return {"success": False}

def send_reminder_email(to_email: str, client_name: str, coach_name: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, reminder_type: str = "24h", booking_id: str = None, lang: str = 'fr') -> dict:
    """Envoie un email de rappel de séance"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Reminder {reminder_type} to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get(f'reminder_subject_{reminder_type}', f'Rappel : Votre séance {reminder_type}')
        title = t.get('reminder_title', 'N\'oubliez pas votre séance !')
        body = t.get(f'reminder_body_{reminder_type}', f'Votre séance approche à grands pas.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {client_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Coach :</strong> {coach_name}</p>
                    <p><strong>Date :</strong> {date_str} à {time_str}</p>
                    <p><strong>Lieu :</strong> {gym_name}</p>
                    <p><strong>Adresse :</strong> {gym_address}</p>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending reminder email: {e}")
        return {"success": False}

def send_cancellation_email(to_email: str, client_name: str, coach_name: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, coach_photo: Optional[str] = None, booking_url: Optional[str] = None, lang: str = 'fr') -> dict:
    """Envoie un email d'annulation de réservation au client"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Cancellation Client to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('cancel_subject', 'Réservation annulée - FitMatch')
        title = t.get('cancel_title', 'Réservation annulée')
        body = t.get('cancel_body', 'Votre réservation a été annulée.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #ef4444; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {client_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Coach :</strong> {coach_name}</p>
                    <p><strong>Date :</strong> {date_str} à {time_str}</p>
                    <p><strong>Lieu :</strong> {gym_name}</p>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending cancellation email: {e}")
        return {"success": False}

def send_cancellation_to_coach_email(to_email: str, coach_name: str, client_name: str, client_email: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, lang: str = 'fr') -> dict:
    """Envoie un email d'annulation de réservation au coach"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Cancellation Coach to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('cancel_coach_subject', 'Une séance a été annulée')
        title = t.get('cancel_coach_title', 'Séance annulée')
        body = t.get('cancel_coach_body', f'Le client {client_name} a annulé sa séance.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Client :</strong> {client_name}</p>
                    <p><strong>Date :</strong> {date_str} à {time_str}</p>
                    <p><strong>Lieu :</strong> {gym_name}</p>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending cancellation coach email: {e}")
        return {"success": False}

def send_coach_notification_email(to_email: str, coach_name: str, client_name: str, client_email: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, booking_id: str = None, lang: str = 'fr') -> dict:
    """Notifie le coach d'une nouvelle demande de réservation"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    site_url = os.environ.get('REPLIT_DEV_DOMAIN', os.environ.get('SITE_URL', 'http://localhost:5000'))
    if site_url and not site_url.startswith('http'): site_url = f"https://{site_url}"
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Coach Notification to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('notification_subject', 'Nouvelle demande de réservation !')
        title = t.get('notification_title', 'Nouvelle demande')
        body = t.get('notification_body', f'Vous avez reçu une nouvelle demande de {client_name}.')
        cta = t.get('notification_cta', 'Voir mes réservations')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Client :</strong> {client_name}</p>
                    <p><strong>Séance :</strong> {service_name}</p>
                    <p><strong>Date :</strong> {date_str} à {time_str}</p>
                    <p><strong>Lieu :</strong> {gym_name}</p>
                </div>
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{site_url}/coach/portal" style="background: #111; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">{cta}</a>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending coach notification: {e}")
        return {"success": False}

def send_rejection_email_to_client(to_email: str, client_name: str, coach_name: str, gym_name: str, gym_address: str, date_str: str, time_str: str, service_name: str, duration: str, price: str, lang: str = 'fr') -> dict:
    """Envoie un email au client si le coach refuse la demande"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Rejection to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('reject_subject', 'Demande non acceptée - FitMatch')
        title = t.get('reject_title', 'Demande non acceptée')
        body = t.get('reject_body', f'Désolé, {coach_name} n\'est pas disponible pour ce créneau.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {client_name},</p>
                <p>{body}</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-top: 20px;">
                    <p><strong>Coach :</strong> {coach_name}</p>
                    <p><strong>Séance :</strong> {service_name}</p>
                    <p><strong>Date :</strong> {date_str} à {time_str}</p>
                </div>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending rejection email: {e}")
        return {"success": False}

def send_coach_cancelled_email(client_email: str, client_name: str, coach_name: str, gym_name: str, date: str, lang: str = 'fr') -> dict:
    """Envoie un email d'annulation au client quand le coach annule la séance"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Coach Cancelled to {client_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('coach_cancel_subject', 'Annulation de votre séance FitMatch')
        title = t.get('coach_cancel_title', 'Séance annulée')
        body = t.get('coach_cancel_body', f'{coach_name} a dû annuler votre séance du {date}.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #111; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {client_name},</p>
                <p>{body}</p>
                <p>Nous vous invitons à choisir un autre créneau ou un autre coach sur la plateforme.</p>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [client_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending coach cancellation email: {e}")
        return {"success": False}

def send_account_restored_email(to_email: str, coach_name: str, lang: str = 'fr') -> dict:
    """Envoie un email quand le compte bloqué est restauré après paiement"""
    resend_key = os.environ.get('RESEND_API_KEY')
    mail_from = 'Fitmatch <contact@fitmatch.fr>'
    t = get_email_translations(lang)
    
    if not resend_key:
        print(f"📧 [DEMO] Account Restored to {to_email} (lang: {lang})")
        return {"success": True, "mode": "demo"}
    
    try:
        subject = t.get('restored_subject', 'Compte FitMatch restauré !')
        title = t.get('restored_title', 'Accès rétabli')
        body = t.get('restored_body', 'Merci pour votre paiement. Votre compte a été restauré et votre profil est de nouveau visible.')
        
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: white; border: 1px solid #eee;">
            <div style="background: #008f57; padding: 40px; text-align: center; color: white;">
                <h1>{title}</h1>
            </div>
            <div style="padding: 40px;">
                <p>Bonjour {coach_name},</p>
                <p>{body}</p>
            </div>
            {get_social_footer(lang)}
        </div>
        """
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": mail_from,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            },
            timeout=10
        )
        return {"success": response.status_code == 200}
    except Exception as e:
        print(f"Error sending restored email: {e}")
        return {"success": False}
