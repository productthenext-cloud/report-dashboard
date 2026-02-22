import hashlib
import json
from datetime import datetime

def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify a password against its hash"""
    return hash_password(password) == hashed

class AuthManager:
    def __init__(self, processor):
        self.processor = processor
        self.users = {}
        self.load_users()
    
    def load_users(self):
        """Load users from storage"""
        try:
            self.users = self.processor.gs_service.get_users()
            if not self.users:
                self.create_default_users()
        except Exception as e:
            print(f"Error loading users: {str(e)}")
            self.create_default_users()
    
    def create_default_users(self):
        """Create default users"""
        default_users = {
            'admin': {
                'password': hash_password('admin123'),
                'role': 'admin',
                'name': 'Administrator',
                'telecaller_name': None,
                'permissions': {
                    'can_edit_all': True,
                    'can_delete_all': True,
                    'can_add_reports': True,
                    'can_edit_own': True,
                    'can_view_all': True,
                    'can_manage_users': True,
                    'can_export_data': True,
                    'can_view_analytics': True
                },
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True
            }
        }
        
        telecallers = ['Prakriti', 'Raphiya', 'Sudikshya', 'Shiru']
        for telecaller in telecallers:
            username = telecaller.lower()
            default_users[username] = {
                'password': hash_password(f'{username}123'),
                'role': 'telecaller',
                'name': telecaller,
                'telecaller_name': telecaller,
                'permissions': {
                    'can_edit_all': False,
                    'can_delete_all': False,
                    'can_add_reports': True,
                    'can_edit_own': True,
                    'can_view_all': False,
                    'can_manage_users': False,
                    'can_export_data': False,
                    'can_view_analytics': True
                },
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True
            }
        
        self.users = default_users
        self.save_users()
    
    def save_users(self):
        """Save users to storage"""
        try:
            self.processor.gs_service.save_users(self.users)
        except Exception as e:
            print(f"Error saving users: {str(e)}")
    
    def get_all_users(self):
        """Get all users"""
        return self.users
    
    def add_user(self, username, user_data):
        """Add new user"""
        if username in self.users:
            return False, "Username already exists"
        
        user_data['password'] = hash_password(user_data['password'])
        user_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_data['is_active'] = True
        
        if user_data['role'] == 'admin':
            user_data['permissions'] = {
                'can_edit_all': True,
                'can_delete_all': True,
                'can_add_reports': True,
                'can_edit_own': True,
                'can_view_all': True,
                'can_manage_users': True,
                'can_export_data': True,
                'can_view_analytics': True
            }
        else:
            user_data['permissions'] = {
                'can_edit_all': False,
                'can_delete_all': False,
                'can_add_reports': True,
                'can_edit_own': True,
                'can_view_all': False,
                'can_manage_users': False,
                'can_export_data': False,
                'can_view_analytics': True
            }
        
        self.users[username] = user_data
        self.save_users()
        return True, "User added successfully"
    
    def delete_user(self, username):
        """Delete user"""
        if username == 'admin':
            return False, "Cannot delete admin user"
        
        if username in self.users:
            del self.users[username]
            self.save_users()
            return True, "User deleted successfully"
        return False, "User not found"
    
    def update_permissions(self, username, permissions):
        """Update user permissions"""
        if username in self.users:
            self.users[username]['permissions'] = permissions
            self.users[username]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.save_users()
            return True, "Permissions updated successfully"
        return False, "User not found"
    
    def authenticate(self, username, password):
        """Authenticate user"""
        if username in self.users and self.users[username]['is_active']:
            if verify_password(password, self.users[username]['password']):
                return True, self.users[username]
        return False, None