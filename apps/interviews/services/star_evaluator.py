"""
STAR Behavioral Evaluator Service for CareerCatalyst.

Provides deterministic, explainable rubric evaluation of candidate responses structured
under the STAR methodology (Situation, Task, Action, Result).
Guards against low-entropy gaming and validates structural components, ownership, and measurable impact.
"""

import re
from typing import Any, Dict, List, Tuple

# Action verbs denoting strong technical or organizational ownership
ACTION_VERBS = {
    'designed', 'developed', 'implemented', 'refactored', 'debugged',
    'orchestrated', 'coordinated', 'analyzed', 'automated', 'created',
    'configured', 'built', 'investigated', 'optimized', 'scheduled',
    'tested', 'deployed', 'migrated', 'architected', 'resolved',
    'established', 'integrated', 'streamlined', 'monitored', 'led',
    'managed', 'engineered', 'authored', 'spearheaded', 'executed'
}

# Ownership pronouns demonstrating personal contribution
OWNERSHIP_PRONOUNS = {'i', 'my', 'me', 'myself', 'we', 'our'}

# Metric / outcome indicators
RESULT_METRIC_PATTERNS = [
    r'\b\d+%\b',                       # e.g. 40%
    r'\b\d+\s*(percent|percentage)\b', # e.g. 30 percent
    r'\b\d+\s*(x|fold)\b',             # e.g. 2x, 10-fold
    r'\b\d+\s*(days|weeks|months|hours|minutes|seconds|ms)\b', # e.g. 3 days, 200 ms
    r'\b\d+\b',                        # Any numeric quantifier
    r'\b(increased|reduced|decreased|improved|accelerated|saved|boosted|doubled|tripled|eliminated|prevented)\b'
]


