"""
Quiz Engine Service for CareerCatalyst.

Provides deterministic, scalable MCQ question selection, server-managed QuizSession lifecycle,
multi-tab anti-clash isolation, server-side timer enforcement, and transactional submissions.
"""

import random
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from apps.interviews.models import (
    QuestionCategory,
    Question,
    QuizSession,
    UserAttempt,
    UserAttemptDetail
)


class QuizEngineService:
    DEFAULT_QUESTION_COUNT = 5
    DEFAULT_DURATION_MINUTES = 10

    @classmethod
    def select_balanced_questions(
        cls,
        category: QuestionCategory,
        count: int = DEFAULT_QUESTION_COUNT
    ) -> List[Question]:
        """
        Scalable, balanced question selection that completely avoids SQL ORDER BY RANDOM() (order_by('?')).
        Fetches question IDs by difficulty bucket and samples in Python using random.sample.
        """
        # Group IDs by difficulty
        easy_ids = list(
            Question.objects.filter(
                category=category,
                question_type='MCQ',
                difficulty='Easy'
            ).values_list('id', flat=True)
        )
        med_ids = list(
            Question.objects.filter(
                category=category,
                question_type='MCQ',
                difficulty='Medium'
            ).values_list('id', flat=True)
        )
        hard_ids = list(
            Question.objects.filter(
                category=category,
                question_type='MCQ',
                difficulty='Hard'
            ).values_list('id', flat=True)
        )

        selected_ids: List[int] = []

        # Target 2 Easy, 2 Medium, 1 Hard if available
        if easy_ids and med_ids and hard_ids and count >= 5:
            selected_ids.extend(random.sample(easy_ids, min(2, len(easy_ids))))
            selected_ids.extend(random.sample(med_ids, min(2, len(med_ids))))
            selected_ids.extend(random.sample(hard_ids, min(1, len(hard_ids))))

        # If not filled to target count, fill from remaining available IDs
        all_candidate_ids = list(
            Question.objects.filter(
                category=category,
                question_type='MCQ'
            ).values_list('id', flat=True)
        )

        remaining_pool = [qid for qid in all_candidate_ids if qid not in selected_ids]
        needed = count - len(selected_ids)
        if needed > 0 and remaining_pool:
            selected_ids.extend(random.sample(remaining_pool, min(needed, len(remaining_pool))))

        # Fetch questions preserving order
        questions_map = {
            q.id: q for q in Question.objects.filter(id__in=selected_ids)
        }
        return [questions_map[qid] for qid in selected_ids if qid in questions_map]

    @classmethod
    def get_or_create_active_session(
        cls,
        user,
        category: QuestionCategory,
        count: int = DEFAULT_QUESTION_COUNT,
        duration_minutes: int = DEFAULT_DURATION_MINUTES
    ) -> Tuple[QuizSession, List[Question], bool]:
        """
        Retrieves an active, unexpired, unsubmitted session or creates a new one.
        Returns (quiz_session, questions, created).
        """
        now = timezone.now()

        # Look for an existing non-submitted, non-expired session for this user & category
        active_session = QuizSession.objects.filter(
            user=user,
            category=category,
            is_submitted=False,
            expires_at__gt=now
        ).order_by('-started_at').first()

        if active_session:
            # Load stored questions
            q_ids = active_session.question_ids
            q_map = {q.id: q for q in Question.objects.filter(id__in=q_ids)}
            questions = [q_map[qid] for qid in q_ids if qid in q_map]
            if questions:
                return active_session, questions, False

        # Create new session
        questions = cls.select_balanced_questions(category, count=count)
        if not questions:
            return None, [], False

        q_ids = [q.id for q in questions]
        expires_at = now + timedelta(minutes=duration_minutes)

        quiz_session = QuizSession.objects.create(
            user=user,
            category=category,
            started_at=now,
            expires_at=expires_at,
            question_ids=q_ids
        )
        return quiz_session, questions, True

    @classmethod
    def get_session_by_uuid(cls, user, session_uuid_str: str) -> Optional[QuizSession]:
        """Safely fetches a QuizSession by UUID verifying user ownership."""
        try:
            s_uuid = uuid.UUID(str(session_uuid_str))
            return QuizSession.objects.filter(user=user, session_uuid=s_uuid).first()
        except (ValueError, TypeError):
            return None

    @classmethod
    def submit_quiz_session(
        cls,
        user,
        session_uuid_str: Optional[str],
        category_id: Optional[int],
        answers_dict: Dict[str, str],
        client_violations_count: int = 0
    ) -> Dict[str, Any]:
        """
        Processes quiz submission with atomic transaction and lock.
        Idempotent: if already submitted, returns the existing attempt.
        """
        now = timezone.now()

        with transaction.atomic():
            quiz_session = None

            # 1. Resolve session via UUID
            if session_uuid_str:
                try:
                    s_uuid = uuid.UUID(str(session_uuid_str))
                    quiz_session = QuizSession.objects.select_for_update().filter(
                        session_uuid=s_uuid
                    ).first()
                except (ValueError, TypeError):
                    pass

            # Fallback for legacy requests passing category_id
            if not quiz_session and category_id:
                quiz_session = QuizSession.objects.select_for_update().filter(
                    user=user,
                    category_id=category_id,
                    is_submitted=False
                ).order_by('-started_at').first()

            if not quiz_session:
                raise ValidationError("No active quiz session found.")

            if quiz_session.user_id != user.id:
                raise PermissionDenied("You do not have permission to submit this quiz session.")

            # Idempotency check
            if quiz_session.is_submitted and quiz_session.attempt:
                attempt = quiz_session.attempt
                return {
                    "attempt": attempt,
                    "category": quiz_session.category,
                    "score": attempt.score,
                    "correct_count": attempt.details.filter(is_correct=True).count(),
                    "total": len(quiz_session.question_ids),
                    "already_submitted": True,
                    "is_expired": False
                }

            # Check expiry
            is_expired = quiz_session.is_expired

            # Evaluate answers
            question_ids = quiz_session.question_ids
            questions = Question.objects.filter(id__in=question_ids)
            q_map = {q.id: q for q in questions}

            correct_count = 0
            details_to_create = []

            # Create attempt
            attempt = UserAttempt.objects.create(
                user=user,
                category=quiz_session.category,
                proctor_violations_count=max(0, client_violations_count)
            )

            for qid in question_ids:
                q = q_map.get(qid)
                if not q:
                    continue

                user_ans = answers_dict.get(f"question_{q.id}", "").strip().upper()
                is_correct = bool(user_ans and q.correct_option and user_ans == q.correct_option.strip().upper())
                if is_correct:
                    correct_count += 1

                details_to_create.append(
                    UserAttemptDetail(
                        attempt=attempt,
                        question=q,
                        user_answer=user_ans,
                        is_correct=is_correct
                    )
                )

            UserAttemptDetail.objects.bulk_create(details_to_create)

            total_q = len(question_ids)
            score = int(round((correct_count / total_q) * 100)) if total_q > 0 else 0

            attempt.score = score
            attempt.save(update_fields=['score'])

            # Finalize session
            quiz_session.is_submitted = True
            quiz_session.submitted_at = now
            quiz_session.score = score
            quiz_session.attempt = attempt
            quiz_session.save(update_fields=['is_submitted', 'submitted_at', 'score', 'attempt'])

            # Record competency evidence if high score
            if score >= 80:
                cls._record_quiz_competency(user, quiz_session.category, score)

            return {
                "attempt": attempt,
                "category": quiz_session.category,
                "score": score,
                "correct_count": correct_count,
                "total": total_q,
                "already_submitted": False,
                "is_expired": is_expired
            }

    @classmethod
    def _record_quiz_competency(cls, user, category: QuestionCategory, score: int):
        """Records interview competency evidence for strong quiz completion."""
        try:
            from apps.interviews.models import InterviewCompetencyEvidence
            skill_name = category.name
            InterviewCompetencyEvidence.objects.create(
                user=user,
                skill_name=skill_name,
                source_type='TECHNICAL_QUIZ',
                score=score,
                confidence_weight=0.8,
                notes=f"Achieved {score}% on {category.name} assessment."
            )
        except Exception:
            pass
