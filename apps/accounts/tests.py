from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import EmailOTP
from apps.accounts.services import (
    create_user_with_otp,
    verify_user_otp,
    resend_user_otp
)

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
