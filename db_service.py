"""
Service de base de données PostgreSQL pour FitMatch
Remplace le mode démo (demo_users.json) par une vraie base de données
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, Dict, Any, List

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Obtient une connexion à la base de données."""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL non configuré")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def load_users_from_db() -> Dict[str, Dict]:
    """Charge tous les utilisateurs depuis la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        users = {}
        for row in rows:
            email = row['email']
            user_data = dict(row)
            user_data['specialties'] = user_data.get('specialties') or []
            user_data['selected_gyms_data'] = user_data.get('selected_gyms_data') or []
            user_data['pending_bookings'] = user_data.get('pending_bookings') or []
            user_data['confirmed_bookings'] = user_data.get('confirmed_bookings') or []
            user_data['rejected_bookings'] = user_data.get('rejected_bookings') or []
            user_data['unavailable_days'] = user_data.get('unavailable_days') or []
            user_data['unavailable_slots'] = user_data.get('unavailable_slots') or []
            users[email] = user_data
        
        return users
    except Exception as e:
        print(f"❌ Erreur chargement utilisateurs depuis DB: {e}")
        return {}

def get_user_from_db(email: str) -> Optional[Dict]:
    """Récupère un utilisateur par email."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            user_data = dict(row)
            user_data['specialties'] = user_data.get('specialties') or []
            user_data['selected_gyms_data'] = user_data.get('selected_gyms_data') or []
            user_data['pending_bookings'] = user_data.get('pending_bookings') or []
            user_data['confirmed_bookings'] = user_data.get('confirmed_bookings') or []
            user_data['rejected_bookings'] = user_data.get('rejected_bookings') or []
            user_data['unavailable_days'] = user_data.get('unavailable_days') or []
            user_data['unavailable_slots'] = user_data.get('unavailable_slots') or []
            return user_data
        return None
    except Exception as e:
        print(f"❌ Erreur récupération utilisateur {email}: {e}")
        return None

