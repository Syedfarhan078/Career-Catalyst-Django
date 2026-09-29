"""
Management command to validate and audit roadmap-earned skills for all existing users.
Safe and idempotent: does NOT mutate StudentProfile.skills.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.roadmaps.models import TopicProgress
from apps.roadmaps.services import get_topic_skills, get_user_earned_skills_set

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Validates and audits roadmap-earned skills across all completed user progress. "
        "Does NOT permanently append earned skills to StudentProfile.skills."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Auditing roadmap-earned skills across user records..."))

        total_completed_progresses = TopicProgress.objects.filter(is_completed=True).select_related('topic', 'user_roadmap__user')
        total_count = total_completed_progresses.count()

        unresolved_topics = set()
        resolved_skills_count = 0
        users_with_earned_skills = set()

        for progress in total_completed_progresses:
            user = progress.user_roadmap.user
            topic = progress.topic
            skills = get_topic_skills(topic)
            if not skills:
                unresolved_topics.add((topic.id, topic.title, topic.milestone.career_path.name))
            else:
                resolved_skills_count += len(skills)
                users_with_earned_skills.add(user.id)

        self.stdout.write(f"Total completed topic progress records audited: {total_count}")
        self.stdout.write(f"Users with active roadmap-earned skills: {len(users_with_earned_skills)}")

        if unresolved_topics:
            self.stdout.write(self.style.WARNING(
                f"\nWarning: Found {len(unresolved_topics)} completed topics with empty skills_taught:"
            ))
            for t_id, t_title, p_name in unresolved_topics:
                self.stdout.write(f"  - [ID: {t_id}] '{t_title}' in path '{p_name}'")
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nAll completed topic progress records resolve cleanly to authoritative skills_taught!"
            ))

        self.stdout.write(self.style.SUCCESS("Audit complete. Zero profile mutations performed."))
