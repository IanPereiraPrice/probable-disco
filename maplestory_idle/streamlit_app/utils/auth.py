"""
Simple authentication system for MapleStory Idle Calculator.
Uses hashed passwords stored in a CSV file.
"""
import hashlib
import os
import csv
from datetime import datetime
from typing import Optional, Tuple

# Registration code - must be provided to create an account
# Set this as REGISTRATION_CODE in Streamlit secrets or environment variable
def _get_registration_code() -> str:
    """Get the registration code from Streamlit secrets or environment."""
    try:
        import streamlit as st
        return st.secrets.get("REGISTRATION_CODE", os.environ.get("REGISTRATION_CODE", ""))
    except Exception:
        return os.environ.get("REGISTRATION_CODE", "")

# Path to users database
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.csv")


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def _ensure_users_file():
    """Create users.csv if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'password_hash', 'created_at'])


def get_all_users() -> list:
    """Get list of all usernames."""
    _ensure_users_file()
    users = []
    with open(USERS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row['username'])
    return users


def user_exists(username: str) -> bool:
    """Check if a user exists."""
    return username.lower() in [u.lower() for u in get_all_users()]


def create_user(username: str, password: str, registration_code: str = "") -> Tuple[bool, str]:
    """
    Create a new user account.
    Requires a valid registration code.
    Returns (success, message).
    """
    _ensure_users_file()

    # Validate registration code
    expected_code = _get_registration_code()
    if not expected_code:
        return False, "Registration is currently disabled"
    if registration_code != expected_code:
        return False, "Invalid registration code"

    # Validate username
    if not username or len(username) < 2:
        return False, "Username must be at least 2 characters"
    if len(username) > 20:
        return False, "Username must be 20 characters or less"
    if not username.replace('_', '').replace('-', '').isalnum():
        return False, "Username can only contain letters, numbers, _ and -"

    # Validate password
    if not password or len(password) < 4:
        return False, "Password must be at least 4 characters"

    # Check if user exists
    if user_exists(username):
        return False, "Username already taken"

    # Create user
    password_hash = _hash_password(password)
    created_at = datetime.now().isoformat()

    with open(USERS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([username, password_hash, created_at])

    return True, "Account created successfully!"


def authenticate(username: str, password: str) -> Tuple[bool, str]:
    """
    Authenticate a user.
    Returns (success, message).
    """
    _ensure_users_file()

    if not username or not password:
        return False, "Please enter username and password"

    password_hash = _hash_password(password)

    with open(USERS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['username'].lower() == username.lower():
                if row['password_hash'] == password_hash:
                    return True, row['username']  # Return actual username (preserves case)
                else:
                    return False, "Incorrect password"

    return False, "User not found"


def change_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Change a user's password.
    Returns (success, message).
    """
    # Verify old password
    success, msg = authenticate(username, old_password)
    if not success:
        return False, "Current password is incorrect"

    # Validate new password
    if not new_password or len(new_password) < 4:
        return False, "New password must be at least 4 characters"

    # Read all users
    users = []
    with open(USERS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['username'].lower() == username.lower():
                row['password_hash'] = _hash_password(new_password)
            users.append(row)

    # Write back
    with open(USERS_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'password_hash', 'created_at'])
        writer.writeheader()
        writer.writerows(users)

    return True, "Password changed successfully!"
