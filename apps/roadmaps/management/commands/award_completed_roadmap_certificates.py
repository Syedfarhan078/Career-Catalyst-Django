"""
Management command to retroactively award RoadmapCertificates to students
who have completed 100% of required topics in enrolled roadmaps.

Idempotent, non-destructive, and supports --dry-run.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.roadmaps.models import UserRoadmap, CareerPath, Topic, RoadmapCertificate
from apps.roadmaps.services import check_and_award_roadmap_certificate

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Evaluates enrolled roadmaps and awards RoadmapCertificates to students "
        "who have completed all required topics. Fully idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate execution and display eligible completions without awarding certificates.'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Target a specific username.'
        )
        parser.add_argument(
            '--path',
            type=str,
            help='Target a specific career path slug or ID.'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        username = options.get('user')
        path_query = options.get('path')

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode. No certificates will be created."))

        # Build UserRoadmap queryset
        enrollments = UserRoadmap.objects.select_related('user', 'career_path').prefetch_related('topic_progress')

        if username:
            try:
                target_user = User.objects.get(username=username)
                enrollments = enrollments.filter(user=target_user)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User with username '{username}' does not exist."))
                return

        if path_query:
            if path_query.isdigit():
                enrollments = enrollments.filter(career_path_id=int(path_query))
            else:
                enrollments = enrollments.filter(career_path__slug=path_query)

        total_scanned = 0
        already_certified = 0
        newly_awarded = 0
        would_award = 0
        skipped_incomplete = 0
        skipped_empty_roadmap = 0

        self.stdout.write(self.style.NOTICE(f"Scanning {enrollments.count()} user roadmap enrollment(s)..."))

        for enrollment in enrollments:
            total_scanned += 1
            user = enrollment.user
            path = enrollment.career_path

            total_topics = Topic.objects.filter(milestone__career_path=path).count()
            if total_topics == 0:
                skipped_empty_roadmap += 1
                continue

            completed_topics = enrollment.topic_progress.filter(is_completed=True).count()
            if completed_topics < total_topics:
                skipped_incomplete += 1
                continue

            # Check if certificate already exists
            existing_cert = RoadmapCertificate.objects.filter(user=user, career_path=path).first()
            if existing_cert:
                already_certified += 1
                continue

            # Eligible for issuance
            if dry_run:
                would_award += 1
                self.stdout.write(
                    f"  [ELIGIBLE] {user.username} has completed {completed_topics}/{total_topics} topics in '{path.name}'."
                )
            else:
                cert, created = check_and_award_roadmap_certificate(user, path)
                if created and cert:
                    newly_awarded += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  [AWARDED] Certificate {cert.certificate_id} issued to {user.username} for '{path.name}'."
                    ))
                elif cert:
                    already_certified += 1

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("ROADMAP CERTIFICATE ISSUANCE SUMMARY")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total Enrollments Scanned: {total_scanned}")
        self.stdout.write(f"Already Certified:        {already_certified}")
        if dry_run:
            self.stdout.write(f"Eligible (Would Award):    {would_award}")
        else:
            self.stdout.write(f"Newly Awarded:             {newly_awarded}")
        self.stdout.write(f"Skipped (Incomplete):      {skipped_incomplete}")
        self.stdout.write(f"Skipped (Empty Roadmap):   {skipped_empty_roadmap}")
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN completed. Database unmodified."))
        else:
            self.stdout.write(self.style.SUCCESS("Certificate award processing completed successfully."))
