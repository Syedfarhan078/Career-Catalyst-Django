from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.profiles.models import StudentProfile
from apps.profiles.forms import StudentProfileForm

User = get_user_model()

class StudentProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teststudent',
            email='student@test.com',
            password='testpassword123',
            first_name='Test',
            last_name='Student'
        )

    def test_profile_creation(self):
        profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            cgpa=9.15,
            graduation_year=2027,
            github='https://github.com/teststudent',
            linkedin='https://linkedin.com/in/teststudent'
        )
        self.assertEqual(profile.user.username, 'teststudent')
        self.assertEqual(float(profile.cgpa), 9.15)
        self.assertEqual(profile.calculate_completion_percentage(), 21) # 5 fields filled out of 23 checked fields

    def test_form_validation_phone_number_too_short(self):
        form_data = {
            'phone_number': '123',  # too short
            'cgpa': 9.0,
            'graduation_year': 2027
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_form_validation_cgpa_out_of_bounds(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 10.5,  # out of bounds (> 10)
            'graduation_year': 2027
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cgpa', form.errors)

    def test_form_validation_graduation_year_past(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2020  # in the past
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('graduation_year', form.errors)

    def test_form_validation_invalid_github_prefix(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2027,
            'github': 'https://gitlab.com/test'  # invalid prefix
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('github', form.errors)

    def test_form_validation_invalid_linkedin_prefix(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2027,
            'linkedin': 'https://facebook.com/test'  # invalid prefix
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('linkedin', form.errors)


class UnifiedSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='settingstestuser',
            email='settings@test.com',
            password='InitialPassword123!',
            first_name='OriginalFirst',
            last_name='OriginalLast',
            bio='Original User Bio'
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            cgpa=8.5,
            graduation_year=2027,
            career_goal='Software Engineer',
            bio='Original Student Bio',
            github='https://github.com/studentdev',
            linkedin='https://linkedin.com/in/studentdev'
        )
        self.client.force_login(self.user)

    def test_settings_get_renders_with_tabs_and_forms(self):
        """Verify GET /profile/edit/ renders the unified Settings page with all 3 forms."""
        response = self.client.get('/profile/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/edit_profile.html')
        self.assertIn('account_form', response.context)
        self.assertIn('profile_form', response.context)
        self.assertIn('password_form', response.context)
        self.assertContains(response, 'Account Settings')
        self.assertContains(response, 'Career & Profile')
        self.assertContains(response, 'Security & Password')
        self.assertContains(response, 'Danger Zone')

    def test_settings_update_account_preserves_independent_fields(self):
        """Verify update_account updates User without overwriting StudentProfile duplicate fields."""
        post_data = {
            'action': 'update_account',
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast',
            'email': 'updated@test.com',
            'bio': 'New Account Level Bio',
            'github': 'https://github.com/userdev',
            'linkedin': 'https://linkedin.com/in/userdev'
        }
        response = self.client.post('/profile/edit/?tab=account', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=account')

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        # User fields updated
        self.assertEqual(self.user.first_name, 'UpdatedFirst')
        self.assertEqual(self.user.last_name, 'UpdatedLast')
        self.assertEqual(self.user.email, 'updated@test.com')
        self.assertEqual(self.user.bio, 'New Account Level Bio')

        # StudentProfile fields remain independent and untouched
        self.assertEqual(self.profile.bio, 'Original Student Bio')
        self.assertEqual(self.profile.github, 'https://github.com/studentdev')

    def test_settings_update_profile_preserves_independent_fields(self):
        """Verify update_profile updates StudentProfile without overwriting User duplicate fields."""
        post_data = {
            'action': 'update_profile',
            'phone_number': '9876543210',
            'cgpa': '9.25',
            'graduation_year': '2028',
            'career_goal': 'AI Research Engineer',
            'bio': 'New Student Career Summary',
            'github': 'https://github.com/updatedstudent',
            'linkedin': 'https://linkedin.com/in/updatedstudent'
        }
        response = self.client.post('/profile/edit/?tab=profile', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=profile')

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        # StudentProfile fields updated
        self.assertEqual(self.profile.phone_number, '9876543210')
        self.assertEqual(float(self.profile.cgpa), 9.25)
        self.assertEqual(self.profile.bio, 'New Student Career Summary')
        self.assertEqual(self.profile.github, 'https://github.com/updatedstudent')

        # User bio remains independent and untouched
        self.assertEqual(self.user.bio, 'Original User Bio')

    def test_settings_change_password_success(self):
        """Verify change_password validates and updates password while preserving user session."""
        post_data = {
            'action': 'change_password',
            'old_password': 'InitialPassword123!',
            'new_password1': 'NewSecurePass2026!',
            'new_password2': 'NewSecurePass2026!'
        }
        response = self.client.post('/profile/edit/?tab=security', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=security')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass2026!'))

    def test_accounts_profile_redirects_to_settings(self):
        """Verify GET /accounts/profile/ seamlessly redirects to /profile/edit/?tab=account."""
        response = self.client.get('/accounts/profile/')
        self.assertRedirects(response, '/profile/edit/?tab=account')

    def test_profile_detail_view_renders(self):
        """Verify GET /profile/view/ renders the profile detail page in dash-shell."""
        response = self.client.get('/profile/view/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/profile.html')
        self.assertContains(response, 'Student Profile')
        self.assertContains(response, 'Software Engineer')

