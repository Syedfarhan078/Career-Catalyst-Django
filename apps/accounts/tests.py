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


