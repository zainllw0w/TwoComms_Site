"""
Unit tests for authentication views (auth.py).

Tests:
- login_view: Login functionality
- register_view: User registration
- logout_view: Logout functionality
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import UserProfile


class LoginViewTests(TestCase):
    """Tests for login_view function."""
    
    def setUp(self):
        """Set up test client and test user."""
        self.client = Client()
        self.login_url = reverse('login')
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, phone='+380991234567')
    
    def test_login_page_loads(self):
        """Test that login page loads successfully."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'login')
    
    def test_login_with_valid_credentials(self):
        """Test login with correct username and password."""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Should redirect to home after successful login
        self.assertEqual(response.status_code, 302)
        
        # User should be authenticated
        self.assertTrue(self.client.session.get('_auth_user_id'))
    
    def test_login_with_invalid_credentials(self):
        """Test login with incorrect password."""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # Should stay on login page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')
    
    def test_login_with_nonexistent_user(self):
        """Test login with non-existent username."""
        response = self.client.post(self.login_url, {
            'username': 'nonexistent',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')
    
    def test_redirect_authenticated_user(self):
        """Test that authenticated user is redirected from login page."""
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Try to access login page
        response = self.client.get(self.login_url)
        
        # Should redirect to home
        self.assertEqual(response.status_code, 302)
    
    def test_login_with_next_parameter(self):
        """Test login redirect with 'next' parameter."""
        response = self.client.post(self.login_url + '?next=/profile/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Should redirect to specified page
        self.assertRedirects(response, '/profile/', fetch_redirect_response=False)


class RegisterViewTests(TestCase):
    """Tests for register_view function."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.register_url = reverse('register')
    
    def test_register_page_loads(self):
        """Test that registration page loads successfully."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'register')
    
    def test_register_new_user(self):
        """Test successful user registration."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123'
        })
        
        # Should create user
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
        # Should redirect to profile setup
        self.assertEqual(response.status_code, 302)
        
        # User should be automatically logged in
        self.assertTrue(self.client.session.get('_auth_user_id'))
    
    def test_register_with_existing_username(self):
        """Test registration with username that already exists."""
        # Create existing user
        User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='pass123'
        )
        
        # Try to register with same username
        response = self.client.post(self.register_url, {
            'username': 'existinguser',
            'email': 'new@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123'
        })
        
        # Should show error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')
    
    def test_register_with_mismatched_passwords(self):
        """Test registration with non-matching passwords."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'securepass123',
            'password2': 'differentpass123'
        })
        
        # Should show error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'password')
        
        # User should not be created
        self.assertFalse(User.objects.filter(username='newuser').exists())
    
    def test_register_with_weak_password(self):
        """Test registration with weak password."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': '123',
            'password2': '123'
        })
        
        # Should show error
        self.assertEqual(response.status_code, 200)
        
        # User should not be created
        self.assertFalse(User.objects.filter(username='newuser').exists())
    
    def test_redirect_authenticated_user_from_register(self):
        """Test that authenticated user is redirected from register page."""
        # Create and login user
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Try to access register page
        response = self.client.get(self.register_url)
        
        # Should redirect to home
        self.assertEqual(response.status_code, 302)


class LogoutViewTests(TestCase):
    """Tests for logout_view function."""
    
    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.logout_url = reverse('logout')
        
        # Create and login user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_logout_authenticated_user(self):
        """Test logout for authenticated user."""
        # Verify user is logged in
        self.assertTrue(self.client.session.get('_auth_user_id'))
        
        # Logout
        response = self.client.get(self.logout_url)
        
        # Should redirect to home
        self.assertEqual(response.status_code, 302)
        
        # User should not be authenticated
        self.assertIsNone(self.client.session.get('_auth_user_id'))
    
    def test_logout_clears_session(self):
        """Test that logout clears user session data."""
        # Add some session data
        session = self.client.session
        session['cart'] = {'test': 'data'}
        session.save()
        
        # Logout
        self.client.get(self.logout_url)
        
        # Session should be cleared
        self.assertNotIn('_auth_user_id', self.client.session)
    
    def test_logout_unauthenticated_user(self):
        """Test logout when user is not authenticated."""
        # Logout first
        self.client.logout()
        
        # Try to logout again
        response = self.client.get(self.logout_url)
        
        # Should still redirect successfully
        self.assertEqual(response.status_code, 302)


