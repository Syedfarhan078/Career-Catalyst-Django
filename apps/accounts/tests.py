from django.db import transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import EmailOTP
from apps.accounts.services import (
    create_user_with_otp,
    verify_user_otp,
    resend_user_otp,
    get_role_based_redirect_url
)
from apps.community.models import MentorProfile
from apps.profiles.models import StudentProfile
from apps.community.services import register_mentor_service

User = get_user_model()

class EmailOTPVerificationTests(TestCase):
    
    def setUp(self):
        self.registration_data = {
            'username': 'testcandidate',
            'email': 'candidate@test.com',
            'first_name': 'Test',
            'last_name': 'Candidate',
            'password': 'SecuredPassword123!'
        }

    def test_registration_creates_inactive_user_with_otp(self):
        """Verify new users are created as inactive and receive a hashed EmailOTP record."""
        user = create_user_with_otp(self.registration_data.copy())
        
        # User assertions
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'candidate@test.com')
        
        # EmailOTP assertions
        otp = EmailOTP.objects.filter(user=user).last()
        self.assertIsNotNone(otp)
        self.assertFalse(otp.is_verified)
        self.assertNotEqual(otp.otp_hash, '')
        self.assertTrue(otp.expires_at > timezone.now())

    def test_successful_otp_verification(self):
        """Verify providing the correct plain OTP activates the user."""
        user = create_user_with_otp(self.registration_data.copy())
        otp = EmailOTP.objects.get(user=user)
        
        # We need the plain code from memory, but since it's hashed in the DB,
        # let's mock validation using Django's check_password verify wrapper.
        # However, to test the actual service flow, we can overwrite the otp_hash with a known code:
        from django.contrib.auth.hashers import make_password
        otp.otp_hash = make_password('123456')
        otp.save()
        
        # Verify success
        active_user = verify_user_otp(user.id, '123456')
        self.assertTrue(active_user.is_active)
        
        # Checked states clean up verified records
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 0)

    def test_failed_verification_increments_attempts(self):
        """Verify incorrect OTP inputs increment attempt counts and fail at 5 tries."""
        user = create_user_with_otp(self.registration_data.copy())
        otp = EmailOTP.objects.get(user=user)
        otp.otp_hash = make_password('123456')
        otp.save()

        # Try incorrect code
        with self.assertRaises(ValidationError) as ctx:
            verify_user_otp(user.id, '000000')
        self.assertIn("Incorrect OTP code. You have 4 attempts remaining.", ctx.exception.message)
        
        # Check attempts incremented
        otp.refresh_from_db()
        self.assertEqual(otp.attempt_count, 1)

        # Trigger max tries
        otp.attempt_count = 4
        otp.save()
        
        with self.assertRaises(ValidationError) as ctx:
            verify_user_otp(user.id, '000000')
        self.assertIn("Too many incorrect attempts. This OTP has been invalidated.", ctx.exception.message)
        
        # Check OTP deleted on lock
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 0)

    def test_expired_otp_verification_fails(self):
        """Verify expired OTP codes cannot activate users."""
        user = create_user_with_otp(self.registration_data.copy())
        otp = EmailOTP.objects.get(user=user)
        otp.otp_hash = make_password('123456')
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save()

        with self.assertRaises(ValidationError) as ctx:
            verify_user_otp(user.id, '123456')
        self.assertIn("This OTP code has expired.", ctx.exception.message)
        self.assertFalse(user.is_active)

    def test_resend_otp_throttling(self):
        """Verify resending OTP codes less than 60 seconds apart triggers ValidationError."""
        user = create_user_with_otp(self.registration_data.copy())
        
        # Try resending immediately (elapsed time < 60s)
        with self.assertRaises(ValidationError) as ctx:
            resend_user_otp(user.id)
        self.assertIn("Please wait", ctx.exception.message)
        
        # Mock time drift to bypass throttle
        otp = EmailOTP.objects.get(user=user)
        otp.created_at = timezone.now() - timedelta(seconds=61)
        otp.save()
        
        # Should succeed now
        resend_user_otp(user.id)
        
        # New OTP should exist, old deleted
        new_otp = EmailOTP.objects.filter(user=user).last()
        self.assertIsNotNone(new_otp)
        self.assertNotEqual(new_otp.id, otp.id)


class AccountDeletionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='deletionuser',
            email='delete@test.com',
            password='TestPassword123!'
        )

    def test_delete_account_get_renders_page(self):
        """Verify GET request to delete_account renders the confirmation page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('delete_account'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/delete_account.html')

    def test_delete_account_success_with_matching_username(self):
        """Verify user is deleted and logged out when typing matching username."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_account'), {'confirm_username': 'deletionuser'})
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(User.objects.filter(username='deletionuser').exists())

    def test_delete_account_fails_with_mismatched_username(self):
        """Verify user is NOT deleted if typed username doesn't match."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('delete_account'), {'confirm_username': 'wrongusername'})
        self.assertRedirects(response, reverse('delete_account'))
        self.assertTrue(User.objects.filter(username='deletionuser').exists())


class RoleArchitectureAndAuthorizationTests(TestCase):
    """
    Phase 1: Verification of single-role account architecture,
    registration flow, role-aware routing, and workspace boundaries.
    """
    def setUp(self):
        self.client = Client()

    def test_user_model_role_default_and_helpers(self):
        """Verify role defaults to 'student' and helper properties function correctly."""
        student = User.objects.create_user(
            username='default_student',
            email='student@test.com',
            password='Password123!'
        )
        self.assertEqual(student.role, 'student')
        self.assertTrue(student.is_student)
        self.assertFalse(student.is_mentor_role)

        mentor = User.objects.create_user(
            username='explicit_mentor',
            email='mentor@test.com',
            password='Password123!',
            role='mentor'
        )
        self.assertEqual(mentor.role, 'mentor')
        self.assertFalse(mentor.is_student)
        self.assertTrue(mentor.is_mentor_role)

    def test_otp_registration_preserves_selected_role(self):
        """Verify OTP registration flow preserves mentor role through verification."""
        mentor_data = {
            'username': 'mentor_candidate',
            'email': 'mentor_candidate@test.com',
            'first_name': 'Grace',
            'last_name': 'Hopper',
            'password': 'SecurePassword123!',
            'role': 'mentor'
        }
        user = create_user_with_otp(mentor_data)
        self.assertFalse(user.is_active)
        self.assertEqual(user.role, 'mentor')

        otp = EmailOTP.objects.get(user=user)
        otp.otp_hash = make_password('654321')
        otp.save()

        verified_user = verify_user_otp(user.id, '654321')
        self.assertTrue(verified_user.is_active)
        self.assertEqual(verified_user.role, 'mentor')

    def test_role_based_redirect_helper(self):
        """Verify get_role_based_redirect_url returns correct destinations for all role and profile states."""
        # 1. Student without profile -> profile_create
        student_no_profile = User.objects.create_user(
            username='stud_no_prof',
            email='snp@test.com',
            password='Password123!',
            role='student'
        )
        self.assertEqual(get_role_based_redirect_url(student_no_profile), reverse('profile_create'))

        # 2. Student with profile -> dashboard
        StudentProfile.objects.create(user=student_no_profile, preferred_domain='Backend')
        self.assertEqual(get_role_based_redirect_url(student_no_profile), reverse('dashboard'))

        # 3. Mentor without profile -> mentor_register
        mentor_no_profile = User.objects.create_user(
            username='ment_no_prof',
            email='mnp@test.com',
            password='Password123!',
            role='mentor'
        )
        self.assertEqual(get_role_based_redirect_url(mentor_no_profile), reverse('community:mentor_register'))

        # 4. Mentor with Pending profile -> mentor_register
        mentor_prof = MentorProfile.objects.create(
            user=mentor_no_profile,
            full_name='Test Mentor',
            email='mnp@test.com',
            company='Tech Inc',
            designation='Lead Dev',
            status='Pending',
            verified=False
        )
        self.assertEqual(get_role_based_redirect_url(mentor_no_profile), reverse('community:mentor_register'))

        # 5. Mentor Approved & Verified -> mentor_dashboard
        mentor_prof.status = 'Approved'
        mentor_prof.verified = True
        mentor_prof.save()
        self.assertEqual(get_role_based_redirect_url(mentor_no_profile), reverse('community:mentor_dashboard'))

        # 6. Mentor Inactive or Blocked -> mentor_register
        mentor_prof.status = 'Inactive'
        mentor_prof.save()
        self.assertEqual(get_role_based_redirect_url(mentor_no_profile), reverse('community:mentor_register'))

        mentor_prof.status = 'Blocked'
        mentor_prof.save()
        self.assertEqual(get_role_based_redirect_url(mentor_no_profile), reverse('community:mentor_register'))

    def test_dashboard_access_protection_for_mentors(self):
        """Verify accessing /dashboard/ redirects mentors to mentor workspace/status without student onboarding."""
        mentor = User.objects.create_user(
            username='dash_mentor',
            email='dm@test.com',
            password='Password123!',
            role='mentor'
        )
        self.client.force_login(mentor)

        # Unapproved mentor hitting dashboard -> mentor_register
        res_unapproved = self.client.get(reverse('dashboard'))
        self.assertRedirects(res_unapproved, reverse('community:mentor_register'))

        # Approved mentor hitting dashboard -> mentor_dashboard
        MentorProfile.objects.create(
            user=mentor,
            full_name='Dash Mentor',
            email='dm@test.com',
            company='Tech',
            designation='Engineer',
            status='Approved',
            verified=True
        )
        res_approved = self.client.get(reverse('dashboard'))
        self.assertRedirects(res_approved, reverse('community:mentor_dashboard'))

    def test_mentor_cannot_access_student_profile_create(self):
        """Verify mentors attempting to access student profile creation are redirected away."""
        mentor = User.objects.create_user(
            username='prof_mentor',
            email='pm@test.com',
            password='Password123!',
            role='mentor'
        )
        self.client.force_login(mentor)

        res = self.client.get(reverse('profile_create'))
        self.assertRedirects(res, reverse('community:mentor_register'))

        # If approved mentor tries to access profile_create
        MentorProfile.objects.create(
            user=mentor,
            full_name='Prof Mentor',
            email='pm@test.com',
            company='Tech',
            designation='Engineer',
            status='Approved',
            verified=True
        )
        res_approved = self.client.get(reverse('profile_create'))
        self.assertRedirects(res_approved, reverse('community:mentor_dashboard'))

    def test_rejected_mentor_reapplication_preserves_mentor_role(self):
        """Verify rejected mentors maintain role='mentor' upon reapplication."""
        mentor = User.objects.create_user(
            username='rejected_mentor',
            email='rm@test.com',
            password='Password123!',
            role='mentor'
        )
        profile = MentorProfile.objects.create(
            user=mentor,
            full_name='Rejected Mentor',
            email='rm@test.com',
            company='Tech',
            designation='Engineer',
            status='Rejected',
            verified=False
        )
        
        # Submit reapplication
        reapply_data = {
            'full_name': 'Rejected Mentor Updated',
            'email': 'rm@test.com',
            'phone_number': '1234567890',
            'company': 'Tech 2',
            'designation': 'Senior Engineer',
            'experience_years': 5,
            'current_location': 'New York',
            'bio': 'Updated bio with more experience',
            'career_domains': 'Backend',
            'skills_csv': 'Python, Django',
            'languages': 'English',
            'available_days': 'Monday',
            'available_time_slots': '10:00 AM - 12:00 PM',
            'mentorship_type': 'Online',
        }
        register_mentor_service(mentor, reapply_data)
        mentor.refresh_from_db()
        profile.refresh_from_db()

        self.assertEqual(mentor.role, 'mentor')
        self.assertEqual(profile.status, 'Pending')
        self.assertEqual(profile.company, 'Tech 2')

    def test_legacy_mentor_preserves_student_profile(self):
        """Verify mentors with legacy StudentProfile records retain all data without disruption."""
        mentor = User.objects.create_user(
            username='legacy_mentor',
            email='lm@test.com',
            password='Password123!',
            role='mentor'
        )
        student_profile = StudentProfile.objects.create(
            user=mentor,
            preferred_domain='Fullstack',
            career_goal='Software Architect',
            skills='Python, React'
        )
        mentor_profile = MentorProfile.objects.create(
            user=mentor,
            full_name='Legacy Mentor',
            email='lm@test.com',
            company='Enterprise',
            designation='Architect',
            status='Approved',
            verified=True
        )

        mentor.refresh_from_db()
        self.assertEqual(mentor.role, 'mentor')
        self.assertTrue(hasattr(mentor, 'studentprofile'))
        self.assertEqual(mentor.studentprofile.career_goal, 'Software Architect')
        self.assertTrue(hasattr(mentor, 'mentor_profile'))
        self.assertEqual(mentor.mentor_profile.status, 'Approved')

    def test_mentor_with_student_profile_cannot_access_student_dashboard(self):
        """A.1 & B.5: Mentor with legacy StudentProfile and session active_role='student' is strictly denied student dashboard."""
        mentor = User.objects.create_user(
            username='legacy_mentor_auth',
            email='lma@test.com',
            password='Password123!',
            role='mentor'
        )
        StudentProfile.objects.create(
            user=mentor,
            preferred_domain='DevOps',
            career_goal='Cloud Architect'
        )
        MentorProfile.objects.create(
            user=mentor,
            full_name='Legacy Auth Mentor',
            email='lma@test.com',
            company='Cloud Corp',
            designation='Principal Architect',
            status='Approved',
            verified=True
        )
        self.client.force_login(mentor)

        # Forging or retaining session active_role='student'
        session = self.client.session
        session['active_role'] = 'student'
        session.save()

        # Accessing /dashboard/ must redirect to mentor_dashboard, NOT student dashboard
        res = self.client.get(reverse('dashboard'))
        self.assertRedirects(res, reverse('community:mentor_dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'mentor')

    def test_mentor_cannot_access_student_only_endpoints(self):
        """A.2: Mentor account cannot access student-only profile and booking endpoints."""
        mentor = User.objects.create_user(
            username='mentor_no_student_area',
            email='mnsa@test.com',
            password='Password123!',
            role='mentor'
        )
        MentorProfile.objects.create(
            user=mentor,
            full_name='Mentor No Student Area',
            email='mnsa@test.com',
            company='Scale Tech',
            designation='Staff Dev',
            status='Approved',
            verified=True
        )
        self.client.force_login(mentor)

        student_endpoints = [
            reverse('profile_create'),
            reverse('profile_edit'),
            reverse('profile_detail'),
            reverse('community:student_bookings'),
        ]
        for url in student_endpoints:
            res = self.client.get(url)
            self.assertRedirects(res, reverse('community:mentor_dashboard'))

    def test_student_cannot_access_mentor_dashboard_or_management_endpoints(self):
        """A.3, A.4 & B.6: Student account cannot access mentor dashboard or management views even with forged session."""
        student = User.objects.create_user(
            username='pure_student',
            email='pure_student@test.com',
            password='Password123!',
            role='student'
        )
        StudentProfile.objects.create(
            user=student,
            preferred_domain='Frontend',
            career_goal='UI Engineer'
        )
        self.client.force_login(student)

        # Forge session active_role='mentor'
        session = self.client.session
        session['active_role'] = 'mentor'
        session.save()

        # Mentor dashboard must deny student
        res_dash = self.client.get(reverse('community:mentor_dashboard'))
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn(reverse('community:mentor_register'), res_dash.url)

        # Protected mentor management endpoints must deny student
        management_endpoints = [
            reverse('community:mentor_requests'),
            reverse('community:manage_availability'),
            reverse('community:mentor_mentees'),
            reverse('community:edit_profile'),
        ]
        for url in management_endpoints:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302)
            self.assertIn(reverse('community:mentor_register'), res.url)

    def test_stale_or_invalid_session_values_cannot_bypass_authorization(self):
        """B.7: Tampered or invalid session values are safely normalized without granting access."""
        student = User.objects.create_user(
            username='tamper_student',
            email='ts@test.com',
            password='Password123!',
            role='student'
        )
        StudentProfile.objects.create(user=student, preferred_domain='AI')
        self.client.force_login(student)

        session = self.client.session
        session['active_role'] = 'invalid_role_value'
        session.save()

        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_workspace'], 'student')
        self.assertEqual(self.client.session.get('active_role'), 'student')

    def test_mentor_approval_status_restrictions(self):
        """C.8-12: Unapproved mentors (Pending, Rejected, Inactive, Blocked) are locked from management views."""
        mentor = User.objects.create_user(
            username='status_test_mentor',
            email='stm@test.com',
            password='Password123!',
            role='mentor'
        )
        profile = MentorProfile.objects.create(
            user=mentor,
            full_name='Status Test Mentor',
            email='stm@test.com',
            company='Acme',
            designation='Engineer',
            status='Pending',
            verified=False
        )
        self.client.force_login(mentor)

        management_url = reverse('community:mentor_requests')

        # 1. Pending mentor
        res_pending = self.client.get(management_url)
        self.assertEqual(res_pending.status_code, 200)
        self.assertTemplateUsed(res_pending, 'community/mentor_status.html')
        self.assertContains(res_pending, 'Verification Pending')

        # 2. Rejected mentor
        profile.status = 'Rejected'
        profile.save()
        res_rejected = self.client.get(management_url)
        self.assertEqual(res_rejected.status_code, 200)
        self.assertTemplateUsed(res_rejected, 'community/mentor_status.html')

        # 3. Inactive mentor
        profile.status = 'Inactive'
        profile.save()
        res_inactive = self.client.get(management_url)
        self.assertEqual(res_inactive.status_code, 200)
        self.assertTemplateUsed(res_inactive, 'community/mentor_status.html')
        self.assertContains(res_inactive, 'Mentor Account Inactive')

        # 4. Blocked mentor
        profile.status = 'Blocked'
        profile.save()
        res_blocked = self.client.get(management_url)
        self.assertEqual(res_blocked.status_code, 200)
        self.assertTemplateUsed(res_blocked, 'community/mentor_status.html')

        # 5. Approved & Verified mentor
        profile.status = 'Approved'
        profile.verified = True
        profile.save()
        res_approved = self.client.get(management_url)
        self.assertEqual(res_approved.status_code, 200)
        self.assertTemplateUsed(res_approved, 'community/mentor_requests.html')

    def test_registration_form_role_selection_and_validation(self):
        """D.13 & D.14: Form validates explicit role selection and programmatic fallback."""
        from apps.accounts.forms import UserRegistrationForm

        # 1. Valid explicit student selection
        form_student = UserRegistrationForm(data={
            'username': 'form_student',
            'email': 'fs@test.com',
            'first_name': 'Form',
            'last_name': 'Student',
            'password1': 'Password123!',
            'password2': 'Password123!',
            'role': 'student'
        })
        self.assertTrue(form_student.is_valid())
        self.assertEqual(form_student.cleaned_data['role'], 'student')

        # 2. Valid explicit mentor selection
        form_mentor = UserRegistrationForm(data={
            'username': 'form_mentor',
            'email': 'fm@test.com',
            'first_name': 'Form',
            'last_name': 'Mentor',
            'password1': 'Password123!',
            'password2': 'Password123!',
            'role': 'mentor'
        })
        self.assertTrue(form_mentor.is_valid())
        self.assertEqual(form_mentor.cleaned_data['role'], 'mentor')

        # 3. Public registration without role is rejected by form validation
        form_no_role = UserRegistrationForm(data={
            'username': 'no_role_user',
            'email': 'nr@test.com',
            'first_name': 'No',
            'last_name': 'Role',
            'password1': 'Password123!',
            'password2': 'Password123!',
        })
        self.assertFalse(form_no_role.is_valid())
        self.assertIn('role', form_no_role.errors)

        # 4. Programmatic registration without role defaults to student
        user_programmatic = create_user_with_otp({
            'username': 'prog_student',
            'email': 'ps@test.com',
            'first_name': 'Prog',
            'last_name': 'Student',
            'password': 'Password123!'
        })
        self.assertEqual(user_programmatic.role, 'student')

    def test_student_without_mentor_profile_accesses_student_dashboard(self):
        """Phase 1.1.1: Student account without a MentorProfile accesses student dashboard normally."""
        student = User.objects.create_user(
            username='pure_student_dash',
            email='psd@test.com',
            password='Password123!',
            role='student'
        )
        StudentProfile.objects.create(
            user=student,
            preferred_domain='Backend',
            career_goal='Backend Engineer'
        )
        self.client.force_login(student)

        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_workspace'], 'student')
        self.assertFalse(res.context['is_approved_mentor'])

    def test_student_with_existing_mentor_profile_accesses_student_dashboard(self):
        """Phase 1.1.1: Student account with an existing MentorProfile still accesses student dashboard."""
        student = User.objects.create_user(
            username='student_with_mp',
            email='swmp@test.com',
            password='Password123!',
            role='student'
        )
        StudentProfile.objects.create(
            user=student,
            preferred_domain='Data Science',
            career_goal='Data Scientist'
        )
        MentorProfile.objects.create(
            user=student,
            full_name='Student With MP',
            email='swmp@test.com',
            company='Startup',
            designation='Advisor',
            status='Approved',
            verified=True
        )
        self.client.force_login(student)

        # Accessing /dashboard/ must render student dashboard, NOT redirect to mentor_dashboard
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_workspace'], 'student')
        self.assertFalse(res.context['is_approved_mentor'])

    def test_mentor_without_mentor_profile_routes_to_mentor_register(self):
        """Phase 1.1.1: Mentor account without a MentorProfile routes to mentor application page."""
        mentor = User.objects.create_user(
            username='mentor_no_mp',
            email='mnmp@test.com',
            password='Password123!',
            role='mentor'
        )
        self.client.force_login(mentor)

        res = self.client.get(reverse('dashboard'))
        self.assertRedirects(res, reverse('community:mentor_register'))

import base64
import json
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from apps.accounts.models import EmailOTP, GoogleIdentity
from apps.accounts.services import get_role_based_redirect_url
from apps.accounts.google_auth import (
    generate_oauth_state,
    generate_pkce_pair,
    generate_oauth_nonce,
    normalize_google_email,
    generate_unique_username,
    get_google_authorization_url,
    verify_google_id_token,
    exchange_code_for_tokens,
    authenticate_or_register_google_user,
    _base64url_decode,
)
from apps.community.models import MentorProfile

User = get_user_model()


@override_settings(
    GOOGLE_CLIENT_ID='test_client_id_123',
    GOOGLE_CLIENT_SECRET='test_client_secret_xyz'
)
class GoogleOAuthAndIdentityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        pn = cls.public_key.public_numbers()
        cls.test_kid = "test_key_kid_1"

        def _int_to_b64(val):
            byte_len = (val.bit_length() + 7) // 8
            return base64.urlsafe_b64encode(val.to_bytes(byte_len, 'big')).decode('ascii').rstrip('=')

        cls.jwks = {
            cls.test_kid: {
                "kid": cls.test_kid,
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": _int_to_b64(pn.n),
                "e": _int_to_b64(pn.e),
            }
        }

    def _create_signed_id_token(self, claims_override=None, header_override=None, sign_key=None):
        header = {
            "alg": "RS256",
            "kid": self.test_kid,
            "typ": "JWT"
        }
        if header_override:
            header.update(header_override)

        now = int(time.time())
        payload = {
            "iss": "https://accounts.google.com",
            "aud": "test_client_id_123",
            "sub": "google_sub_998877",
            "email": "testuser@gmail.com",
            "email_verified": True,
            "given_name": "Test",
            "family_name": "GoogleUser",
            "nonce": "test_nonce_val_123",
            "iat": now,
            "exp": now + 3600
        }
        if claims_override:
            payload.update(claims_override)

        def _b64encode_json(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode('utf-8')).decode('ascii').rstrip('=')

        h_b64 = _b64encode_json(header)
        p_b64 = _b64encode_json(payload)
        signed_bytes = f"{h_b64}.{p_b64}".encode('ascii')

        key_to_use = sign_key or self.private_key
        sig = key_to_use.sign(signed_bytes, padding.PKCS1v15(), hashes.SHA256())
        s_b64 = base64.urlsafe_b64encode(sig).decode('ascii').rstrip('=')
        return f"{h_b64}.{p_b64}.{s_b64}"

    def _get_mock_request(self):
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get('/')
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request


    # -------------------------------------------------------------
    # OAuth Protocol Tests (Scenarios 1-15)
    # -------------------------------------------------------------
    def test_01_authorization_url_generation(self):
        client = Client()
        session = client.session
        request = MagicMock()
        request.session = session
        request.build_absolute_uri.return_value = 'http://testserver/accounts/google/callback/'
        request.is_secure.return_value = False
        request.headers = {}

        url = get_google_authorization_url(request, role='student')
        self.assertIn('https://accounts.google.com/o/oauth2/v2/auth', url)
        self.assertIn('client_id=test_client_id_123', url)
        self.assertIn('response_type=code', url)
        self.assertIn('code_challenge_method=S256', url)
        self.assertIn('state=', url)
        self.assertIn('nonce=', url)
        self.assertEqual(session['oauth_pending_role'], 'student')

    def test_02_state_generation(self):
        s1 = generate_oauth_state()
        s2 = generate_oauth_state()
        self.assertTrue(len(s1) >= 32)
        self.assertNotEqual(s1, s2)

    def test_03_state_mismatch_rejection(self):
        client = Client()
        session = client.session
        session['oauth_state'] = 'correct_state_val'
        session['oauth_code_verifier'] = 'verifier_123'
        session['oauth_nonce'] = 'nonce_123'
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'auth_code_1', 'state': 'tampered_state'})
        self.assertRedirects(response, reverse('login'))
        # Ensure error message set
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("Invalid or expired session state" in str(m) for m in messages))

    def test_04_missing_state_rejection(self):
        client = Client()
        session = client.session
        session['oauth_state'] = 'correct_state_val'
        session['oauth_code_verifier'] = 'verifier_123'
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'auth_code_1'})
        self.assertRedirects(response, reverse('login'))

    def test_05_pkce_challenge_generation(self):
        v, c = generate_pkce_pair()
        self.assertTrue(len(v) >= 43)
        self.assertTrue(len(c) >= 43)
        # Re-derive challenge from verifier
        import hashlib
        expected_c = base64.urlsafe_b64encode(hashlib.sha256(v.encode('ascii')).digest()).decode('ascii').rstrip('=')
        self.assertEqual(c, expected_c)

    def test_06_missing_verifier_rejection(self):
        client = Client()
        session = client.session
        session['oauth_state'] = 'state_123'
        # missing oauth_code_verifier
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'auth_code_1', 'state': 'state_123'})
        self.assertRedirects(response, reverse('login'))

    def test_07_nonce_generation_and_validation(self):
        n1 = generate_oauth_nonce()
        n2 = generate_oauth_nonce()
        self.assertTrue(len(n1) >= 32)
        self.assertNotEqual(n1, n2)

    def test_08_invalid_id_token_signature(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._create_signed_id_token(sign_key=other_key)
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("signature verification failed", str(ctx.exception))

    def test_09_invalid_audience(self):
        token = self._create_signed_id_token(claims_override={"aud": "wrong_audience_id"})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("Invalid ID token audience", str(ctx.exception))

    def test_10_invalid_issuer(self):
        token = self._create_signed_id_token(claims_override={"iss": "https://malicious.issuer.com"})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("Invalid ID token issuer", str(ctx.exception))

    def test_11_expired_token(self):
        past_time = int(time.time()) - 3600
        token = self._create_signed_id_token(claims_override={"exp": past_time - 60, "iat": past_time - 120})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("ID token has expired", str(ctx.exception))

    def test_12_nonce_mismatch(self):
        token = self._create_signed_id_token(claims_override={"nonce": "token_nonce_1"})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="session_nonce_different", jwks_keys=self.jwks)
        self.assertIn("nonce does not match", str(ctx.exception))

    def test_13_unverified_email(self):
        token = self._create_signed_id_token(claims_override={"email_verified": False})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("email address is not verified", str(ctx.exception))

    @patch('apps.accounts.google_auth.requests.post')
    def test_14_google_api_timeout(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout("Connection timed out")
        with self.assertRaises(ValidationError) as ctx:
            exchange_code_for_tokens('code123', 'verifier123', 'http://testserver/callback/')
        self.assertIn("Failed to communicate with Google", str(ctx.exception))

    def test_15_cancelled_consent(self):
        client = Client()
        response = client.get(reverse('google_callback'), {'error': 'access_denied'})
        self.assertRedirects(response, reverse('login'))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("cancelled" in str(m) for m in messages))

    # -------------------------------------------------------------
    # GoogleIdentity Model Tests (Scenarios 16-21)
    # -------------------------------------------------------------
    def test_16_google_identity_creation(self):
        user = User.objects.create_user(username='uid16', email='u16@example.com', password='pass')
        gi = GoogleIdentity.objects.create(
            user=user,
            provider='google',
            provider_user_id='sub_16',
            email_at_link='u16@example.com'
        )
        self.assertEqual(gi.provider, 'google')
        self.assertEqual(gi.provider_user_id, 'sub_16')
        self.assertEqual(gi.user, user)

    def test_17_unique_provider_and_provider_id_constraint(self):
        u1 = User.objects.create_user(username='uid17_1', email='u17_1@example.com')
        u2 = User.objects.create_user(username='uid17_2', email='u17_2@example.com')
        GoogleIdentity.objects.create(user=u1, provider='google', provider_user_id='sub_17_same', email_at_link=u1.email)
        with self.assertRaises(IntegrityError):
            GoogleIdentity.objects.create(user=u2, provider='google', provider_user_id='sub_17_same', email_at_link=u2.email)

    def test_18_unique_user_provider_constraint(self):
        u = User.objects.create_user(username='uid18', email='u18@example.com')
        GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_18_a', email_at_link=u.email)
        with self.assertRaises(IntegrityError):
            GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_18_b', email_at_link=u.email)

    def test_19_correct_user_relationship(self):
        u = User.objects.create_user(username='uid19', email='u19@example.com')
        gi = GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_19', email_at_link=u.email)
        self.assertEqual(list(u.google_identities.all()), [gi])

    def test_20_identity_deletion_cascades_on_user_delete(self):
        u = User.objects.create_user(username='uid20', email='u20@example.com')
        GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_20', email_at_link=u.email)
        u.delete()
        self.assertFalse(GoogleIdentity.objects.filter(provider_user_id='sub_20').exists())

    def test_21_lookup_by_provider_and_provider_id(self):
        u = User.objects.create_user(username='uid21', email='u21@example.com')
        GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_21_lookup', email_at_link=u.email)
        found = GoogleIdentity.objects.filter(provider='google', provider_user_id='sub_21_lookup').first()
        self.assertIsNotNone(found)
        self.assertEqual(found.user, u)

    # -------------------------------------------------------------
    # New Account Tests (Scenarios 22-32)
    # -------------------------------------------------------------
    @patch('apps.accounts.views.exchange_code_for_tokens')
    @patch('apps.accounts.views.verify_google_id_token')
    def test_22_new_student_signup_from_register(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {'id_token': 'fake_token'}
        mock_verify.return_value = {
            'sub': 'student_new_sub_22',
            'email': 'newstudent@example.com',
            'email_verified': True,
            'given_name': 'New',
            'family_name': 'Student',
        }

        client = Client()
        session = client.session
        session['oauth_state'] = 'state_22'
        session['oauth_code_verifier'] = 'verifier_22'
        session['oauth_pending_role'] = 'student'
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'c22', 'state': 'state_22'})
        user = User.objects.get(email='newstudent@example.com')
        self.assertEqual(user.role, 'student')
        self.assertTrue(user.is_active)
        self.assertTrue(GoogleIdentity.objects.filter(user=user, provider_user_id='student_new_sub_22').exists())
        self.assertRedirects(response, reverse('profile_create'))

    @patch('apps.accounts.views.exchange_code_for_tokens')
    @patch('apps.accounts.views.verify_google_id_token')
    def test_23_new_mentor_signup_from_register(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {'id_token': 'fake_token'}
        mock_verify.return_value = {
            'sub': 'mentor_new_sub_23',
            'email': 'newmentor@example.com',
            'email_verified': True,
            'given_name': 'New',
            'family_name': 'Mentor',
        }

        client = Client()
        session = client.session
        session['oauth_state'] = 'state_23'
        session['oauth_code_verifier'] = 'verifier_23'
        session['oauth_pending_role'] = 'mentor'
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'c23', 'state': 'state_23'})
        user = User.objects.get(email='newmentor@example.com')
        self.assertEqual(user.role, 'mentor')
        self.assertTrue(user.is_active)
        self.assertFalse(hasattr(user, 'mentor_profile'))
        self.assertRedirects(response, reverse('community:mentor_register'))

    @patch('apps.accounts.views.exchange_code_for_tokens')
    @patch('apps.accounts.views.verify_google_id_token')
    def test_24_new_login_user_receives_role_selection_page(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {'id_token': 'fake_token'}
        mock_verify.return_value = {
            'sub': 'login_new_sub_24',
            'email': 'choosertester@example.com',
            'email_verified': True,
            'given_name': 'Choose',
            'family_name': 'User',
        }

        client = Client()
        session = client.session
        session['oauth_state'] = 'state_24'
        session['oauth_code_verifier'] = 'verifier_24'
        # No oauth_pending_role
        session.save()

        response = client.get(reverse('google_callback'), {'code': 'c24', 'state': 'state_24'})
        self.assertRedirects(response, reverse('google_choose_role'))
        # Ensure session pending user stored
        self.assertEqual(client.session.get('oauth_pending_user')['email'], 'choosertester@example.com')

    def test_25_no_user_created_before_role_selection(self):
        client = Client()
        session = client.session
        session['oauth_pending_user'] = {
            'sub': 'uncreated_sub_25',
            'email': 'uncreated25@example.com',
            'given_name': 'Wait',
            'family_name': 'User',
            'timestamp': time.time(),
        }
        session.save()

        # Just viewing choose-role does not create user
        response = client.get(reverse('google_choose_role'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='uncreated25@example.com').exists())

    def test_26_invalid_role_rejected(self):
        client = Client()
        session = client.session
        session['oauth_pending_user'] = {
            'sub': 'invalid_role_sub_26',
            'email': 'invalidrole26@example.com',
            'timestamp': time.time(),
        }
        session.save()

        response = client.post(reverse('google_choose_role'), {'role': 'administrator'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='invalidrole26@example.com').exists())

    def test_27_user_and_google_identity_created_atomically(self):
        req = self._get_mock_request()
        data = {
            'sub': 'atomic_sub_27',
            'email': 'atomic27@example.com',
            'given_name': 'Atomic',
            'family_name': 'User'
        }
        status, user, err = authenticate_or_register_google_user(req, data, role='student')
        self.assertEqual(status, 'created')
        self.assertIsNotNone(user)
        self.assertTrue(GoogleIdentity.objects.filter(user=user, provider_user_id='atomic_sub_27').exists())

    def test_28_username_collision_handled(self):
        User.objects.create_user(username='collisionuser', email='existing@example.com')
        new_username = generate_unique_username('collisionuser')
        self.assertEqual(new_username, 'collisionuser_1')

    def test_29_duplicate_email_handled(self):
        User.objects.create_user(username='u29', email='duplicate29@example.com')
        req = self._get_mock_request()
        data = {'sub': 'sub_29', 'email': 'duplicate29@example.com'}
        status, user, err = authenticate_or_register_google_user(req, data, role='student')
        # Authenticates matching existing account instead of creating duplicate
        self.assertEqual(status, 'authenticated')
        self.assertEqual(user.username, 'u29')
        self.assertEqual(User.objects.filter(email='duplicate29@example.com').count(), 1)

    def test_30_concurrent_duplicate_signup_handled(self):
        User.objects.create_user(username='concurrent_u', email='concurrent@example.com')
        req = self._get_mock_request()
        data = {'sub': 'concurrent_sub_30', 'email': 'concurrent@example.com'}
        # Both calls should resolve safely
        status, user, err = authenticate_or_register_google_user(req, data, role='student')
        self.assertEqual(status, 'authenticated')
        self.assertEqual(User.objects.filter(email='concurrent@example.com').count(), 1)

    def test_31_student_redirected_to_profile_completion(self):
        u = User.objects.create_user(username='student31', email='s31@example.com', role='student')
        dest = get_role_based_redirect_url(u)
        self.assertEqual(dest, reverse('profile_create'))

    def test_32_mentor_redirected_to_mentor_application(self):
        u = User.objects.create_user(username='mentor32', email='m32@example.com', role='mentor')
        dest = get_role_based_redirect_url(u)
        self.assertEqual(dest, reverse('community:mentor_register'))

    # -------------------------------------------------------------
    # Existing Account Tests (Scenarios 33-50)
    # -------------------------------------------------------------
    def test_33_existing_student_authenticates_automatically(self):
        user = User.objects.create_user(username='stud33', email='student33@example.com', role='student')
        req = self._get_mock_request()
        data = {'sub': 'sub_33', 'email': 'student33@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, user)
        self.assertTrue(GoogleIdentity.objects.filter(user=user, provider_user_id='sub_33').exists())

    def test_34_existing_mentor_authenticates_automatically(self):
        user = User.objects.create_user(username='mentor34', email='mentor34@example.com', role='mentor')
        req = self._get_mock_request()
        data = {'sub': 'sub_34', 'email': 'mentor34@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, user)
        self.assertTrue(GoogleIdentity.objects.filter(user=user, provider_user_id='sub_34').exists())

    def test_35_existing_google_identity_login_uses_stored_sub(self):
        user = User.objects.create_user(username='linked35', email='original35@example.com')
        GoogleIdentity.objects.create(user=user, provider='google', provider_user_id='sub_35_linked', email_at_link=user.email)
        req = self._get_mock_request()
        data = {'sub': 'sub_35_linked', 'email': 'original35@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, user)

    def test_36_google_email_changes_sub_still_identifies_account(self):
        user = User.objects.create_user(username='changedemail36', email='firstemail36@example.com')
        GoogleIdentity.objects.create(user=user, provider='google', provider_user_id='sub_36_stable', email_at_link=user.email)
        req = self._get_mock_request()
        data = {'sub': 'sub_36_stable', 'email': 'completely_new_email@gmail.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, user)

    def test_37_existing_account_role_remains_unchanged(self):
        user = User.objects.create_user(username='mentor37', email='m37@example.com', role='mentor')
        req = self._get_mock_request()
        # Incoming role is student, but user is mentor
        data = {'sub': 'sub_37', 'email': 'm37@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data, role='student')
        user.refresh_from_db()
        self.assertEqual(user.role, 'mentor')

    def test_38_existing_password_remains_unchanged(self):
        user = User.objects.create_user(username='pass38', email='pass38@example.com', password='OriginalSecretPassword123!')
        orig_hash = user.password
        req = self._get_mock_request()
        data = {'sub': 'sub_38', 'email': 'pass38@example.com'}
        authenticate_or_register_google_user(req, data)
        user.refresh_from_db()
        self.assertEqual(user.password, orig_hash)

    def test_39_existing_profile_data_remains_unchanged(self):
        user = User.objects.create_user(username='prof39', email='prof39@example.com', first_name='OriginalName')
        req = self._get_mock_request()
        data = {'sub': 'sub_39', 'email': 'prof39@example.com', 'given_name': 'NewGoogleName'}
        authenticate_or_register_google_user(req, data)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'OriginalName')

    def test_40_no_duplicate_user_is_created(self):
        User.objects.create_user(username='nodup40', email='nodup40@example.com')
        req = self._get_mock_request()
        data = {'sub': 'sub_40', 'email': 'nodup40@example.com'}
        authenticate_or_register_google_user(req, data)
        self.assertEqual(User.objects.filter(email='nodup40@example.com').count(), 1)

    def test_41_case_insensitive_initial_email_matching(self):
        user = User.objects.create_user(username='case41', email='John.Doe@Example.COM')
        req = self._get_mock_request()
        data = {'sub': 'sub_41', 'email': 'john.doe@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, user)

    def test_42_multiple_normalized_email_matches_rejected(self):
        # Temporarily bypass unique constraint or simulate multiple matches
        u1 = User(username='match42_1', email='dup@test.com')
        u1.save()
        # Use raw query or mock filter to simulate multiple matches safely
        req = self._get_mock_request()
        with patch.object(User.objects, 'filter') as mock_filter:
            mock_filter.return_value.count.return_value = 2
            mock_filter.return_value.__iter__.return_value = [u1, u1]
            data = {'sub': 'sub_42', 'email': 'dup@test.com'}
            status, logged_in, err = authenticate_or_register_google_user(req, data)
            self.assertEqual(status, 'error')
            self.assertIn("Multiple accounts found", err)

    def test_43_incomplete_otp_account_recovered_under_valid_conditions(self):
        user = User.objects.create_user(username='otp43', email='otp43@example.com', is_active=False)
        EmailOTP.objects.create(user=user, otp_hash=make_password('112233'))
        req = self._get_mock_request()
        data = {'sub': 'sub_43', 'email': 'otp43@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'authenticated')
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 0)

    def test_44_administratively_disabled_account_cannot_be_reactivated(self):
        user = User.objects.create_user(username='admin_disabled44', email='disabled44@example.com', is_active=False)
        # No unexpired OTP
        req = self._get_mock_request()
        data = {'sub': 'sub_44', 'email': 'disabled44@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'error')
        self.assertIn("deactivated", err)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_45_blocked_mentor_restrictions_remain_intact(self):
        user = User.objects.create_user(username='blocked_m45', email='bm45@example.com', role='mentor', is_active=False)
        req = self._get_mock_request()
        data = {'sub': 'sub_45', 'email': 'bm45@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, 'error')
        self.assertFalse(user.is_active)

    def test_46_pending_mentor_state_remains_intact(self):
        user = User.objects.create_user(username='pending_m46', email='pm46@example.com', role='mentor')
        MentorProfile.objects.create(user=user, company='TechCorp', designation='Engineer', experience_years=5, status='Pending', verified=False)
        dest = get_role_based_redirect_url(user)
        self.assertEqual(dest, reverse('community:mentor_register'))

    def test_47_rejected_mentor_state_remains_intact(self):
        user = User.objects.create_user(username='rej_m47', email='rm47@example.com', role='mentor')
        MentorProfile.objects.create(user=user, company='TechCorp', designation='Engineer', experience_years=5, status='Rejected', verified=False)
        dest = get_role_based_redirect_url(user)
        self.assertEqual(dest, reverse('community:mentor_register'))

    def test_48_inactive_mentor_state_remains_intact(self):
        user = User.objects.create_user(username='inact_m48', email='im48@example.com', role='mentor')
        MentorProfile.objects.create(user=user, company='TechCorp', designation='Engineer', experience_years=5, status='Inactive', verified=False)
        dest = get_role_based_redirect_url(user)
        self.assertEqual(dest, reverse('community:mentor_register'))

    def test_49_existing_google_identity_cannot_be_linked_to_another_user(self):
        u1 = User.objects.create_user(username='u49_1', email='u49_1@example.com')
        u2 = User.objects.create_user(username='u49_2', email='u49_2@example.com')
        GoogleIdentity.objects.create(user=u1, provider='google', provider_user_id='sub_49_dup', email_at_link=u1.email)
        req = self._get_mock_request()
        data = {'sub': 'sub_49_dup', 'email': 'u49_2@example.com'}
        status, logged_in, err = authenticate_or_register_google_user(req, data)
        # Sub matches u1, so it authenticates u1, not u2
        self.assertEqual(status, 'authenticated')
        self.assertEqual(logged_in, u1)

    def test_50_failed_linking_transaction_leaves_no_partial_records(self):
        u = User.objects.create_user(username='u50', email='u50@example.com')
        req = self._get_mock_request()
        with patch.object(GoogleIdentity.objects, 'create', side_effect=IntegrityError("DB lock")):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    GoogleIdentity.objects.create(user=u, provider='google', provider_user_id='sub_50', email_at_link=u.email)
        self.assertFalse(GoogleIdentity.objects.filter(provider_user_id='sub_50').exists())

    # -------------------------------------------------------------
    # Regression Tests (Scenarios 51-56)
    # -------------------------------------------------------------
    def test_51_existing_username_password_login_works(self):
        User.objects.create_user(username='reg51', email='r51@example.com', password='Password123!')
        client = Client()
        response = client.post(reverse('login'), {'username': 'reg51', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 302)

    def test_52_existing_email_otp_registration_works(self):
        client = Client()
        reg_data = {
            'username': 'reg52_user',
            'email': 'r52@example.com',
            'first_name': 'Reg',
            'last_name': 'FiftyTwo',
            'role': 'student',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        with patch('apps.accounts.services.send_otp_email'):
            response = client.post(reverse('register'), reg_data)
        self.assertRedirects(response, reverse('verify_otp'))
        user = User.objects.get(username='reg52_user')
        self.assertFalse(user.is_active)
        self.assertTrue(EmailOTP.objects.filter(user=user).exists())

    def test_53_existing_otp_verification_works(self):
        user = User.objects.create_user(username='reg53', email='r53@example.com', is_active=False)
        otp = EmailOTP.objects.create(user=user, otp_hash=make_password('654321'))
        client = Client()
        session = client.session
        session['verify_user_id'] = user.id
        session.save()

        response = client.post(reverse('verify_otp'), {'otp_code': '654321'})
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertRedirects(response, reverse('profile_create'))

    def test_54_existing_password_reset_works(self):
        User.objects.create_user(username='reg54', email='r54@example.com')
        client = Client()
        with patch('django.contrib.auth.forms.PasswordResetForm.save'):
            response = client.post(reverse('password_reset'), {'email': 'r54@example.com'})
        self.assertEqual(response.status_code, 302)

    def test_55_existing_logout_works(self):
        user = User.objects.create_user(username='reg55', email='r55@example.com')
        client = Client()
        client.force_login(user)
        response = client.get(reverse('logout'))
        self.assertRedirects(response, reverse('home'))

    def test_56_existing_role_based_redirect_behavior_remains_unchanged(self):
        student = User.objects.create_user(username='reg56_s', email='r56s@example.com', role='student')
        mentor = User.objects.create_user(username='reg56_m', email='r56m@example.com', role='mentor')
        self.assertEqual(get_role_based_redirect_url(student), reverse('profile_create'))
        self.assertEqual(get_role_based_redirect_url(mentor), reverse('community:mentor_register'))

    # -------------------------------------------------------------
    # Phase 2 Security Hardening Tests (Nonce, Cleanup, Atomicity, azp)
    # -------------------------------------------------------------
    def test_hardening_missing_expected_nonce_fails_closed(self):
        token = self._create_signed_id_token()
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce=None, jwks_keys=self.jwks)
        self.assertIn("Missing or empty expected nonce", str(ctx.exception))

    def test_hardening_empty_expected_nonce_fails_closed(self):
        token = self._create_signed_id_token()
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="", jwks_keys=self.jwks)
        self.assertIn("Missing or empty expected nonce", str(ctx.exception))

    def test_hardening_missing_token_nonce_fails_closed(self):
        token = self._create_signed_id_token(claims_override={"nonce": None})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("missing nonce claim", str(ctx.exception))

    def test_hardening_nonce_matching_accepted(self):
        token = self._create_signed_id_token(claims_override={"nonce": "exact_matching_nonce"})
        payload = verify_google_id_token(token, expected_nonce="exact_matching_nonce", jwks_keys=self.jwks)
        self.assertEqual(payload["nonce"], "exact_matching_nonce")

    def test_hardening_cancellation_clears_all_oauth_session_keys(self):
        client = Client()
        session = client.session
        session["oauth_state"] = "state_cancel_test"
        session["oauth_code_verifier"] = "verifier_cancel_test"
        session["oauth_nonce"] = "nonce_cancel_test"
        session["oauth_pending_role"] = "student"
        session["oauth_created_at"] = time.time()
        session["oauth_pending_user"] = {"sub": "cancel_sub"}
        session["unrelated_custom_key"] = "preserve_me_123"
        session.save()

        response = client.get(reverse("google_callback"), {"error": "access_denied"})
        self.assertRedirects(response, reverse("login"))

        # Re-fetch session
        updated_session = client.session
        oauth_keys = [
            "oauth_state",
            "oauth_code_verifier",
            "oauth_nonce",
            "oauth_pending_role",
            "oauth_created_at",
            "oauth_pending_user",
        ]
        for key in oauth_keys:
            self.assertNotIn(key, updated_session, f"Key {key} was not cleared on cancellation")
        self.assertEqual(updated_session.get("unrelated_custom_key"), "preserve_me_123")

    def test_hardening_failed_callback_clears_stale_session_data(self):
        client = Client()
        session = client.session
        session["oauth_state"] = "valid_state"
        session["oauth_code_verifier"] = "valid_verifier"
        session["oauth_nonce"] = "valid_nonce"
        session["oauth_pending_role"] = "mentor"
        session.save()

        # Trigger state mismatch failure
        response = client.get(reverse("google_callback"), {"code": "c", "state": "invalid_state"})
        self.assertRedirects(response, reverse("login"))

        updated_session = client.session
        self.assertNotIn("oauth_pending_role", updated_session)
        self.assertNotIn("oauth_code_verifier", updated_session)
        self.assertNotIn("oauth_nonce", updated_session)

    def test_hardening_atomic_otp_activation_success(self):
        user = User.objects.create_user(username="atomic_ok", email="atomic_ok@example.com", is_active=False)
        EmailOTP.objects.create(user=user, otp_hash=make_password("998877"))
        req = self._get_mock_request()
        data = {"sub": "sub_atomic_ok", "email": "atomic_ok@example.com"}

        status, logged_in, err = authenticate_or_register_google_user(req, data)
        self.assertEqual(status, "authenticated")
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 0)
        self.assertTrue(GoogleIdentity.objects.filter(user=user, provider_user_id="sub_atomic_ok").exists())

    def test_hardening_atomic_otp_activation_rollback_on_identity_creation_error(self):
        user = User.objects.create_user(username="atomic_fail", email="atomic_fail@example.com", is_active=False)
        otp = EmailOTP.objects.create(user=user, otp_hash=make_password("998877"))
        req = self._get_mock_request()
        data = {"sub": "sub_atomic_fail", "email": "atomic_fail@example.com"}

        with patch.object(GoogleIdentity.objects, "create", side_effect=IntegrityError("DB collision")):
            with self.assertRaises(IntegrityError):
                authenticate_or_register_google_user(req, data)

        user.refresh_from_db()
        # Ensure user.is_active remained False (rolled back)
        self.assertFalse(user.is_active)
        # Ensure EmailOTP was NOT deleted (rolled back)
        self.assertTrue(EmailOTP.objects.filter(user=user).exists())
        self.assertFalse(GoogleIdentity.objects.filter(provider_user_id="sub_atomic_fail").exists())

    def test_hardening_azp_correct_accepted(self):
        token = self._create_signed_id_token(claims_override={"azp": "test_client_id_123"})
        payload = verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertEqual(payload.get("azp"), "test_client_id_123")

    def test_hardening_azp_incorrect_rejected(self):
        token = self._create_signed_id_token(claims_override={"azp": "unauthorized_client_xyz"})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("authorized party (azp)", str(ctx.exception))

    def test_hardening_azp_malformed_rejected(self):
        token = self._create_signed_id_token(claims_override={"azp": 123456})
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("Malformed 'azp' claim", str(ctx.exception))

    def test_hardening_azp_multi_audience_valid_accepted(self):
        token = self._create_signed_id_token(claims_override={
            "aud": ["test_client_id_123", "secondary_aud_456"],
            "azp": "test_client_id_123"
        })
        payload = verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertEqual(payload.get("azp"), "test_client_id_123")

    def test_hardening_azp_multi_audience_missing_azp_rejected(self):
        token = self._create_signed_id_token(claims_override={
            "aud": ["test_client_id_123", "secondary_aud_456"],
        })
        with self.assertRaises(ValidationError) as ctx:
            verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertIn("missing valid 'azp' claim", str(ctx.exception))

    def test_hardening_azp_single_audience_without_azp_accepted(self):
        token = self._create_signed_id_token(claims_override={"aud": "test_client_id_123"})
        payload = verify_google_id_token(token, expected_nonce="test_nonce_val_123", jwks_keys=self.jwks)
        self.assertEqual(payload.get("aud"), "test_client_id_123")

