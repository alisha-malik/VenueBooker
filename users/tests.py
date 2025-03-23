from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class LogoutTests(TransactionTestCase):
    def setUp(self):
        # creating a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.client = Client()
        
    def test_logout_redirects_to_login_page(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('users:logout'))
        self.assertRedirects(response, reverse('users:login'))
    
    def test_logout_terminates_session(self):
        self.client.login(username='testuser', password='testpassword123')
        
        # access a page w/c users can only access when logged in 
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 200)
        
        # logout the user
        self.client.get(reverse('users:logout'))
        
        # access the profile page again 
        response = self.client.get(reverse('users:profile'))

        # check that the user has been redireced
        self.assertEqual(response.status_code, 302)  
        
        # check w/c url the user has been redirected to
        self.assertTrue('/users/login/' in response.url)

    def test_register_page(self):
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_login_page(self):
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_login_success(self):
        # set up test user
        self.client.logout()
        
        # attempt login
        response = self.client.post(
            reverse('users:login'),
            {'username': 'testuser', 'password': 'testpassword123'},
            follow=True
        )
        
        # verify that the redirection is the same as what is expected
        self.assertRedirects(response, reverse('users:profile'))
        
        # verify that the user is authenticated after login
        self.assertTrue(response.context['user'].is_authenticated)

    def test_login_failure(self):
        response = self.client.post(reverse('users:login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertContains(response, 'Invalid credentials')

    def test_profile_page_authenticated(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/profile.html')

    def test_profile_page_unauthenticated(self):
        response = self.client.get(reverse('users:profile'))
        self.assertRedirects(response, reverse('users:login') + '?next=/users/profile/')

    def test_logout(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('users:logout'))
        self.assertRedirects(response, reverse('users:login'))
        response = self.client.get(reverse('users:profile'))
        self.assertRedirects(response, reverse('users:login') + '?next=/users/profile/')
        
        