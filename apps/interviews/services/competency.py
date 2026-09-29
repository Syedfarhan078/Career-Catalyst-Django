"""
Interview Competency Evidence Service for CareerCatalyst.

Maintains a cautious, verifiable evidence model for skills demonstrated in technical assessments,
coding challenges, and mock interviews.
Distinguishes interview evidence from self-reported profile skills and roadmap-earned skills,
and provides a clean service API for platform integration.
"""

from typing import Dict, List, Set, Any
from django.utils import timezone
from apps.interviews.models import InterviewCompetencyEvidence, Question


class CompetencyEvidenceService:
    MIN_SCORE_THRESHOLD = 75

    @classmethod
    def record_evidence(
        cls,
        user,
        skill_name: str,
        source_type: str,
        score: int,
        confidence_weight: float = 1.0,
        notes: str = ""
    ) -> Any:
        """
        Records an interview competency evidence event.
        Requires authenticated user and score >= MIN_SCORE_THRESHOLD.
        """
        if not user or not user.is_authenticated:
            return None

        clean_skill = (skill_name or "").strip()
        if not clean_skill or score < cls.MIN_SCORE_THRESHOLD:
            return None

        evidence = InterviewCompetencyEvidence.objects.create(
            user=user,
            skill_name=clean_skill,
            source_type=source_type,
            score=score,
            confidence_weight=confidence_weight,
            notes=notes
        )
        return evidence

    @classmethod
    def record_coding_evidence(cls, user, question: Question, score: int):
        """Records evidence from coding challenge completion."""
        if score < cls.MIN_SCORE_THRESHOLD or not question:
            return

        skills_str = getattr(question, 'skills_evaluated', '')
        if not skills_str:
            # Fall back to title or category
            skills_str = question.title

        for raw_s in skills_str.split(','):
            clean_s = raw_s.strip()
            if clean_s:
                cls.record_evidence(
                    user=user,
                    skill_name=clean_s,
                    source_type='CODING_CHALLENGE',
                    score=score,
                    confidence_weight=1.0,
                    notes=f"Solved coding challenge '{question.title}' with {score}% score."
                )

    @classmethod
    def record_star_evidence(cls, user, question: Question, score: int):
        """Records evidence from behavioral STAR completion."""
        if score < cls.MIN_SCORE_THRESHOLD or not question:
            return

        skills_str = getattr(question, 'skills_evaluated', '') or "Behavioral & STAR Communication"
        for raw_s in skills_str.split(','):
            clean_s = raw_s.strip()
            if clean_s:
                cls.record_evidence(
                    user=user,
                    skill_name=clean_s,
                    source_type='BEHAVIORAL_STAR',
                    score=score,
                    confidence_weight=0.8,
                    notes=f"Completed STAR behavioral question '{question.title}' with {score}% score."
                )

    @classmethod
    def get_user_verified_interview_skills(cls, user) -> Set[str]:
        """
        Returns a normalized set of skill names verified through strong interview performance.
        Does NOT touch or mutate StudentProfile.skills.
        """
        if not user or not user.is_authenticated:
            return set()

        evidences = InterviewCompetencyEvidence.objects.filter(
            user=user,
            score__gte=cls.MIN_SCORE_THRESHOLD
        ).values_list('skill_name', flat=True)

        return {s.strip() for s in evidences if s.strip()}