class STAREvaluatorService:

    @classmethod
    def is_gamed_or_low_entropy(cls, text: str) -> Tuple[bool, str]:
        """
        Detects repetitive gibberish, single-character spam, or low-entropy gaming attempts.
        Returns (is_gamed, reason).
        """
        clean = text.strip()
        if not clean:
            return True, "Section is empty."

        if len(clean) < 15:
            return True, "Response is too short to provide meaningful context."

        # Check for single character spam: "aaaaaaaaaaaaaaaa"
        char_counts = {}
        for c in clean.lower():
            if c.isalnum():
                char_counts[c] = char_counts.get(c, 0) + 1
        total_alnum = sum(char_counts.values())
        if total_alnum > 0:
            max_char_freq = max(char_counts.values()) / total_alnum
            if max_char_freq > 0.40 and total_alnum > 20:
                return True, "Response contains excessive repeated characters."

        # Check token diversity: "project project project project"
        words = re.findall(r'\b\w+\b', clean.lower())
        if len(words) >= 6:
            unique_words = set(words)
            diversity_ratio = len(unique_words) / len(words)
            if diversity_ratio < 0.35:
                return True, "Response lacks vocabulary diversity (repeated words detected)."

        return False, ""

    @classmethod
    def evaluate_situation(cls, text: str) -> Dict[str, Any]:
        """Evaluates Situation block (0-25 pts)."""
        score = 0
        feedback = []
        is_gamed, reason = cls.is_gamed_or_low_entropy(text)
        if is_gamed:
            return {"score": 0, "feedback": [reason]}

        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)

        # Baseline volume & context
        if word_count >= 12:
            score += 15
            feedback.append("Thorough context and background established.")
        elif word_count >= 6:
            score += 8
            feedback.append("Context is clear, but consider adding project stakes or background details.")
        else:
            score += 4
            feedback.append("Brief situation context; expand on the team or company environment.")

        # Contextual framing markers
        context_markers = {'when', 'during', 'project', 'team', 'company', 'client', 'system', 'production', 'deadline', 'issue', 'problem', 'challenge'}
        matched_markers = sum(1 for m in context_markers if m in text.lower())
        if matched_markers >= 2:
            score += 10
            feedback.append("Good framing of the business or technical scenario.")
        elif matched_markers == 1:
            score += 6
            feedback.append("Framing is present; highlight the specific challenge or constraint.")
        else:
            feedback.append("Clarify the specific obstacle or timeframe in the situation.")

        return {"score": min(score, 25), "feedback": feedback}

    @classmethod
    def evaluate_task(cls, text: str) -> Dict[str, Any]:
        """Evaluates Task block (0-25 pts)."""
        score = 0
        feedback = []
        is_gamed, reason = cls.is_gamed_or_low_entropy(text)
        if is_gamed:
            return {"score": 0, "feedback": [reason]}

        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)

        if word_count >= 10:
            score += 15
            feedback.append("Clear assignment and objective definition.")
        elif word_count >= 6:
            score += 8
            feedback.append("Deliverable is stated; articulate your personal ownership scope.")
        else:
            score += 4
            feedback.append("Task definition is brief; define your expected responsibility.")

        # Goal and responsibility markers
        task_markers = {'my', 'responsible', 'assigned', 'goal', 'deliverable', 'objective', 'task', 'needed', 'required', 'role'}
        has_task_marker = any(m in text.lower() for m in task_markers)
        if has_task_marker:
            score += 10
            feedback.append("Explicitly clarifies candidate role and targets.")
        else:
            feedback.append("Specify what you were directly held accountable for delivering.")

        return {"score": min(score, 25), "feedback": feedback}

    @classmethod
    def evaluate_action(cls, text: str) -> Dict[str, Any]:
        """Evaluates Action block (0-25 pts)."""
        score = 0
        feedback = []
        is_gamed, reason = cls.is_gamed_or_low_entropy(text)
        if is_gamed:
            return {"score": 0, "feedback": [reason]}

        words = [w.lower() for w in re.findall(r'\b\w+\b', text)]
        word_count = len(words)

        if word_count >= 10:
            score += 10
            feedback.append("Procedural description of steps taken.")
        elif word_count >= 6:
            score += 6
            feedback.append("Steps are outlined; include specific technical or interpersonal details.")
        else:
            score += 3
            feedback.append("Expand on the concrete methods you utilized.")

        # Check for first-person ownership pronouns
        has_ownership = any(p in words for p in OWNERSHIP_PRONOUNS)
        if has_ownership:
            score += 5
            feedback.append("Demonstration of personal accountability and agency.")
        else:
            feedback.append("Use first-person language ('I implemented', 'I led') to emphasize your actions.")

        # Check for action verbs
        matched_verbs = [v for v in ACTION_VERBS if v in words]
        if len(matched_verbs) >= 2:
            score += 10
            feedback.append(f"Excellent proactive action verbs: {', '.join(matched_verbs[:3])}.")
        elif len(matched_verbs) == 1:
            score += 6
            feedback.append(f"Good action orientation ({matched_verbs[0]}); add further implementation steps.")
        else:
            feedback.append("Incorporate decisive action verbs (e.g. 'architected', 'resolved', 'automated').")

        return {"score": min(score, 25), "feedback": feedback}

    @classmethod
    def evaluate_result(cls, text: str) -> Dict[str, Any]:
        """Evaluates Result block (0-25 pts)."""
        score = 0
        feedback = []
        is_gamed, reason = cls.is_gamed_or_low_entropy(text)
        if is_gamed:
            return {"score": 0, "feedback": [reason]}

        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)

        if word_count >= 10:
            score += 10
            feedback.append("Clear outcome narrative provided.")
        elif word_count >= 6:
            score += 6
            feedback.append("Outcome is mentioned; elaborate on business impact.")
        else:
            score += 3
            feedback.append("Result is very brief; explain how the project concluded.")

        # Metric & impact verification
        metric_matches = []
        for pattern in RESULT_METRIC_PATTERNS:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                metric_matches.extend(found)

        if len(metric_matches) >= 1:
            score += 15
            feedback.append("Measurable evidence and quantitative impact demonstrated.")
        else:
            feedback.append("Quantify results with measurable outcomes (e.g., 'reduced latency by 35%', 'saved 10 hours').")

        return {"score": min(score, 25), "feedback": feedback}

    @classmethod
    def evaluate(cls, situation: str, task: str, action: str, result: str) -> Dict[str, Any]:
        """
        Evaluates full STAR response and returns a structured scorecard.
        """
        sit_res = cls.evaluate_situation(situation)
        task_res = cls.evaluate_task(task)
        act_res = cls.evaluate_action(action)
        res_res = cls.evaluate_result(result)

        total_score = sit_res["score"] + task_res["score"] + act_res["score"] + res_res["score"]

        overall_feedback = []
        if total_score >= 85:
            overall_feedback.append("Exceptional response adhering thoroughly to the STAR methodology with strong agency and metrics.")
        elif total_score >= 70:
            overall_feedback.append("Solid behavioral answer with good structure. Review section feedback to add quantitative metrics and sharper action verbs.")
        elif total_score >= 50:
            overall_feedback.append("Competent foundation, but several sections require additional detail, clear personal agency, or measurable outcomes.")
        else:
            overall_feedback.append("Incomplete or insufficient answer. Ensure every block contains substantive details, first-person actions, and concrete outcomes.")

        return {
            "score": total_score,
            "sections": {
                "situation": sit_res,
                "task": task_res,
                "action": act_res,
                "result": res_res
            },
            "overall_feedback": overall_feedback
        }
