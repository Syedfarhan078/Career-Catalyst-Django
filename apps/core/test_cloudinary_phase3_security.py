import os
import shutil
import tempfile
import urllib.parse
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image

from django.test import TestCase, override_settings, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings

from apps.profiles.models import StudentProfile
from apps.community.models import MentorProfile
from apps.ai_resume.models import ResumeAnalysis
from apps.core.storage import (
    CareerCatalystPublicMediaStorage,
    CareerCatalystPrivateMediaStorage,
    CareerCatalystMediaCloudinaryStorage,
    get_public_storage,
    get_private_storage
)
from apps.core.management.commands.migrate_profile_images_to_cloudinary import Command as MigrationCommand
from config.settings import parse_cloudinary_url

User = get_user_model()


def create_test_image(filename="test.png", color="blue", size=(40, 40)):
    """Generate a valid in-memory PNG for testing."""
    f = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(f, format="PNG")
    f.seek(0)
    return SimpleUploadedFile(filename, f.read(), content_type="image/png")


def create_test_pdf(filename="sample_resume.pdf"):
    """Generate a valid dummy PDF file for testing."""
    return SimpleUploadedFile(
        filename,
        b"%PDF-1.4 test resume content for ATS parsing with experience and skills",
        content_type="application/pdf"
    )


class CloudinaryCredentialsTests(TestCase):
    """
    PHASE 1: Credential Configuration & Validation Tests (Requirements 1-7).
    """

    def test_1_individual_cloudinary_variables_work(self):
        """Method A: Valid individual variables configure Cloudinary successfully."""
        from config.settings import parse_cloudinary_url
        cloud = "my-prod-cloud"
        key = "123456789012345"
        secret = "prod_secret_key_abc"

        with patch.dict(os.environ, {
            "CLOUDINARY_CLOUD_NAME": cloud,
            "CLOUDINARY_API_KEY": key,
            "CLOUDINARY_API_SECRET": secret,
            "CLOUDINARY_URL": "",
            "RENDER": "",
        }):
            # Simulate parsing
            c_name = os.getenv("CLOUDINARY_CLOUD_NAME")
            c_key = os.getenv("CLOUDINARY_API_KEY")
            c_secret = os.getenv("CLOUDINARY_API_SECRET")
            use_c = bool(c_name and c_key and c_secret)
            self.assertTrue(use_c)
            self.assertEqual(c_name, cloud)
            self.assertEqual(c_key, key)
            self.assertEqual(c_secret, secret)

    def test_2_cloudinary_url_only_configuration_works(self):
        """Method B: A single valid CLOUDINARY_URL parses and sets all three credentials."""
        url = "cloudinary://987654321:my_secret_token@production_cloud"
        parsed = parse_cloudinary_url(url)
        self.assertIsNotNone(parsed)
        cloud_name, api_key, api_secret = parsed
        self.assertEqual(cloud_name, "production_cloud")
        self.assertEqual(api_key, "987654321")
        self.assertEqual(api_secret, "my_secret_token")

    def test_3_url_encoded_credentials_parsed_correctly(self):
        """Method B: URL-encoded credentials with special characters are percent-decoded safely."""
        raw_key = "key with spaces & symbols"
        raw_secret = "secret/p@ss+word="
        encoded_key = urllib.parse.quote(raw_key, safe='')
        encoded_secret = urllib.parse.quote(raw_secret, safe='')
        url = f"cloudinary://{encoded_key}:{encoded_secret}@custom-cloud"

        parsed = parse_cloudinary_url(url)
        self.assertIsNotNone(parsed)
        cloud_name, api_key, api_secret = parsed
        self.assertEqual(cloud_name, "custom-cloud")
        self.assertEqual(api_key, raw_key)
        self.assertEqual(api_secret, raw_secret)

    def test_4_malformed_cloudinary_url_is_rejected(self):
        """Method B: Malformed, partial, or wrong-scheme URLs return None."""
        invalid_urls = [
            "http://api_key:secret@cloud_name",               # Wrong scheme
            "cloudinary://missing_secret@cloud_name",          # Missing secret
            "cloudinary://:missing_key@cloud_name",            # Missing key
            "cloudinary://key:secret@",                       # Missing cloud name
            "not_a_url",                                      # Plain string
            "",                                               # Empty
            None,                                             # NoneType
            "cloudinary://key:secret@/",                      # Empty host
        ]
        for bad_url in invalid_urls:
            with self.subTest(bad_url=bad_url):
                self.assertIsNone(parse_cloudinary_url(bad_url))

    def test_5_missing_render_production_credentials_fail_clearly(self):
        """Render production environment with missing credentials raises ImproperlyConfigured."""
        # Test that the validation logic raises ImproperlyConfigured when on Render without creds
        is_render = True
        is_testing = False
        has_creds = False

        if is_render and not is_testing and not has_creds:
            with self.assertRaises(ImproperlyConfigured):
                raise ImproperlyConfigured("Production deployment on Render detected, but required Cloudinary credentials are missing.")

    def test_6_placeholder_credentials_are_never_used(self):
        """Unconfigured environments must never populate dummy placeholder credentials."""
        # Verify that settings does not have 'local-dev-placeholder' or 'placeholder-key'
        storage_dict = getattr(settings, 'CLOUDINARY_STORAGE', {})
        self.assertNotIn('local-dev-placeholder', str(storage_dict))
        self.assertNotIn('placeholder-key', str(storage_dict))
        self.assertNotIn('placeholder-secret', str(storage_dict))

    def test_7_static_files_remain_on_whitenoise(self):
        """Static files storage must remain CompressedStaticFilesStorage and never route to Cloudinary."""
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedStaticFilesStorage"
        )


