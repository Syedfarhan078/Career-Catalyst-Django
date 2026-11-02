import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import FileSystemStorage, storages
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.profiles.models import StudentProfile
from apps.community.models import MentorProfile
from apps.ai_resume.models import ResumeAnalysis

try:
    from cloudinary_storage.storage import MediaCloudinaryStorage
except (ImportError, Exception):
    MediaCloudinaryStorage = None

from apps.core.storage import (
    CareerCatalystPublicMediaStorage,
    CareerCatalystPrivateMediaStorage,
    CareerCatalystMediaCloudinaryStorage,
    get_public_storage,
    get_private_storage
)


class Command(BaseCommand):
    help = (
        "Idempotently migrates existing locally stored media (public avatars and private resumes) "
        "from legacy local FileSystemStorage to Cloudinary persistent storage with strict access controls."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            default=False,
            help="Actually perform uploads to Cloudinary. Defaults to dry-run mode."
        )
        parser.add_argument(
            '--source-media-root',
            type=str,
            default=str(settings.MEDIA_ROOT),
            help="Path to legacy local media directory (defaults to settings.MEDIA_ROOT)."
        )

    def get_target_storage(self):
        """Resolves default target storage."""
        return storages['default']

    def get_public_target_storage(self):
        """Resolves dedicated public target storage."""
        target = self.get_target_storage()
        if getattr(target, '_is_mock_cloudinary', False):
            return target
        if getattr(settings, 'USE_CLOUDINARY', False):
            return CareerCatalystPublicMediaStorage()
        return target

    def get_private_target_storage(self):
        """Resolves dedicated private target storage."""
        target = self.get_target_storage()
        if getattr(target, '_is_mock_cloudinary', False):
            return target
        if getattr(settings, 'USE_CLOUDINARY', False):
            return CareerCatalystPrivateMediaStorage()
        return target

    def handle(self, *args, **options):
        execute_mode = options['execute']
        source_media_root = Path(options['source_media_root']).resolve()

        self.stdout.write(self.style.MIGRATE_HEADING("=== CareerCatalyst: Media Migration to Cloudinary ==="))

        # --- PHASE 3 DESTINATION GUARD ---
        if not getattr(settings, 'USE_CLOUDINARY', False):
            self.stderr.write(
                self.style.ERROR(
                    "MIGRATION REFUSED: Cloudinary persistent storage is not configured (settings.USE_CLOUDINARY is False).\n"
                    "The destination MUST be Cloudinary persistent storage. Local FileSystemStorage cannot masquerade as the target.\n"
                    "Please configure CLOUDINARY_URL or CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET."
                )
            )
            raise CommandError("Cloudinary storage is not configured (settings.USE_CLOUDINARY is False). Refusing to run.")

        target_storage = self.get_target_storage()
        is_mock = getattr(target_storage, '_is_mock_cloudinary', False)
        is_real_cloudinary = (
            (MediaCloudinaryStorage is not None and isinstance(target_storage, MediaCloudinaryStorage))
            or isinstance(target_storage, (
                CareerCatalystMediaCloudinaryStorage,
                CareerCatalystPublicMediaStorage,
                CareerCatalystPrivateMediaStorage
            ))
        )
        if isinstance(target_storage, FileSystemStorage) and not is_mock and not hasattr(target_storage, 'is_private_asset'):
            is_real_cloudinary = False

        if not (is_real_cloudinary or is_mock):
            self.stderr.write(
                self.style.ERROR(
                    f"MIGRATION REFUSED: Resolved target storage '{target_storage.__class__.__name__}' is not "
                    f"an instance of MediaCloudinaryStorage. Local FileSystemStorage cannot be used as destination."
                )
            )
            raise CommandError(f"Target storage is not MediaCloudinaryStorage (got {target_storage.__class__.__name__}).")

        public_storage = self.get_public_target_storage()
        private_storage = self.get_private_target_storage()

        if execute_mode:
            self.stdout.write(self.style.WARNING("Mode: EXECUTE (Files will be uploaded to persistent Cloudinary storage)"))
        else:
            self.stdout.write(self.style.SUCCESS("Mode: DRY-RUN (Safe inspection only; no files or records will be modified)"))

        legacy_fs = FileSystemStorage(location=str(source_media_root))

        self.stdout.write(f"Source storage:       {legacy_fs.__class__.__name__} ({source_media_root})")
        self.stdout.write(f"Destination storage:  {target_storage.__class__.__name__} (Cloudinary persistent storage)")
        cloud_name = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', '')
        self.stdout.write(f"Destination cloud:    {cloud_name or 'Configured'}")
        self.stdout.write(f"Public target:        {public_storage.__class__.__name__} (type='upload')")
        self.stdout.write(f"Private target:       {private_storage.__class__.__name__} (type='authenticated')")

        if not source_media_root.exists():
            self.stdout.write(self.style.WARNING(f"Warning: Source directory '{source_media_root}' does not exist on disk."))

        User = get_user_model()
        references = []

        # 1. User.profile_picture (Public)
        for user in User.objects.exclude(profile_picture='').exclude(profile_picture=None):
            if user.profile_picture and user.profile_picture.name:
                references.append({
                    'model_name': 'User',
                    'record_id': user.pk,
                    'identifier': user.username,
                    'field_name': 'profile_picture',
                    'instance': user,
                    'file_field': user.profile_picture,
                    'raw_path': str(user.profile_picture.name).replace('\\', '/'),
                    'is_private': False,
                })

        # 2. StudentProfile.profile_picture (Public)
        for sp in StudentProfile.objects.exclude(profile_picture='').exclude(profile_picture=None):
            if sp.profile_picture and sp.profile_picture.name:
                references.append({
                    'model_name': 'StudentProfile',
                    'record_id': sp.pk,
                    'identifier': getattr(sp.user, 'username', f"ID-{sp.pk}"),
                    'field_name': 'profile_picture',
                    'instance': sp,
                    'file_field': sp.profile_picture,
                    'raw_path': str(sp.profile_picture.name).replace('\\', '/'),
                    'is_private': False,
                })

        # 3. MentorProfile.profile_photo (Public)
        for mp in MentorProfile.objects.exclude(profile_photo='').exclude(profile_photo=None):
            if mp.profile_photo and mp.profile_photo.name:
                references.append({
                    'model_name': 'MentorProfile',
                    'record_id': mp.pk,
                    'identifier': mp.full_name or getattr(mp.user, 'username', f"ID-{mp.pk}"),
                    'field_name': 'profile_photo',
                    'instance': mp,
                    'file_field': mp.profile_photo,
                    'raw_path': str(mp.profile_photo.name).replace('\\', '/'),
                    'is_private': False,
                })

        # 4. ResumeAnalysis.uploaded_file (Private)
        for ra in ResumeAnalysis.objects.exclude(uploaded_file='').exclude(uploaded_file=None):
            if ra.uploaded_file and ra.uploaded_file.name:
                references.append({
                    'model_name': 'ResumeAnalysis',
                    'record_id': ra.pk,
                    'identifier': getattr(ra.user, 'username', f"ID-{ra.pk}"),
                    'field_name': 'uploaded_file',
                    'instance': ra,
                    'file_field': ra.uploaded_file,
                    'raw_path': str(ra.uploaded_file.name).replace('\\', '/'),
                    'is_private': True,
                })

        # 5. MentorProfile.resume (Private)
        for mp in MentorProfile.objects.exclude(resume='').exclude(resume=None):
            if mp.resume and mp.resume.name:
                references.append({
                    'model_name': 'MentorProfile',
                    'record_id': mp.pk,
                    'identifier': mp.full_name or getattr(mp.user, 'username', f"ID-{mp.pk}"),
                    'field_name': 'resume',
                    'instance': mp,
                    'file_field': mp.resume,
                    'raw_path': str(mp.resume.name).replace('\\', '/'),
                    'is_private': True,
                })

        total_references = len(references)
        public_refs = [r for r in references if not r['is_private']]
        private_refs = [r for r in references if r['is_private']]
        unique_paths = set(ref['raw_path'] for ref in references)
        duplicate_refs_count = total_references - len(unique_paths)

        self.stdout.write(f"\nDiscovered {total_references} asset reference(s) across {len(unique_paths)} unique path(s):")
        self.stdout.write(f"  • Public image references:   {len(public_refs)}")
        self.stdout.write(f"  • Private resume references: {len(private_refs)}")
        if duplicate_refs_count > 0:
            self.stdout.write(f"  • Duplicate/shared paths:    {duplicate_refs_count}")

        # Metrics
        files_existing_locally = 0
        files_missing_locally = 0
        files_already_in_target = 0
        files_would_upload = 0
        files_uploaded_success = 0
        invalid_or_error_files = 0

        # Cache of uploaded paths during execution to prevent redundant uploads of duplicate files
        already_uploaded_in_run = set()

        self.stdout.write("\n--- Processing Discovered References ---")

        for ref in references:
            rel_path = ref['raw_path']
            is_priv = ref['is_private']
            policy_label = "PRIVATE (authenticated)" if is_priv else "PUBLIC (upload)"
            dest_backend = private_storage if is_priv else public_storage
            model_desc = f"{ref['model_name']} (ID {ref['record_id']}, {ref['identifier']}) [{policy_label}]"

            # Check if source file exists locally
            local_exists = legacy_fs.exists(rel_path)

            if not local_exists:
                files_missing_locally += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  [MISSING LOCAL] {model_desc} field '{ref['field_name']}': "
                        f"'{rel_path}' not found in source directory. Preserving database reference."
                    )
                )
                continue

            files_existing_locally += 1

            # Check if target storage already has this asset in Cloudinary
            target_exists = False
            if rel_path in already_uploaded_in_run:
                target_exists = True
            else:
                try:
                    target_exists = dest_backend.exists(rel_path)
                except Exception:
                    target_exists = False

            if target_exists:
                files_already_in_target += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [ALREADY PRESENT IN CLOUDINARY] {model_desc}: '{rel_path}' is already available in Cloudinary target."
                    )
                )
                continue

            # File exists locally and is not yet in target storage
            if not execute_mode:
                files_would_upload += 1
                file_size = legacy_fs.size(rel_path)
                self.stdout.write(
                    f"  [DRY-RUN] {model_desc}: would upload '{rel_path}' ({file_size} bytes) to Cloudinary via {dest_backend.__class__.__name__}."
                )
            else:
                # Execute upload safely
                try:
                    with legacy_fs.open(rel_path, 'rb') as f:
                        saved_name = dest_backend.save(rel_path, f)
                        already_uploaded_in_run.add(rel_path)
                        already_uploaded_in_run.add(saved_name)
                    files_uploaded_success += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [UPLOADED] {model_desc}: '{rel_path}' successfully migrated as '{saved_name}'."
                        )
                    )
                except Exception as upload_err:
                    invalid_or_error_files += 1
                    self.stderr.write(
                        self.style.ERROR(
                            f"  [UPLOAD ERROR] {model_desc}: failed to upload '{rel_path}': {upload_err}. Database record preserved."
                        )
                    )

        # Final Summary
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Migration Summary ==="))
        self.stdout.write(f"Total asset references discovered:   {total_references}")
        self.stdout.write(f"  - Public image references:         {len(public_refs)}")
        self.stdout.write(f"  - Private document references:     {len(private_refs)}")
        self.stdout.write(f"Unique source files discovered:       {len(unique_paths)}")
        self.stdout.write(f"Duplicate references detected:        {duplicate_refs_count}")
        self.stdout.write(f"Files existing locally:               {files_existing_locally}")
        self.stdout.write(f"Files missing locally on disk:        {files_missing_locally} (database records preserved)")
        self.stdout.write(f"Files already available in Cloudinary:{files_already_in_target}")
        if execute_mode:
            self.stdout.write(self.style.SUCCESS(f"Files successfully uploaded:          {files_uploaded_success}"))
        else:
            self.stdout.write(self.style.NOTICE(f"Files that would be uploaded:         {files_would_upload}"))
        self.stdout.write(f"Errors / failed uploads:              {invalid_or_error_files}")

        if not execute_mode:
            self.stdout.write(
                self.style.WARNING(
                    "\nTo execute actual uploads to Cloudinary, run with the --execute flag:\n"
                    "  python manage.py migrate_profile_images_to_cloudinary --execute"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nMigration execution completed successfully."))
