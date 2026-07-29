import os
import sqlite3
import json
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography.fernet import Fernet

DB_FILE = os.path.join(os.path.dirname(__file__), "users.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_fernet_key(secret_key):
    h = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(h)

def hash_otp(otp_code):
    return hashlib.sha256(otp_code.encode()).hexdigest()

def encrypt_otp(otp_code, secret_key):
    key = get_fernet_key(secret_key)
    f = Fernet(key)
    return f.encrypt(otp_code.encode()).decode()

def decrypt_otp(encrypted_otp, secret_key):
    key = get_fernet_key(secret_key)
    f = Fernet(key)
    return f.decrypt(encrypted_otp.encode()).decode()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            email TEXT PRIMARY KEY,
            otp TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            attempts INTEGER DEFAULT 0,
            store_method TEXT DEFAULT 'plain'
        )
    """)
    
    
    try:
        cursor.execute("ALTER TABLE otps ADD COLUMN attempts INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE otps ADD COLUMN store_method TEXT DEFAULT 'plain'")
    except sqlite3.OperationalError:
        pass
        
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            source_name TEXT,
            question TEXT,
            analysis TEXT,
            extracted_text TEXT,
            timestamp TEXT,
            timestamp_display TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def create_user(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (email) VALUES (?)", (email.lower().strip(),))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        
        cursor.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),))
        row = cursor.fetchone()
        user_id = row['id'] if row else None
    conn.close()
    return user_id

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def save_otp(email, otp_code, store_method="plain", expires_in_seconds=300, secret_key=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    
    if store_method == "hash":
        stored_val = hash_otp(otp_code)
    elif store_method == "encrypt":
        if not secret_key:
            raise ValueError("Secret key is required for encrypting OTP")
        stored_val = encrypt_otp(otp_code, secret_key)
    else:
        stored_val = otp_code
        
    expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
    expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT OR REPLACE INTO otps (email, otp, expires_at, attempts, store_method)
        VALUES (?, ?, ?, 0, ?)
    """, (email.lower().strip(), stored_val, expires_at_str, store_method))
    
    conn.commit()
    conn.close()

def get_active_otp(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        SELECT * FROM otps 
        WHERE email = ? AND expires_at > ?
    """, (email.lower().strip(), current_time_str))
    
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def extend_otp_expiry(email, expires_in_seconds=300):
    conn = get_db_connection()
    cursor = conn.cursor()
    expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
    expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        UPDATE otps 
        SET expires_at = ?
        WHERE email = ?
    """, (expires_at_str, email.lower().strip()))
    
    conn.commit()
    conn.close()

def verify_otp_status(email, otp_code, allowed_attempts=3, secret_key=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    
    cursor.execute("""
        SELECT * FROM otps 
        WHERE email = ? AND expires_at > ?
    """, (email.lower().strip(), current_time_str))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "INVALID_OR_EXPIRED"
        
    otp_record = dict(row)
    
    
    if otp_record["attempts"] >= allowed_attempts:
        
        cursor.execute("DELETE FROM otps WHERE email = ?", (email.lower().strip(),))
        conn.commit()
        conn.close()
        return False, "TOO_MANY_ATTEMPTS"
        
    
    store_method = otp_record.get("store_method", "plain")
    stored_otp = otp_record["otp"]
    match = False
    
    if store_method == "hash":
        match = (stored_otp == hash_otp(otp_code))
    elif store_method == "encrypt":
        if not secret_key:
            conn.close()
            raise ValueError("Secret key is required to decrypt OTP")
        try:
            match = (decrypt_otp(stored_otp, secret_key) == otp_code)
        except Exception:
            match = False
    else: 
        match = (stored_otp == otp_code)
        
    if match:
        
        cursor.execute("DELETE FROM otps WHERE email = ?", (email.lower().strip(),))
        conn.commit()
        conn.close()
        return True, None
    else:
        
        new_attempts = otp_record["attempts"] + 1
        if new_attempts >= allowed_attempts:
            
            cursor.execute("DELETE FROM otps WHERE email = ?", (email.lower().strip(),))
            conn.commit()
            conn.close()
            return False, "TOO_MANY_ATTEMPTS"
        else:
            cursor.execute("""
                UPDATE otps 
                SET attempts = ? 
                WHERE email = ?
            """, (new_attempts, email.lower().strip()))
            conn.commit()
            conn.close()
            return False, "INVALID_CODE"

def verify_otp(email, otp_code):
    
    success, _ = verify_otp_status(email, otp_code, allowed_attempts=3)
    return success

def load_history_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_history_for_user(user_id, entry):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    
    cursor.execute("""
        INSERT OR REPLACE INTO history (id, user_id, title, source_name, question, analysis, extracted_text, timestamp, timestamp_display)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry.get("id"),
        user_id,
        entry.get("title"),
        entry.get("source_name"),
        entry.get("question"),
        entry.get("analysis"),
        entry.get("extracted_text"),
        entry.get("timestamp"),
        entry.get("timestamp_display")
    ))
    
    
    cursor.execute("""
        DELETE FROM history 
        WHERE user_id = ? AND id NOT IN (
            SELECT id FROM history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        )
    """, (user_id, user_id))
    
    conn.commit()
    conn.close()

def delete_history_item_for_user(user_id, item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE user_id = ? AND id = ?", (user_id, item_id))
    conn.commit()
    conn.close()


def migrate_guest_history(guest_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if guest_id:
        cursor.execute("UPDATE history SET user_id = ? WHERE user_id = ?", (user_id, guest_id))
    # Also migrate any unassigned guest lab reports to the user
    cursor.execute("UPDATE history SET user_id = ? WHERE user_id LIKE 'guest_%'", (user_id,))
    conn.commit()
    conn.close()

