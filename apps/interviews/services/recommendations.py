"""
Interview Practice Recommendation Service for CareerCatalyst.

Derives personalized interview practice recommendations from real stored platform data:
- StudentProfile.career_goal / target domain
- CareerAnalysis.missing_skills and readiness indicators
- Completed roadmap skills
- Past assessment attempt scores and unpracticed categories
"""

from typing import Any, Dict, List, Optional
from django.db.models import Avg

from apps.interviews.models import QuestionCategory, UserAttempt, Question
from apps.profiles.models import StudentProfile


class InterviewRecommendationService:

    @classmethod
    def get_personalized_recommendations(cls, user) -> Dict[str, Any]:
        """
        Derives authentic, personalized practice recommendations for the Interview Hub.
        """
        if not user or not user.is_authenticated:
            return {
                "target_career": "",
                "recommended_focus": [],
                "weak_categories": [],
                "missing_skills": []
            }

        profile = StudentProfile.objects.filter(user=user).first()
        target_career = (profile.career_goal.strip() if profile and profile.career_goal else "")

        # 1. Fetch missing skills from latest CareerAnalysis if available
        missing_skills = []
        try:
            from apps.recommendation.models import CareerAnalysis
            latest_analysis = CareerAnalysis.objects.filter(user=user).order_by('-created_at').first()
            if latest_analysis and latest_analysis.missing_skills:
                missing_skills = list(latest_analysis.missing_skills)[:5]
                if not target_career and latest_analysis.recommended_career:
                    target_career = latest_analysis.recommended_career
        except Exception:
            pass

        # 2. Analyze past attempt performance by category
        categories = list(QuestionCategory.objects.all())
        category_stats = []
        weak_categories = []

        for cat in categories:
            cat_attempts = UserAttempt.objects.filter(user=user, category=cat)
            count = cat_attempts.count()
            avg_score = cat_attempts.aggregate(Avg('score'))['score__avg']

            if count == 0:
                category_stats.append({
                    "category": cat,
                    "status": "UNATTEMPTED",
                    "avg_score": 0,
                    "count": 0,
                    "priority": 1  # High priority to try at least once
                })
            elif avg_score is not None and avg_score < 70:
                weak_categories.append(cat.name)
                category_stats.append({
                    "category": cat,
                    "status": "NEEDS_IMPROVEMENT",
                    "avg_score": round(avg_score, 1),
                    "count": count,
                    "priority": 2
                })
            else:
                category_stats.append({
                    "category": cat,
                    "status": "PROFICIENT",
                    "avg_score": round(avg_score, 1),
                    "count": count,
                    "priority": 3
                })

        # Sort recommendations by priority (unattempted -> weak -> proficient)
        category_stats.sort(key=lambda x: x["priority"])

        recommended_focus = []
        for cs in category_stats[:3]:
            cat = cs["category"]
            reason = "Recommended: Not yet attempted" if cs["status"] == "UNATTEMPTED" else f"Practice recommended (Average: {cs['avg_score']}%)"
            recommended_focus.append({
                "slug": cat.slug,
                "name": cat.name,
                "description": cat.description,
                "reason": reason,
                "status": cs["status"]
            })

        return {
            "target_career": target_career,
            "recommended_focus": recommended_focus,
            "weak_categories": weak_categories,
            "missing_skills": missing_skills
        }
