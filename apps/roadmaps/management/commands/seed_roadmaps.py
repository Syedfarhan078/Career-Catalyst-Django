from django.core.management.base import BaseCommand
from apps.roadmaps.models import CareerPath, Milestone, Topic
from apps.roadmaps.roadmaps_data import CAREER_PATHS


class Command(BaseCommand):
    help = 'Seed the database with pre-built career roadmap data.'

    def handle(self, *args, **options):
        created_paths = 0
        created_milestones = 0
        created_topics = 0

        for path_data in CAREER_PATHS:
            path, path_created = CareerPath.objects.get_or_create(
                slug=path_data['slug'],
                defaults={
                    'name': path_data['name'],
                    'description': path_data['description'],
                    'icon': path_data['icon'],
                    'estimated_weeks': path_data['estimated_weeks'],
                    'difficulty': path_data['difficulty'],
                }
            )
            if path_created:
                created_paths += 1
                self.stdout.write(f"  + Created path: {path.name}")
            else:
                self.stdout.write(f"  - Path already exists: {path.name}")
                continue  # Skip creating milestones if path already exists

            for ms_data in path_data.get('milestones', []):
                milestone, ms_created = Milestone.objects.get_or_create(
                    career_path=path,
                    week_number=ms_data['week'],
                    defaults={
                        'title': ms_data['title'],
                        'level': ms_data['level'],
                        'order': ms_data['week'],
                    }
                )
                if ms_created:
                    created_milestones += 1

                for idx, topic_data in enumerate(ms_data.get('topics', [])):
                    _, t_created = Topic.objects.get_or_create(
                        milestone=milestone,
                        title=topic_data['title'],
                        defaults={
                            'description': topic_data.get('desc', ''),
                            'resource_url': topic_data.get('url', ''),
                            'resource_type': topic_data.get('type', 'Article'),
                            'estimated_hours': topic_data.get('hours', 2),
                            'order': idx,
                        }
                    )
                    if t_created:
                        created_topics += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeding complete! Created {created_paths} paths, "
            f"{created_milestones} milestones, {created_topics} topics."
        ))
