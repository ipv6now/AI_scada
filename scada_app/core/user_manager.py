"""
User Manager - Handles user authentication and authorization
"""
import hashlib
import sqlite3
import os
from enum import Enum
from typing import Dict, List, Optional


class UserRole(Enum):
    """User roles with different permissions"""
    ADMIN = "admin"      # Full access
    ENGINEER = "engineer"  # HMI design, PLC configuration
    OPERATOR = "operator"  # View only, basic controls
    GUEST = "guest"      # View only


class User:
    """User class with authentication and authorization"""
    def __init__(self, username: str, password_hash: str, role: UserRole):
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.is_authenticated = False
    
    def check_password(self, password: str) -> bool:
        """Check if the provided password is correct"""
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, password: str) -> bool:
        """Authenticate the user with password"""
        if self.check_password(password):
            self.is_authenticated = True
            return True
        return False
    
    def logout(self):
        """Logout the user"""
        self.is_authenticated = False
    
    def has_permission(self, required_permission: str) -> bool:
        """Check if user has the required permission"""
        if not self.is_authenticated:
            return False
        
        # Define permission hierarchy
        permissions = {
            UserRole.ADMIN: ["admin", "engineer", "operator", "guest"],
            UserRole.ENGINEER: ["engineer", "operator", "guest"],
            UserRole.OPERATOR: ["operator", "guest"],
            UserRole.GUEST: ["guest"]
        }
        
        return required_permission in permissions.get(self.role, [])


class UserManager:
    """User manager for authentication and authorization"""
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "..", "database", "users.db")
        self.current_user: Optional[User] = None
        self._init_database()
        self._create_default_users()
    
    def _init_database(self):
        """Initialize the user database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _create_default_users(self):
        """Create default users if none exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if any users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin user
            admin_password = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', ("admin", admin_password, UserRole.ADMIN.value))
            
            # Create default operator user
            operator_password = hashlib.sha256("operator123".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', ("operator", operator_password, UserRole.OPERATOR.value))
            
            print("Default users created:")
            print("- admin / admin123 (Admin)")
            print("- operator / operator123 (Operator)")
        
        conn.commit()
        conn.close()
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user and return User object if successful"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, password_hash, role FROM users WHERE username = ?
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            username, password_hash, role = row
            user = User(username, password_hash, UserRole(role))
            if user.authenticate(password):
                self.current_user = user
                return user
        
        return None
    
    def logout(self):
        """Logout the current user"""
        if self.current_user:
            self.current_user.logout()
            self.current_user = None
    
    def get_current_user(self) -> Optional[User]:
        """Get the currently authenticated user"""
        return self.current_user
    
    def has_permission(self, required_permission: str) -> bool:
        """Check if current user has required permission"""
        if not self.current_user:
            return False
        return self.current_user.has_permission(required_permission)
    
    def add_user(self, username: str, password: str, role: UserRole) -> bool:
        """Add a new user"""
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', (username, password_hash, role.value))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding user: {str(e)}")
            return False
    
    def remove_user(self, username: str) -> bool:
        """Remove a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM users WHERE username = ?', (username,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error removing user: {str(e)}")
            return False
    
    def list_users(self) -> List[Dict]:
        """List all users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT username, role FROM users')
        users = [
            {"username": row[0], "role": row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return users
    
    def create_default_user(self):
        """Create a default admin user for debugging and set it as current user"""
        # Ensure default users exist
        self._create_default_users()
        
        # Create a default admin user object and authenticate it
        admin_password = hashlib.sha256("admin123".encode()).hexdigest()
        admin_user = User("admin", admin_password, UserRole.ADMIN)
        admin_user.is_authenticated = True
        self.current_user = admin_user
        print("Default admin user created and authenticated for debugging")