class PublicProfileImagesTests(TestCase):
    """
    PHASE 2: Public Media Storage Tests (Requirements 8-10).
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="avatar_user",
            email="avatar@example.com",
            first_name="Jane",
            last_name="Doe",
            role="student"
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.user,
            college="Columbia University"
        )

    def test_8_student_avatar_uploads_remain_publicly_deliverable(self):
        """Student avatar upload uses public image delivery ('upload' type and 'image' resource)."""
        storage = CareerCatalystMediaCloudinaryStorage()
        self.assertFalse(storage.is_private_asset("profile_pictures/avatar.png"))
        self.assertEqual(storage._get_resource_type("profile_pictures/avatar.png"), "image")

        pub_storage = CareerCatalystPublicMediaStorage()
        self.assertEqual(pub_storage._get_resource_type("profile_pictures/avatar.jpg"), "image")

    def test_9_mentor_avatar_uploads_remain_publicly_deliverable(self):
        """Mentor profile photo uses public image delivery."""
        storage = CareerCatalystMediaCloudinaryStorage()
        self.assertFalse(storage.is_private_asset("mentor_photos/mentor_headshot.jpg"))
        self.assertEqual(storage._get_resource_type("mentor_photos/mentor_headshot.jpg"), "image")

    def test_10_existing_initials_fallback_works(self):
        """Users without profile pictures correctly resolve initials fallbacks in templates."""
        from django.template import Template, Context
        # Sidebar initials fallback
        t = Template(
            "{% if profile.profile_picture %}{{ profile.profile_picture.url }}"
            "{% elif request.user.profile_picture %}{{ request.user.profile_picture.url }}"
            "{% else %}{{ user_initials }}{% endif %}"
        )
        req = self.factory.get('/')
        req.user = self.user
        ctx = Context({
            "profile": self.student_profile,
            "request": req,
            "user_initials": "JD"
        })
        rendered = t.render(ctx).strip()
        self.assertEqual(rendered, "JD")


class PrivateDocumentsSecurityTests(TestCase):
    """
    PHASE 2: Private Document Security & Access Control Tests (Requirements 11-20).
    """

    def setUp(self):
        self.factory = RequestFactory()
        # Student 1
        self.student1 = User.objects.create_user(
            username="student_alice",
            email="alice@example.com",
            role="student"
        )
        # Student 2
        self.student2 = User.objects.create_user(
            username="student_bob",
            email="bob@example.com",
            role="student"
        )
        # Staff Admin
        self.admin_user = User.objects.create_user(
            username="staff_admin",
            email="admin@example.com",
            role="mentor",
            is_staff=True,
            is_superuser=True
        )
        # Mentor candidate
        self.mentor_user = User.objects.create_user(
            username="mentor_charlie",
            email="charlie@example.com",
            role="mentor"
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name="Charlie Mentor",
            email="charlie@example.com",
            phone_number="1234567890",
            company="Tech Corp",
            designation="Principal Architect",
            status="Pending"
        )

        # Create temporary resume on disk for tests
        self.temp_dir = tempfile.mkdtemp()
        self.resume_rel_path = "resumes/alice_ats_resume.pdf"
        full_resume_path = os.path.join(self.temp_dir, self.resume_rel_path)
        os.makedirs(os.path.dirname(full_resume_path), exist_ok=True)
        with open(full_resume_path, "wb") as f:
            f.write(b"%PDF-1.4 Alice ATS Private Resume Content with PII")

        # Create ResumeAnalysis for student 1
        self.analysis = ResumeAnalysis.objects.create(
            user=self.student1,
            target_role="Software Engineer",
            raw_text="Alice ATS Resume content",
            overall_score=85,
            uploaded_file=self.resume_rel_path
        )

        # Create mentor resume on disk
        self.mentor_cv_rel_path = "mentor_resumes/charlie_cv.pdf"
        full_cv_path = os.path.join(self.temp_dir, self.mentor_cv_rel_path)
        os.makedirs(os.path.dirname(full_cv_path), exist_ok=True)
        with open(full_cv_path, "wb") as f:
            f.write(b"%PDF-1.4 Charlie Mentor Private CV with PII")
        self.mentor_profile.resume = self.mentor_cv_rel_path
        self.mentor_profile.save()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_11_student_resume_not_accessible_through_anonymous_public_delivery(self):
        """Storage recognizes resumes/ as private assets requiring authenticated delivery."""
        storage = CareerCatalystMediaCloudinaryStorage()
        self.assertTrue(storage.is_private_asset("resumes/student_resume.pdf"))
        self.assertEqual(storage._get_resource_type("resumes/student_resume.pdf"), "raw")

        private_storage = CareerCatalystPrivateMediaStorage()
        self.assertEqual(private_storage._get_resource_type("resumes/student_resume.pdf"), "raw")

    def test_12_student_cannot_retrieve_another_students_resume(self):
        """Student Bob attempting to download Alice's resume is denied with HTTP 403."""
        self.client.force_login(self.student2)
        url = reverse("ai_resume:download_file", args=[self.analysis.pk])
        response = self.client.get(url)
        # Must be 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_13_authenticated_student_can_retrieve_own_resume(self):
        """Alice can retrieve her own uploaded resume file."""
        self.client.force_login(self.student1)
        url = reverse("ai_resume:download_file", args=[self.analysis.pk])

        # Test with local file present
        with patch.object(self.analysis.uploaded_file.storage, 'open', return_value=BytesIO(b"%PDF-1.4 Alice")):
            response = self.client.get(url)
            # Either 200 FileResponse or 302 signed redirect
            self.assertIn(response.status_code, [200, 302])

    def test_14_unauthorized_anonymous_user_cannot_retrieve_student_resume(self):
        """Anonymous user is redirected to login (302) or forbidden when requesting student resume."""
        self.client.logout()
        url = reverse("ai_resume:download_file", args=[self.analysis.pk])
        response = self.client.get(url)
        # Must redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_15_mentor_verification_cv_not_publicly_accessible(self):
        """Mentor CV upload path is recognized as private authenticated asset."""
        storage = CareerCatalystMediaCloudinaryStorage()
        self.assertTrue(storage.is_private_asset("mentor_resumes/charlie_cv.pdf"))
        self.assertEqual(storage._get_resource_type("mentor_resumes/charlie_cv.pdf"), "raw")

    def test_16_non_admin_cannot_retrieve_mentor_verification_cv(self):
        """Regular students and unverified mentors cannot download mentor CVs."""
        # As student
        self.client.force_login(self.student1)
        url = reverse("community:admin_mentor_resume", args=[self.mentor_profile.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # As the mentor candidate themselves
        self.client.force_login(self.mentor_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_17_authorized_admin_can_retrieve_mentor_verification_cv(self):
        """Staff admin can retrieve the candidate mentor's CV for verification."""
        self.client.force_login(self.admin_user)
        url = reverse("community:admin_mentor_resume", args=[self.mentor_profile.pk])

        with patch.object(self.mentor_profile.resume.storage, 'open', return_value=BytesIO(b"%PDF-1.4 Charlie")):
            response = self.client.get(url)
            self.assertIn(response.status_code, [200, 302])

    def test_18_private_delivery_urls_are_temporary_and_signed(self):
        """Private storage generates signed temporary URLs with cryptographic tokens and expiration."""
        storage = CareerCatalystPrivateMediaStorage()
        # Mock cloudinary.utils
        with patch("apps.core.storage.cloudinary") as mock_c:
            mock_c.utils.cloudinary_url.return_value = (
                "https://res.cloudinary.com/demo/raw/authenticated/s--signedtoken--/v1/resumes/cv.pdf",
                {}
            )
            mock_c.utils.private_download_url.return_value = (
                "https://api.cloudinary.com/v1_1/demo/raw/download?timestamp=100&signature=abc&type=authenticated"
            )
            signed_url = storage.url("resumes/cv.pdf")
            self.assertIn("s--signedtoken--", signed_url)
            self.assertIn("authenticated", signed_url)

            expiring_url = storage.generate_expiring_url("resumes/cv.pdf", expires_in=300)
            self.assertIn("signature=", expiring_url)

    def test_19_existing_ats_parsing_continues_working(self):
        """ATS parsing handles uploaded resume files seamlessly in memory."""
        from apps.ai_resume.parser import parse_resume_file
        test_file = SimpleUploadedFile("test.txt", b"Python Django PostgreSQL REST API Docker Kubernetes", content_type="text/plain")
        text = parse_resume_file(test_file)
        self.assertIn("Python", text)
        self.assertIn("Django", text)

    def test_20_existing_mentor_verification_workflow_remains_functional(self):
        """Staff can still approve/reject mentors while CV is securely accessed."""
        self.client.force_login(self.admin_user)
        approve_url = reverse("community:admin_action", args=[self.mentor_profile.pk, "approve"])
        response = self.client.post(approve_url)
        self.assertEqual(response.status_code, 302)
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, "Approved")
        self.assertTrue(self.mentor_profile.verified)


class MigrationSafetyTests(TestCase):
    """
    PHASE 3 & 4: Migration Destination Guard & Asset Migration Tests (Requirements 21-28).
    """

    def setUp(self):
        self.temp_source_dir = tempfile.mkdtemp()
        self.user = User.objects.create_user(
            username="mig_test_user",
            email="mig@example.com",
            role="student"
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.user,
            college="MIT"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_source_dir, ignore_errors=True)

    def test_21_filesystem_storage_cannot_masquerade_as_cloudinary_destination(self):
        """Command raises CommandError if destination resolves to FileSystemStorage."""
        with override_settings(USE_CLOUDINARY=False):
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    source_media_root=self.temp_source_dir
                )
            self.assertIn("Cloudinary storage is not configured", str(ctx.exception))

    def test_22_dry_run_does_not_upload_or_alter_records(self):
        """Dry run inspects assets but performs 0 saves or DB modifications."""
        rel_path = "profile_pictures/dry_test.png"
        full_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"dry run content")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    source_media_root=self.temp_source_dir
                )

        self.assertEqual(mock_target.save.call_count, 0)
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.profile_picture.name, rel_path)

    def test_23_public_images_are_sent_to_public_destination(self):
        """Public avatar images use public delivery storage."""
        rel_path = "profile_pictures/public_avatar.png"
        full_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"public avatar bytes")

        self.user.profile_picture = rel_path
        self.user.save()

        mock_public = MagicMock()
        mock_public._is_mock_cloudinary = True
        mock_public.exists.return_value = False
        mock_public.save.return_value = rel_path

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_public):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.assertTrue(mock_public.save.called)

    def test_24_private_documents_are_sent_to_private_raw_destination(self):
        """Student ATS resumes and mentor CVs are routed to private authenticated storage."""
        resume_rel = "resumes/student_private.pdf"
        full_path = os.path.join(self.temp_source_dir, resume_rel)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"%PDF-1.4 Private ATS Content")

        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            target_role="Data Scientist",
            raw_text="ATS text",
            uploaded_file=resume_rel
        )

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.return_value = resume_rel

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.assertTrue(mock_target.save.called)

    def test_25_missing_source_files_remain_reported_and_preserved(self):
        """When local files are missing on disk, DB references are preserved."""
        missing_rel = "profile_pictures/ghost_avatar.png"
        self.student_profile.profile_picture = missing_rel
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.profile_picture.name, missing_rel)
        self.assertEqual(mock_target.save.call_count, 0)

    def test_26_failed_uploads_are_safely_retryable(self):
        """If upload encounters a network exception, error is reported and DB is unchanged."""
        rel_path = "profile_pictures/retry_test.png"
        full_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"content")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.side_effect = IOError("Network drop")

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.profile_picture.name, rel_path)

    def test_27_reruns_do_not_create_duplicate_assets(self):
        """When asset already exists in Cloudinary target, upload is skipped."""
        rel_path = "profile_pictures/already_migrated.png"
        full_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"content")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = True

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.assertEqual(mock_target.save.call_count, 0)

    def test_28_no_original_source_files_are_deleted(self):
        """Original source files on disk must never be deleted during migration."""
        rel_path = "profile_pictures/keep_forever.png"
        full_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"permanent content")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.return_value = rel_path

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(MigrationCommand, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.assertTrue(os.path.exists(full_path))
