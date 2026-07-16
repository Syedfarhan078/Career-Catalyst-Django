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
