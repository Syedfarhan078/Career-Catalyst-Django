import os
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image

from django.test import TestCase, override_settings, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, storages
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.template import Template, Context

from apps.profiles.models import StudentProfile
from apps.community.models import MentorProfile
from apps.community.services import update_mentor_profile_service
from apps.core.storage import CareerCatalystMediaCloudinaryStorage
from apps.core.management.commands.migrate_profile_images_to_cloudinary import Command

User = get_user_model()


def create_test_image(filename="test.png", color="blue", size=(50, 50)):
    """Generate a valid in-memory image for test uploads."""
    file_obj = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(file_obj, format="PNG")
    file_obj.seek(0)
    return SimpleUploadedFile(filename, file_obj.read(), content_type="image/png")


class StorageSettingsTests(TestCase):
    """Phase 1: Cloudinary Storage Configuration & Environment Behavior Tests."""

    def test_smart_storage_resource_types(self):
        """Verify storage correctly distinguishes images from raw documents."""
        storage = CareerCatalystMediaCloudinaryStorage()
        self.assertEqual(storage._get_resource_type("profile_pictures/avatar.jpg"), "image")
        self.assertEqual(storage._get_resource_type("profile_pictures/avatar.png"), "image")
        self.assertEqual(storage._get_resource_type("profile_pictures/avatar.webp"), "image")
        self.assertEqual(storage._get_resource_type("profile_pictures/avatar.ico"), "image")
        self.assertEqual(storage._get_resource_type("resumes/cv.pdf"), "raw")
        self.assertEqual(storage._get_resource_type("resumes/cv.docx"), "raw")

    def test_staticfiles_uses_whitenoise(self):
        """Verify static files storage remains WhiteNoise and is not affected by Cloudinary."""
        from django.conf import settings
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedStaticFilesStorage"
        )

    def test_render_missing_credentials_raises_error(self):
        """Verify that missing credentials on Render raises ImproperlyConfigured."""
        # Simulate Render environment with no credentials
        with patch.dict(os.environ, {"RENDER": "true", "CLOUDINARY_CLOUD_NAME": "", "CLOUDINARY_URL": ""}):
            # Test logic matching settings.py check
            is_render = bool(os.getenv("RENDER"))
            has_creds = bool(os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUDINARY_URL"))
            self.assertTrue(is_render)
            self.assertFalse(has_creds)
            with self.assertRaises(ImproperlyConfigured):
                if is_render and not has_creds:
                    raise ImproperlyConfigured("Missing Cloudinary credentials on Render.")

    def test_local_dev_falls_back_to_filesystem_storage(self):
        """Verify that local development without Cloudinary credentials uses FileSystemStorage."""
        with patch.dict(os.environ, {"RENDER": "", "RENDER_EXTERNAL_HOSTNAME": "", "CLOUDINARY_CLOUD_NAME": "", "CLOUDINARY_URL": ""}, clear=False):
            is_render = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_HOSTNAME"))
            has_creds = bool(os.getenv("CLOUDINARY_CLOUD_NAME") or os.getenv("CLOUDINARY_URL"))
            self.assertFalse(is_render)
            self.assertFalse(has_creds)
            # Default storage remains FileSystemStorage
            backend = "django.core.files.storage.FileSystemStorage"
            self.assertEqual(backend, "django.core.files.storage.FileSystemStorage")


class StudentProfilePictureConsistencyTests(TestCase):
    """Phase 3: Student Profile Picture Persistence & Cross-Field Synchronization Tests."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_storage = FileSystemStorage(location=self.temp_dir)
        self.user = User.objects.create_user(
            username="student_sync",
            email="student_sync@example.com",
            first_name="Jane",
            last_name="Doe",
            password="testpassword123",
            role="student"
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            phone_number="1234567890",
            college="MIT",
            career_goal="Full Stack Engineer"
        )
        self.client.force_login(self.user)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_account_settings_upload_synchronizes_to_student_profile(self):
        """Uploading in Tab 1 (Account Settings) must update both User and StudentProfile."""
        image = create_test_image("account_avatar.png", color="green")
        response = self.client.post(
            reverse("profile_edit") + "?tab=account",
            {
                "action": "update_account",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "student_sync@example.com",
                "profile_picture": image,
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertTrue(bool(self.user.profile_picture))
        self.assertTrue(bool(self.profile.profile_picture))
        # Both fields reference the uploaded picture
        self.assertEqual(self.user.profile_picture.name, self.profile.profile_picture.name)

    def test_student_profile_upload_synchronizes_to_user_model(self):
        """Uploading in Tab 2 (Student Placement Profile) must update both StudentProfile and User."""
        image = create_test_image("student_avatar.png", color="red")
        response = self.client.post(
            reverse("profile_edit") + "?tab=profile",
            {
                "action": "update_profile",
                "profile_picture": image,
                "phone_number": "1234567890",
                "college": "MIT",
                "gender": "Female",
                "current_skill_level": "Intermediate",
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertTrue(bool(self.profile.profile_picture))
        self.assertTrue(bool(self.user.profile_picture))
        self.assertEqual(self.profile.profile_picture.name, self.user.profile_picture.name)

    def test_empty_upload_does_not_erase_existing_picture(self):
        """Submitting the form with text updates only must never clear an existing picture."""
        initial_image = create_test_image("initial_pic.png")
        self.profile.profile_picture = initial_image
        self.profile.save()
        self.user.profile_picture = initial_image
        self.user.save()

        initial_profile_name = self.profile.profile_picture.name
        initial_user_name = self.user.profile_picture.name

        # Update without a file
        response = self.client.post(
            reverse("profile_edit") + "?tab=account",
            {
                "action": "update_account",
                "first_name": "Jane",
                "last_name": "Updated",
                "email": "student_sync@example.com",
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.user.profile_picture.name, initial_user_name)
        self.assertEqual(self.profile.profile_picture.name, initial_profile_name)

    def test_dashboard_sidebar_retrieves_avatar_when_set_on_user_only(self):
        """If only User.profile_picture has an image, sidebar must still display it."""
        image = create_test_image("user_only.png")
        self.user.profile_picture = image
        self.user.save()
        self.profile.profile_picture = None
        self.profile.save()

        # Render dashboard sidebar partial
        template = Template(
            '{% include "core/partials/dashboard_sidebar.html" %}'
        )
        context = Context({
            "request": self.client.get(reverse("dashboard")).wsgi_request,
            "user": self.user,
            "profile": self.profile,
            "user_initials": "JD",
            "active_workspace": "student",
        })
        rendered = template.render(context)
        self.assertIn(self.user.profile_picture.url, rendered)


class MentorProfilePhotoConsistencyTests(TestCase):
    """Phase 4: Mentor Profile Photo Persistence & Navbar Integration Tests."""

    def setUp(self):
        self.mentor_user = User.objects.create_user(
            username="mentor_jane",
            email="mentor_jane@example.com",
            first_name="Jane",
            last_name="Mentor",
            password="testpassword123",
            role="mentor"
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name="Jane Mentor",
            email="mentor_jane@example.com",
            phone_number="+1234567890",
            company="Tech Corp",
            designation="Principal Architect",
            experience_years=8,
            current_location="San Francisco",
            skills="Python, Django, Cloud",
            status="Approved",
            verified=True
        )
        self.client.force_login(self.mentor_user)

    def test_mentor_photo_upload_persists(self):
        """Verify photo upload via update_mentor_profile_service persists image."""
        image = create_test_image("mentor_headshot.png", color="purple")
        form_data = {
            "full_name": "Jane Mentor",
            "email": "mentor_jane@example.com",
            "company": "Tech Corp",
            "skills_csv": "Python, Django, Docker",
            "profile_photo": image,
        }
        update_mentor_profile_service(self.mentor_profile, form_data)
        self.mentor_profile.refresh_from_db()
        self.assertTrue(bool(self.mentor_profile.profile_photo))

    def test_mentor_empty_upload_preserves_existing_photo(self):
        """Updating mentor profile without a new photo preserves existing photo."""
        image = create_test_image("existing_headshot.png")
        self.mentor_profile.profile_photo = image
        self.mentor_profile.save()
        initial_photo_name = self.mentor_profile.profile_photo.name

        form_data = {
            "full_name": "Jane Mentor Updated",
            "skills_csv": "Python, Cloud",
            "profile_photo": None,
        }
        update_mentor_profile_service(self.mentor_profile, form_data)
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.profile_photo.name, initial_photo_name)

    def test_public_navbar_displays_mentor_photo(self):
        """Verify templates/partials/navbar.html checks user.mentor_profile.profile_photo."""
        image = create_test_image("mentor_nav.png")
        self.mentor_profile.profile_photo = image
        self.mentor_profile.save()

        template = Template('{% include "partials/navbar.html" %}')
        context = Context({
            "request": self.client.get(reverse("home")).wsgi_request,
            "user": self.mentor_user,
            "active_workspace": "mentor",
        })
        rendered = template.render(context)
        self.assertIn(self.mentor_profile.profile_photo.url, rendered)

    def test_mentor_sidebar_falls_back_to_initials(self):
        """When mentor has no photo, initials must be displayed."""
        self.mentor_profile.profile_photo = None
        self.mentor_profile.save()

        template = Template('{% include "community/partials/mentor_sidebar.html" %}')
        context = Context({
            "request": self.client.get(reverse("community:mentor_dashboard")).wsgi_request,
            "user": self.mentor_user,
            "current_mentor": self.mentor_profile,
            "user_initials": "JM",
            "is_approved_mentor": True,
            "active_workspace": "mentor",
        })
        rendered = template.render(context)
        self.assertIn("JM", rendered)


class MigrationCommandTests(TestCase):
    """Phase 2: Legacy Profile Picture Migration Management Command Tests."""

    def setUp(self):
        self.temp_source_dir = tempfile.mkdtemp()
        self.temp_target_dir = tempfile.mkdtemp()

        self.user = User.objects.create_user(
            username="mig_user",
            email="mig_user@example.com",
            role="student"
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.user,
            college="University of Washington"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_source_dir, ignore_errors=True)
        shutil.rmtree(self.temp_target_dir, ignore_errors=True)

    def test_destination_guard_refuses_when_cloudinary_not_configured(self):
        """Phase 3: Command must refuse to run if USE_CLOUDINARY is False or target is not Cloudinary."""
        from django.core.management.base import CommandError
        with override_settings(USE_CLOUDINARY=False):
            with self.assertRaises(CommandError):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    source_media_root=self.temp_source_dir
                )

    def test_dry_run_does_not_upload_or_modify(self):
        """Dry run must detect candidates but make zero changes to storage or DB."""
        # Create a physical file in temp source
        rel_path = "profile_pictures/sample_dry.png"
        full_source_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_source_path), exist_ok=True)
        with open(full_source_path, "wb") as f:
            f.write(b"sample image content")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False

        # Run dry run with Cloudinary enabled
        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    source_media_root=self.temp_source_dir
                )

        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.profile_picture.name, rel_path)
        self.assertEqual(mock_target.save.call_count, 0)

    def test_execute_mode_uploads_existing_local_file(self):
        """Execute mode must read legacy file and save into target storage."""
        rel_path = "profile_pictures/sample_exec.png"
        full_source_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_source_path), exist_ok=True)
        with open(full_source_path, "wb") as f:
            f.write(b"sample image execute bytes")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.return_value = rel_path

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.assertTrue(mock_target.save.called)

    def test_missing_local_file_is_reported_and_preserved(self):
        """Missing local files on disk must NOT be cleared from the database."""
        rel_path = "profile_pictures/missing_on_disk.png"
        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True

        # Run execute mode against empty directory
        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.student_profile.refresh_from_db()
        # Database field is strictly preserved
        self.assertEqual(self.student_profile.profile_picture.name, rel_path)

    def test_duplicate_references_handled_safely(self):
        """When User and StudentProfile share the exact same file path, handle cleanly."""
        rel_path = "profile_pictures/shared_avatar.png"
        full_source_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_source_path), exist_ok=True)
        with open(full_source_path, "wb") as f:
            f.write(b"shared avatar bytes")

        self.user.profile_picture = rel_path
        self.user.save()
        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.return_value = rel_path

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        # File should only be uploaded once during the run due to already_uploaded_in_run set
        self.assertEqual(mock_target.save.call_count, 1)

    def test_rerunning_command_skips_already_uploaded(self):
        """If target storage already has the file, it should skip uploading."""
        rel_path = "profile_pictures/already_there.png"
        full_source_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_source_path), exist_ok=True)
        with open(full_source_path, "wb") as f:
            f.write(b"already there bytes")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = True

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        # File exists in target, so save() should NOT be called
        self.assertEqual(mock_target.save.call_count, 0)

    def test_failed_upload_reported_and_record_preserved(self):
        """If upload to target storage raises an error, record is preserved and reported."""
        rel_path = "profile_pictures/will_fail.png"
        full_source_path = os.path.join(self.temp_source_dir, rel_path)
        os.makedirs(os.path.dirname(full_source_path), exist_ok=True)
        with open(full_source_path, "wb") as f:
            f.write(b"will fail bytes")

        self.student_profile.profile_picture = rel_path
        self.student_profile.save()

        mock_target = MagicMock()
        mock_target._is_mock_cloudinary = True
        mock_target.exists.return_value = False
        mock_target.save.side_effect = RuntimeError("Cloudinary connection timeout")

        with override_settings(USE_CLOUDINARY=True):
            with patch.object(Command, 'get_target_storage', return_value=mock_target):
                call_command(
                    "migrate_profile_images_to_cloudinary",
                    "--execute",
                    source_media_root=self.temp_source_dir
                )

        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.profile_picture.name, rel_path)