def save_user_to_db(email: str, user_data: Dict) -> bool:
    """Sauvegarde ou met à jour un utilisateur dans la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        specialties = user_data.get('specialties', [])
        if isinstance(specialties, str):
            try:
                specialties = json.loads(specialties)
            except:
                specialties = []
        
        selected_gyms_data = user_data.get('selected_gyms_data', [])
        if isinstance(selected_gyms_data, str):
            try:
                selected_gyms_data = json.loads(selected_gyms_data)
            except:
                selected_gyms_data = []
        
        pending_bookings = user_data.get('pending_bookings', [])
        if isinstance(pending_bookings, str):
            try:
                pending_bookings = json.loads(pending_bookings)
            except:
                pending_bookings = []
        
        confirmed_bookings = user_data.get('confirmed_bookings', [])
        if isinstance(confirmed_bookings, str):
            try:
                confirmed_bookings = json.loads(confirmed_bookings)
            except:
                confirmed_bookings = []
        
        rejected_bookings = user_data.get('rejected_bookings', [])
        if isinstance(rejected_bookings, str):
            try:
                rejected_bookings = json.loads(rejected_bookings)
            except:
                rejected_bookings = []
        
        unavailable_days = user_data.get('unavailable_days', [])
        if isinstance(unavailable_days, str):
            try:
                unavailable_days = json.loads(unavailable_days)
            except:
                unavailable_days = []
        
        unavailable_slots = user_data.get('unavailable_slots', [])
        if isinstance(unavailable_slots, str):
            try:
                unavailable_slots = json.loads(unavailable_slots)
            except:
                unavailable_slots = []
        
        cur.execute("""
            INSERT INTO users (
                email, password, full_name, role, gender, country_code,
                coach_gender_preference, profile_completed, verified, email_verified,
                bio, city, instagram_url, price_from, radius_km, profile_photo_url,
                profile_slug, specialties, selected_gym_ids, selected_gyms_data,
                subscription_status, stripe_customer_id, stripe_subscription_id,
                subscription_period_end, otp_code, otp_expiry,
                pending_bookings, confirmed_bookings, rejected_bookings,
                unavailable_days, unavailable_slots, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (email) DO UPDATE SET
                password = COALESCE(EXCLUDED.password, users.password),
                full_name = COALESCE(EXCLUDED.full_name, users.full_name),
                role = COALESCE(EXCLUDED.role, users.role),
                gender = COALESCE(EXCLUDED.gender, users.gender),
                country_code = COALESCE(EXCLUDED.country_code, users.country_code),
                coach_gender_preference = EXCLUDED.coach_gender_preference,
                profile_completed = COALESCE(EXCLUDED.profile_completed, users.profile_completed),
                verified = COALESCE(EXCLUDED.verified, users.verified),
                email_verified = COALESCE(EXCLUDED.email_verified, users.email_verified),
                bio = COALESCE(EXCLUDED.bio, users.bio),
                city = COALESCE(EXCLUDED.city, users.city),
                instagram_url = COALESCE(EXCLUDED.instagram_url, users.instagram_url),
                price_from = COALESCE(EXCLUDED.price_from, users.price_from),
                radius_km = COALESCE(EXCLUDED.radius_km, users.radius_km),
                profile_photo_url = COALESCE(EXCLUDED.profile_photo_url, users.profile_photo_url),
                profile_slug = COALESCE(EXCLUDED.profile_slug, users.profile_slug),
                specialties = COALESCE(EXCLUDED.specialties, users.specialties),
                selected_gym_ids = COALESCE(EXCLUDED.selected_gym_ids, users.selected_gym_ids),
                selected_gyms_data = COALESCE(EXCLUDED.selected_gyms_data, users.selected_gyms_data),
                subscription_status = COALESCE(EXCLUDED.subscription_status, users.subscription_status),
                stripe_customer_id = COALESCE(EXCLUDED.stripe_customer_id, users.stripe_customer_id),
                stripe_subscription_id = COALESCE(EXCLUDED.stripe_subscription_id, users.stripe_subscription_id),
                subscription_period_end = EXCLUDED.subscription_period_end,
                otp_code = EXCLUDED.otp_code,
                otp_expiry = EXCLUDED.otp_expiry,
                pending_bookings = COALESCE(EXCLUDED.pending_bookings, users.pending_bookings),
                confirmed_bookings = COALESCE(EXCLUDED.confirmed_bookings, users.confirmed_bookings),
                rejected_bookings = COALESCE(EXCLUDED.rejected_bookings, users.rejected_bookings),
                unavailable_days = COALESCE(EXCLUDED.unavailable_days, users.unavailable_days),
                unavailable_slots = COALESCE(EXCLUDED.unavailable_slots, users.unavailable_slots),
                updated_at = CURRENT_TIMESTAMP
        """, (
            email,
            user_data.get('password'),
            user_data.get('full_name'),
            user_data.get('role', 'client'),
            user_data.get('gender'),
            user_data.get('country_code'),
            user_data.get('coach_gender_preference'),
            user_data.get('profile_completed', False),
            user_data.get('verified', False),
            user_data.get('email_verified', False),
            user_data.get('bio'),
            user_data.get('city'),
            user_data.get('instagram_url'),
            user_data.get('price_from', 50),
            user_data.get('radius_km', 10),
            user_data.get('profile_photo_url'),
            user_data.get('profile_slug'),
            json.dumps(specialties),
            user_data.get('selected_gym_ids'),
            json.dumps(selected_gyms_data),
            user_data.get('subscription_status', 'pending_payment'),
            user_data.get('stripe_customer_id'),
            user_data.get('stripe_subscription_id'),
            user_data.get('subscription_period_end'),
            user_data.get('otp_code'),
            user_data.get('otp_expiry'),
            json.dumps(pending_bookings),
            json.dumps(confirmed_bookings),
            json.dumps(rejected_bookings),
            json.dumps(unavailable_days),
            json.dumps(unavailable_slots)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Utilisateur {email} sauvegardé dans la DB")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde utilisateur {email}: {e}")
        return False

def remove_user_from_db(email: str) -> bool:
    """Supprime un utilisateur de la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Erreur suppression utilisateur {email}: {e}")
        return False

def migrate_json_to_db():
    """Migre les utilisateurs de demo_users.json vers la base de données."""
    try:
        json_file = "demo_users.json"
        if not os.path.exists(json_file):
            print("⚠️ Pas de fichier demo_users.json à migrer")
            return 0
        
        with open(json_file, 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        migrated = 0
        for email, user_data in users.items():
            user_data['email'] = email
            if save_user_to_db(email, user_data):
                migrated += 1
        
        print(f"✅ Migration terminée: {migrated} utilisateurs migrés")
        return migrated
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        return 0

def user_exists_in_db(email: str) -> bool:
    """Vérifie si un utilisateur existe dans la base de données."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"❌ Erreur vérification existence {email}: {e}")
        return False
