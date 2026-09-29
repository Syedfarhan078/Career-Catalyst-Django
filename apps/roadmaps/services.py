"""
Roadmap-to-Skills Synchronization Services.

Provides deterministic derivation of roadmap-earned skills from
Topic.skills_taught and completed TopicProgress.
"""
from typing import List, Set, Dict, Any
from apps.roadmaps.models import Topic, TopicProgress


def get_topic_skills(topic: Topic) -> List[str]:
    """
    Extracts and normalizes skills taught by a Topic.
    
    Requirements:
    - Sourced strictly from topic.skills_taught.
    - Strips whitespace.
    - Filters empty tokens.
    - Deduplicates case-insensitively while preserving canonical display casing.
    - If skills_taught is empty, returns empty list []. No title-guessing fallback.
    """
    if not topic or not getattr(topic, 'skills_taught', None):
        return []

    raw_skills = topic.skills_taught.split(',')
    unique_skills: List[str] = []
    seen_lower: Set[str] = set()

    for s in raw_skills:
        clean = s.strip()
        if not clean:
            continue
        lower_key = clean.lower()
        if lower_key not in seen_lower:
            seen_lower.add(lower_key)
            unique_skills.append(clean)

    return unique_skills


def get_user_earned_skills_set(user) -> Set[str]:
    """
    Queries all completed TopicProgress records across all roadmaps for the user
    and aggregates their authoritative skills_taught.

    Returns a normalized, deduplicated set of skill names.
    Note: Represents ROADMAP-EARNED skills only; does NOT touch StudentProfile.skills.
    """
    if not user or not user.is_authenticated:
        return set()

    completed_progresses = TopicProgress.objects.filter(
        user_roadmap__user=user,
        is_completed=True
    ).select_related('topic')

    earned_skills: Set[str] = set()
    for progress in completed_progresses:
        for skill in get_topic_skills(progress.topic):
            earned_skills.add(skill)

    return earned_skills


def sync_topic_completion(user, topic: Topic, is_completed: bool) -> Dict[str, Any]:
    """
    Maintains idempotent roadmap completion synchronization.
    
    When is_completed=True:
      Determines which skills taught by this topic are newly earned
      (i.e., not already provided by another completed topic for this user).

    When is_completed=False:
      Determines which skills taught by this topic are now lost
      (i.e., no other completed topic for this user provides them).

    Returns a dict with:
      - 'newly_earned_skills': list of newly earned skills (if completed)
      - 'lost_skills': list of lost skills (if uncompleted)
      - 'all_earned_skills': full set/list of user's current roadmap-earned skills
    """
    topic_skills = get_topic_skills(topic)

    # Fetch other completed topic progress records for this user (excluding this topic)
    other_completed_qs = TopicProgress.objects.filter(
        user_roadmap__user=user,
        is_completed=True
    ).exclude(topic=topic).select_related('topic')

    other_skills_map: Dict[str, str] = {}
    for progress in other_completed_qs:
        for s in get_topic_skills(progress.topic):
            other_skills_map[s.lower()] = s

    if is_completed:
        newly_earned = [
            s for s in topic_skills 
            if s.lower() not in other_skills_map
        ]
        # Current total earned skills including this topic
        all_earned = set(other_skills_map.values()) | set(topic_skills)
        return {
            "is_completed": True,
            "newly_earned_skills": newly_earned,
            "lost_skills": [],
            "all_earned_skills": sorted(list(all_earned))
        }
    else:
        lost = [
            s for s in topic_skills 
            if s.lower() not in other_skills_map
        ]
        all_earned = set(other_skills_map.values())
        return {
            "is_completed": False,
            "newly_earned_skills": [],
            "lost_skills": lost,
            "all_earned_skills": sorted(list(all_earned))
        }
