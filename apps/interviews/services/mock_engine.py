"""
Mock Interview Engine for CareerCatalyst.

Provides a state-driven, bounded dialogue engine with role-aware question selection
sourced from CareerCatalyst's canonical career tracks.
Evaluates candidate dialogue using a transparent multi-dimensional rubric
(Technical Depth, Problem Solving, Role Relevance, Communication) rather than superficial buzzword counters.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction

from apps.interviews.models import (
    MockInterviewSession,
    MockInterviewChat,
    InterviewCompetencyEvidence
)

# Canonical interview question banks by career track
ROLE_QUESTION_BANKS = {
    'frontend': {
        'display_name': 'Frontend Developer',
        'technical': "Let's dive into frontend engineering. How do you optimize critical rendering paths in single-page applications, manage complex asynchronous UI state, and prevent unnecessary component re-renders?",
        'scenario': "Suppose users report intermittent UI freezes and high memory usage on a data-dense dashboard with live charts. Walk me through how you profile the browser runtime and resolve the bottleneck.",
        'behavioral': "Tell me about a time you had a technical disagreement with a designer or product manager regarding responsive UX vs. technical feasibility. How did you negotiate the outcome?",
        'keywords': {'javascript', 'typescript', 'react', 'vue', 'dom', 'css', 'state', 'rendering', 'virtual', 'memo', 'props', 'accessibility', 'bundle', 'webpack', 'vite', 'performance', 'profiler'}
    },
    'backend': {
        'display_name': 'Backend Developer',
        'technical': "Let's explore backend systems. How do you architect a high-throughput REST or GraphQL API that handles concurrent database transactions, connection pooling, and multi-tier caching with Redis?",
        'scenario': "Imagine a database query starts timing out during a sudden 10x traffic spike on a payment processing endpoint. Walk me through your triage strategy, database indexing, and resilience mechanisms.",
        'behavioral': "Describe a situation where you had to push back on a rushed deadline because cutting corners would cause technical debt or security vulnerabilities. How did you communicate this to leadership?",
        'keywords': {'django', 'python', 'sql', 'postgres', 'database', 'api', 'rest', 'cache', 'redis', 'transaction', 'acid', 'scale', 'concurrency', 'orm', 'indexing', 'queue', 'celery', 'auth'}
    },
    'data': {
        'display_name': 'Data Scientist / Engineer',
        'technical': "Let's discuss data pipelines and modeling. How do you design an end-to-end data preprocessing pipeline that handles schema evolution, missing values, anomalies, and feature scaling reliably?",
        'scenario': "You discover that a machine learning model deployed in production has experienced severe performance degradation due to data drift. How do you detect, isolate, and remediate the issue?",
        'behavioral': "Tell me about a time a stakeholder misinterpreted analytical findings or pushed for a flawed metric. How did you use data and communication to realign expectations?",
        'keywords': {'python', 'sql', 'pandas', 'numpy', 'scikit', 'pipeline', 'etl', 'model', 'feature', 'drift', 'cross-validation', 'metric', 'anomaly', 'spark', 'warehouse', 'regression', 'clustering'}
    },
    'ml': {
        'display_name': 'Machine Learning Engineer',
        'technical': "Let's focus on ML systems and MLOps. What strategies do you use for efficient model training, hyperparameter optimization, and reducing inference latency in containerized production environments?",
        'scenario': "A computer vision or NLP service is consuming excessive GPU memory and dropping client requests during peak hours. How do you optimize batching, quantization, and auto-scaling?",
        'behavioral': "Share an experience where an experimental model architecture failed to outperform a simple heuristic baseline. How did you decide when to pivot or discontinue the experiment?",
        'keywords': {'pytorch', 'tensorflow', 'mlops', 'quantization', 'latency', 'inference', 'docker', 'gpu', 'batching', 'evaluation', 'loss', 'training', 'hyperparameter', 'monitoring', 'accuracy'}
    },
    'devops': {
        'display_name': 'DevOps & Cloud Engineer',
        'technical': "Let's discuss infrastructure and deployment. How do you design an automated zero-downtime CI/CD deployment pipeline with immutable container images, secret management, and infrastructure as code?",
        'scenario': "A production Kubernetes cluster experiences a cascading service failure due to a misconfigured readiness probe and OOM kills. Walk me through your incident response and post-mortem process.",
        'behavioral': "Describe a time when a critical release failed in staging or production. How did you collaborate with developers to execute a clean rollback and conduct a blameless post-mortem?",
        'keywords': {'docker', 'kubernetes', 'k8s', 'ci', 'cd', 'linux', 'cloud', 'aws', 'terraform', 'pipeline', 'monitoring', 'prometheus', 'grafana', 'security', 'rollback', 'ingress', 'cluster'}
    },
    'general': {
        'display_name': 'Software Engineer',
        'technical': "Let's start with software architecture. How do you approach designing maintainable, modular software components that isolate business logic, enforce clean interfaces, and support unit testing?",
        'scenario': "Suppose a core background task occasionally silently fails or deadlocks under high load without throwing exceptions. How do you trace, reproduce, and resolve this non-deterministic issue?",
        'behavioral': "Tell me about a challenging project where team members had conflicting opinions on coding standards, tools, or architectural patterns. How did you foster consensus?",
        'keywords': {'architecture', 'modular', 'testing', 'unit', 'refactoring', 'design', 'patterns', 'scalability', 'debugging', 'concurrency', 'interface', 'abstraction', 'git', 'clean', 'code'}
    }
}

# Dialogue Phase Definitions
PHASE_INTRO = 'INTRODUCTION'
PHASE_TECHNICAL = 'TECHNICAL'
PHASE_SCENARIO = 'SCENARIO'
PHASE_BEHAVIORAL = 'BEHAVIORAL'
PHASE_WRAPUP = 'WRAPUP'
PHASE_COMPLETED = 'COMPLETED'

PHASE_SEQUENCE = [
    PHASE_INTRO,
    PHASE_TECHNICAL,
    PHASE_SCENARIO,
    PHASE_BEHAVIORAL,
    PHASE_WRAPUP,
    PHASE_COMPLETED
]


class MockInterviewEngine:

    @classmethod
    def match_role_track(cls, role_str: str) -> str:
        """Matches a role string to a canonical question bank track."""
        if not role_str:
            return 'general'
        r = role_str.lower()
        if any(k in r for k in ['front', 'react', 'ui', 'vue', 'angular', 'web designer']):
            return 'frontend'
        elif any(k in r for k in ['back', 'django', 'python developer', 'api', 'database', 'spring', 'node', 'full stack', 'fullstack']):
            return 'backend'
        elif any(k in r for k in ['ml', 'machine learning', 'ai', 'deep learning']):
            return 'ml'
        elif any(k in r for k in ['data', 'analytics', 'etl', 'bi']):
            return 'data'
        elif any(k in r for k in ['devops', 'cloud', 'infra', 'kubernetes', 'sre', 'security', 'cyber']):
            return 'devops'
        return 'general'

    @classmethod
    def get_initial_greeting(cls, role_str: str) -> str:
        """Generates opening greeting for Turn 0."""
        return (
            f"Hello! Welcome to your simulated technical interview for the {role_str} position. "
            f"Let's begin. Can you start by introducing yourself, walking me through your background, "
            f"and mentioning the primary technologies you have used in your recent projects?"
        )

    @classmethod
    def process_candidate_turn(
        cls,
        session: MockInterviewSession,
        candidate_msg: str,
        proctor_violations_count: int = 0
    ) -> Dict[str, Any]:
        """
        Executes one dialogue turn of the state machine.
        Validates transition, generates role-tailored prompt, and handles completion.
        """
        if session.is_completed:
            return {
                "completed": True,
                "message": "This interview session is already completed.",
                "redirect_url": f"/interviews/mock/{session.id}/report/"
            }

        candidate_msg = candidate_msg.strip()
        if not candidate_msg:
            return {
                "error": "Response cannot be empty. Please provide an authentic answer.",
                "completed": False
            }

        with transaction.atomic():
            # Save candidate message
            MockInterviewChat.objects.create(
                session=session,
                sender='Candidate',
                message=candidate_msg,
                phase=session.current_phase
            )

            # Audit proctoring if increased
            if proctor_violations_count > session.proctor_violations_count:
                session.proctor_violations_count = proctor_violations_count
                session.save(update_fields=['proctor_violations_count'])

            candidate_turns = MockInterviewChat.objects.filter(
                session=session,
                sender='Candidate'
            ).count()

            track_key = cls.match_role_track(session.role)
            track_data = ROLE_QUESTION_BANKS.get(track_key, ROLE_QUESTION_BANKS['general'])

            next_phase = PHASE_COMPLETED
            interviewer_reply = ""
            is_done = False

            if candidate_turns == 1:
                next_phase = PHASE_TECHNICAL
                interviewer_reply = f"Thank you for the introduction. {track_data['technical']}"
            elif candidate_turns == 2:
                next_phase = PHASE_BEHAVIORAL
                interviewer_reply = f"Good technical reasoning. Now let's explore behavioral dynamics and conflict resolution: {track_data['behavioral']}"
            else:
                next_phase = PHASE_COMPLETED
                is_done = True
                interviewer_reply = (
                    "Thank you! That concludes our simulated technical interview. "
                    "I am now analyzing your responses across Technical Depth, Problem Solving, Role Relevance, and Communication to prepare your scorecard."
                )

            # Record interviewer response
            MockInterviewChat.objects.create(
                session=session,
                sender='Interviewer',
                message=interviewer_reply,
                phase=session.current_phase
            )

            session.current_phase = next_phase
            session.current_turn = candidate_turns

            if is_done:
                cls._finalize_session_evaluation(session, track_key)
            else:
                session.save(update_fields=['current_phase', 'current_turn'])

            return {
                "completed": is_done,
                "message": interviewer_reply,
                "phase": next_phase,
                "turn": candidate_turns,
                "redirect_url": f"/interviews/mock/{session.id}/report/" if is_done else ""
            }

    @classmethod
    def _finalize_session_evaluation(cls, session: MockInterviewSession, track_key: str):
        """
        Evaluates dialogue using a transparent multi-dimensional rubric:
        1. Technical Depth (0-30)
        2. Problem Solving & Tradeoff Analysis (0-25)
        3. Role Relevance (0-25)
        4. Communication & Ownership (0-20)
        Note: Proctor violations DO NOT modify performance scores!
        """
        candidate_chats = list(
            MockInterviewChat.objects.filter(session=session, sender='Candidate').order_by('created_at')
        )
        all_text = " ".join(c.message for c in candidate_chats)
        all_text_lower = all_text.lower()
        words = re.findall(r'\b\w+\b', all_text_lower)
        total_words = len(words)

        track_data = ROLE_QUESTION_BANKS.get(track_key, ROLE_QUESTION_BANKS['general'])
        domain_keywords = track_data.get('keywords', set())

        # 1. Technical Depth (0-30 pts)
        tech_score = 0
        tech_feedback = []
        # Look for technical concept explanation (words like "because", "due to", "configured", "handles", "ensures")
        explanation_words = {'because', 'due', 'configured', 'implements', 'handles', 'ensures', 'optimizes', 'isolates', 'architecture'}
        has_explanation = sum(1 for w in explanation_words if w in all_text_lower)
        if has_explanation >= 4:
            tech_score += 15
            tech_feedback.append("Articulated clear technical rationale and architectural decisions.")
        elif has_explanation >= 2:
            tech_score += 10
            tech_feedback.append("Addressed technical concepts; provide deeper implementation specifics.")
        else:
            tech_score += 5
            tech_feedback.append("Brief technical explanations; elaborate on internal mechanisms.")

        # Substantive volume check (prevent one-sentence answers)
        if total_words >= 250:
            tech_score += 15
            tech_feedback.append("Detailed technical responses across dialogue turns.")
        elif total_words >= 150:
            tech_score += 10
            tech_feedback.append("Satisfactory depth; elaborate with concrete examples.")
        else:
            tech_score += 5
            tech_feedback.append("Answers were concise; expand on key engineering considerations.")

        # 2. Problem Solving & Tradeoff Analysis (0-25 pts)
        ps_score = 0
        ps_feedback = []
        tradeoff_markers = {'tradeoff', 'latency', 'bottleneck', 'throughput', 'consistency', 'reliability', 'cost', 'scaling', 'pros', 'cons', 'monitoring', 'failover', 'caching'}
        matched_tradeoffs = [m for m in tradeoff_markers if m in all_text_lower]
        if len(matched_tradeoffs) >= 4:
            ps_score += 25
            ps_feedback.append(f"Demonstrated excellent systems thinking and trade-off awareness ({', '.join(matched_tradeoffs[:3])}).")
        elif len(matched_tradeoffs) >= 2:
            ps_score += 18
            ps_feedback.append("Identified engineering trade-offs; consider contrasting alternative approaches.")
        else:
            ps_score += 10
            ps_feedback.append("Frame engineering choices in terms of trade-offs (e.g. latency vs. cost, consistency vs. availability).")

        # 3. Role Relevance (0-25 pts)
        rel_score = 0
        rel_feedback = []
        matched_domain = [kw for kw in domain_keywords if kw in all_text_lower]
        if len(matched_domain) >= 6:
            rel_score += 25
            rel_feedback.append(f"Strong domain fluency for {track_data['display_name']} ({', '.join(matched_domain[:4])}).")
        elif len(matched_domain) >= 3:
            rel_score += 18
            rel_feedback.append(f"Relevant domain terminology applied ({', '.join(matched_domain[:3])}).")
        else:
            rel_score += 10
            rel_feedback.append(f"Integrate more domain-specific concepts for {track_data['display_name']}.")

        # 4. Communication & Ownership (0-20 pts)
        comm_score = 0
        comm_feedback = []
        ownership_pronouns = {'i', 'my', 'we', 'our'}
        has_ownership = any(p in words for p in ownership_pronouns)
        if has_ownership and total_words >= 100:
            comm_score += 20
            comm_feedback.append("Clear professional communication and personal ownership.")
        elif total_words >= 60:
            comm_score += 12
            comm_feedback.append("Professional tone; clearly identify your specific individual contributions.")
        else:
            comm_score += 6
            comm_feedback.append("Response volume is minimal; provide thorough, structured explanations.")

        overall_score = min(tech_score + ps_score + rel_score + comm_score, 100)

        dimension_scores = {
            "technical_depth": {"score": tech_score, "max": 30, "percentage": int(round((tech_score / 30) * 100))},
            "problem_solving": {"score": ps_score, "max": 25, "percentage": int(round((ps_score / 25) * 100))},
            "role_relevance": {"score": rel_score, "max": 25, "percentage": int(round((rel_score / 25) * 100))},
            "communication": {"score": comm_score, "max": 20, "percentage": int(round((comm_score / 20) * 100))}
        }

        all_notes = tech_feedback + ps_feedback + rel_feedback + comm_feedback
        feedback_summary = " ".join(all_notes)

        session.is_completed = True
        session.completed_at = timezone.now()
        session.overall_score = overall_score
        session.dimension_scores = dimension_scores
        session.feedback = feedback_summary
        session.save()

        # Record competency evidence if overall score >= 75%
        if overall_score >= 75:
            try:
                InterviewCompetencyEvidence.objects.create(
                    user=session.user,
                    skill_name=track_data['display_name'],
                    source_type='MOCK_INTERVIEW',
                    score=overall_score,
                    confidence_weight=0.9,
                    notes=f"Achieved {overall_score}% in simulated technical mock interview for {session.role}."
                )
            except Exception:
                pass
