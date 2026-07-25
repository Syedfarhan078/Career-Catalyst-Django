from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.community.models import (
    ForumCategory, MentorProfile, SharedProject, SuccessStory, 
    MentorSkill, MentorAvailability
)

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds the database with community categories, mentor profiles, shared projects, and success stories."

    def handle(self, *args, **options):
        # 1. Seed Forum Categories
        categories = [
            {"name": "General Discussion", "slug": "general", "desc": "Chat about anything related to tech, learning, and student life."},
            {"name": "Career Advice", "slug": "career-advice", "desc": "Get suggestions on career tracks, job hunting, and salaries."},
            {"name": "Resumes & Portfolios", "slug": "resumes-portfolios", "desc": "Share your resume/portfolio for constructive feedback."},
            {"name": "Interview Preparation", "slug": "interview-prep", "desc": "Discuss technical questions, mock interviews, and system design."}
        ]

        seeded_cats = []
        for cat_data in categories:
            cat, created = ForumCategory.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={
                    "name": cat_data["name"],
                    "description": cat_data["desc"]
                }
            )
            seeded_cats.append(cat)
            if created:
                self.stdout.write(f"Created category: {cat.name}")

        # 2. Seed Mentor Users & Profiles
        mentors_data = [
            {
                "username": "alex_mentor",
                "email": "alex.mentor@example.com",
                "full_name": "Alex Carter",
                "phone": "+1 415 555 0199",
                "designation": "Senior Software Engineer",
                "company": "Google",
                "location": "San Francisco, CA",
                "bio": "Alex is a backend systems expert with 7+ years of experience in distributed databases, scale architectures, and system design. Former lead engineer at Google Maps.",
                "domains": "Backend, System Design",
                "skills": "Python, Django, PostgreSQL, Docker, Redis",
                "experience": 8,
                "rating": 4.8
            },
            {
                "username": "sarah_mentor",
                "email": "sarah.mentor@example.com",
                "full_name": "Sarah Miller",
                "phone": "+91 80 9876 5432",
                "designation": "Lead Data Scientist",
                "company": "Meta",
                "location": "Bengaluru, India",
                "bio": "Sarah leads machine learning operations for recommendation systems. Passionate about helping students transition into ML and statistics.",
                "domains": "Data Science, Machine Learning",
                "skills": "Python, PyTorch, Scikit-Learn, SQL, Pandas",
                "experience": 6,
                "rating": 4.9
            },
            {
                "username": "michael_mentor",
                "email": "michael.mentor@example.com",
                "full_name": "Michael Chang",
                "phone": "+1 206 555 0144",
                "designation": "Product Manager",
                "company": "Amazon",
                "location": "Seattle, WA",
                "bio": "Michael translates tech capabilities into customer-centric products. Expert in product strategy, A/B testing, and cross-functional leadership.",
                "domains": "Product Management, Agile",
                "skills": "Product Strategy, Agile, Scrum, SQL, Figma",
                "experience": 5,
                "rating": 4.7
            },
            {
                "username": "emily_mentor",
                "email": "emily.mentor@example.com",
                "full_name": "Emily Watson",
                "phone": "+1 212 555 0177",
                "designation": "DevOps Architect",
                "company": "Microsoft",
                "location": "New York, NY",
                "bio": "Emily builds automated CI/CD environments and secure cloud-native architectures. Azure Certified Expert, Open source contributor.",
                "domains": "DevOps, Cloud",
                "skills": "Terraform, Kubernetes, Docker, CI/CD, Azure",
                "experience": 9,
                "rating": 4.6
            }
        ]

        mentor_users = []
        for m in mentors_data:
            user, u_created = User.objects.update_or_create(
                username=m["username"],
                defaults={
                    "email": m["email"],
                    "bio": m["bio"],
                    "is_active": True
                }
            )
            if u_created:
                user.set_password("mentorpass123")
                user.save()
                self.stdout.write(f"Created user: {user.username}")

            profile, p_created = MentorProfile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": m["full_name"],
                    "email": m["email"],
                    "phone_number": m["phone"],
                    "company": m["company"],
                    "designation": m["designation"],
                    "experience_years": m["experience"],
                    "current_location": m["location"],
                    "bio": m["bio"],
                    "career_domains": m["domains"],
                    "skills": m["skills"],
                    "languages": "English",
                    "available_days": "Monday, Wednesday, Friday",
                    "available_time_slots": "10:00 AM - 12:00 PM, 04:00 PM - 06:00 PM",
                    "rating": m["rating"],
                    "status": "Approved",
                    "verified": True
                }
            )
            mentor_users.append(user)
            
            if p_created:
                self.stdout.write(f"Created mentor profile: {profile.full_name}")
            else:
                self.stdout.write(f"Updated mentor profile: {profile.full_name}")

            # Seed MentorSkills
            profile.mentor_skills.all().delete()
            skills_list = [s.strip() for s in m["skills"].split(",") if s.strip()]
            for skill_name in skills_list:
                MentorSkill.objects.create(mentor=profile, name=skill_name)

            # Seed MentorAvailabilities
            profile.availabilities.all().delete()
            days = ["Monday", "Wednesday", "Friday"]
            for day in days:
                MentorAvailability.objects.create(
                    mentor=profile,
                    day=day,
                    start_time="10:00:00",
                    end_time="12:00:00",
                    max_sessions=2
                )

        # 3. Seed Shared Projects (using first mentor as author)
        default_author = mentor_users[0]
        projects_data = [
            {
                "title": "Collaborative Task Manager",
                "desc": "Real-time collaborative task planner built with Django Channels, WebSockets, and Redis. Features interactive boards, task cards, drag-and-drop, and team visibility logs.",
                "github": "https://github.com/example/task-manager",
                "live": "https://task-manager-demo.example.com",
                "tags": "Django, WebSockets, Redis, JavaScript, Bootstrap"
            },
            {
                "title": "AI Image Upscaler",
                "desc": "Deep learning image processing service that increases resolution by 4x using pre-trained super-resolution CNNs. Wrapped in a FastAPI container and hosted on AWS Lambda.",
                "github": "https://github.com/example/image-upscaler",
                "live": "https://upscaler.example.com",
                "tags": "Python, FastAPI, PyTorch, Docker, AWS"
            },
            {
                "title": "Crypto Portfolio Tracker",
                "desc": "Single Page Application that aggregates real-time price rates from CoinGecko API. Users can input holdings, visualize returns in interactive charts, and set price target alerts.",
                "github": "https://github.com/example/portfolio-tracker",
                "live": "https://crypto-tracker.example.com",
                "tags": "React, CSS, ChartJS, API, Netlify"
            }
        ]

        for p in projects_data:
            proj, created = SharedProject.objects.get_or_create(
                title=p["title"],
                defaults={
                    "description": p["desc"],
                    "github_link": p["github"],
                    "live_link": p["live"],
                    "tags": p["tags"],
                    "author": default_author
                }
            )
            if created:
                self.stdout.write(f"Created shared project: {proj.title}")

        # 4. Seed Career Success Stories
        stories_data = [
            {
                "title": "Landing a Backend Role at Google",
                "author_name": "Daniel Carter",
                "role": "Software Engineer (Backend)",
                "company": "Google",
                "grad_year": 2025,
                "content": "Transitioning from college projects to Google's system design rounds was tough. Career Catalyst helped me structure my learning roadmaps and mock interviews. My key tip: master your database index mechanisms and keep coding every day!"
            },
            {
                "title": "Breaking into Data Science from Non-Tech",
                "author_name": "Sophia Martinez",
                "role": "Data Analyst / Scientist",
                "company": "Meta",
                "grad_year": 2024,
                "content": "I graduated with an Economics degree but wanted to do data modeling. I built a solid portfolio, shared my clean data pipelines in the community here, and was followed by mentors who pointed me to recruiter referrals. Master SQL first and tell compelling stories with data graphs!"
            },
            {
                "title": "Navigating Off-Campus Placements",
                "author_name": "Rohan Sharma",
                "role": "Associate PM",
                "company": "Amazon",
                "grad_year": 2025,
                "content": "Off-campus hiring is a numbers game, but quality beats volume. I refined my resume with the ATS Analyzer tool, customized it for PM roles, and practiced STAR behavioral answers. Learn to describe the 'Result' in raw numbers!"
            }
        ]

        for s in stories_data:
            story, created = SuccessStory.objects.get_or_create(
                title=s["title"],
                defaults={
                    "author_name": s["author_name"],
                    "placed_role": s["role"],
                    "placed_company": s["company"],
                    "content": s["content"],
                    "grad_year": s["grad_year"]
                }
            )
            if created:
                self.stdout.write(f"Created success story: {story.title}")

        self.stdout.write(self.style.SUCCESS("Community database seeding completed successfully!"))
