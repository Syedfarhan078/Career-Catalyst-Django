from django.core.management.base import BaseCommand
from apps.interviews.models import QuestionCategory, Question

class Command(BaseCommand):
    help = "Seeds the database with high-quality Aptitude, Technical MCQ, Coding, and HR/Behavioral questions."

    def handle(self, *args, **options):
        # Create categories
        categories = {
            "aptitude": {
                "name": "Aptitude Practice",
                "desc": "Quizzes covering quantitative reasoning, verbal aptitude, and logical problem solving."
            },
            "technical": {
                "name": "Technical MCQ",
                "desc": "Multiple choice questions on DSA, programming languages, databases, and system design."
            },
            "coding": {
                "name": "Coding Challenges",
                "desc": "Interactive coding workspace to write and test Python algorithms locally."
            },
            "behavioral": {
                "name": "HR & Behavioral",
                "desc": "Practice behavioral interviews structured using the STAR method (Situation, Task, Action, Result)."
            }
        }

        seeded_categories = {}
        for key, data in categories.items():
            category, created = QuestionCategory.objects.get_or_create(
                slug=key,
                defaults={"name": data["name"], "description": data["desc"]}
            )
            seeded_categories[key] = category
            if created:
                self.stdout.write(f"Created category: {category.name}")

        # Seed Aptitude Questions
        apt_questions = [
            {
                "title": "Train and Pole Length",
                "content": "A train running at the speed of 60 km/hr crosses a pole in 9 seconds. What is the length of the train?",
                "difficulty": "Easy",
                "options": ["120 metres", "150 metres", "324 metres", "180 metres"],
                "correct_option": "B"
            },
            {
                "title": "Compound Interest",
                "content": "Find the compound interest on Rs. 10,000 for 2 years at 10% per annum, compounded annually.",
                "difficulty": "Medium",
                "options": ["Rs. 2,000", "Rs. 2,100", "Rs. 2,200", "Rs. 2,500"],
                "correct_option": "B"
            },
            {
                "title": "Work and Time",
                "content": "A can do a work in 15 days and B in 20 days. If they work on it together for 4 days, then the fraction of the work that is left is:",
                "difficulty": "Medium",
                "options": ["1/4", "1/10", "7/15", "8/15"],
                "correct_option": "D"
            },
            {
                "title": "Logical Sequences",
                "content": "Look at this series: 2, 1, (1/2), (1/4), ... What number should come next?",
                "difficulty": "Easy",
                "options": ["1/3", "1/8", "2/8", "1/16"],
                "correct_option": "B"
            },
            {
                "title": "Clock Angles",
                "content": "An accurate clock shows 8 o'clock in the morning. Through how many degrees will the hour hand rotate when the clock shows 2 o'clock in the afternoon?",
                "difficulty": "Hard",
                "options": ["144 degrees", "150 degrees", "168 degrees", "180 degrees"],
                "correct_option": "D"
            }
        ]

        for idx, q in enumerate(apt_questions):
            Question.objects.get_or_create(
                category=seeded_categories["aptitude"],
                title=q["title"],
                defaults={
                    "content": q["content"],
                    "question_type": "MCQ",
                    "difficulty": q["difficulty"],
                    "options": q["options"],
                    "correct_option": q["correct_option"]
                }
            )

        # Seed Technical MCQs
        tech_questions = [
            {
                "title": "Database Isolation Levels",
                "content": "Which of the following database isolation levels prevents all types of read concurrency anomalies (dirty read, non-repeatable read, phantom read)?",
                "difficulty": "Medium",
                "options": ["Read Committed", "Read Uncommitted", "Repeatable Read", "Serializable"],
                "correct_option": "D"
            },
            {
                "title": "Python Memory Management",
                "content": "How does Python handle garbage collection for cyclic references?",
                "difficulty": "Hard",
                "options": [
                    "Reference counting alone is sufficient",
                    "It relies strictly on manual memory deallocation",
                    "It uses a cyclic garbage collector using a tri-color marking algorithm periodically",
                    "Through JVM-style mark-and-sweep only"
                ],
                "correct_option": "C"
            },
            {
                "title": "Django QuerySet Evaluation",
                "content": "Which of the following actions does NOT trigger evaluation of a Django QuerySet?",
                "difficulty": "Medium",
                "options": [
                    "Iterating over the QuerySet (e.g. for obj in queryset)",
                    "Calling filter() or exclude() on the QuerySet",
                    "Calling len() on the QuerySet",
                    "Slicing the QuerySet with a step parameter (e.g. queryset[0:10:2])"
                ],
                "correct_option": "B"
            },
            {
                "title": "Time Complexity of Binary Search",
                "content": "What is the worst-case time complexity of searching an element in a balanced binary search tree (BST) of size N?",
                "difficulty": "Easy",
                "options": ["O(1)", "O(log N)", "O(N)", "O(N log N)"],
                "correct_option": "B"
            },
            {
                "title": "REST HTTP Methods",
                "content": "Which of the following HTTP methods is NOT idempotent?",
                "difficulty": "Easy",
                "options": ["GET", "PUT", "DELETE", "POST"],
                "correct_option": "D"
            }
        ]

        for idx, q in enumerate(tech_questions):
            Question.objects.get_or_create(
                category=seeded_categories["technical"],
                title=q["title"],
                defaults={
                    "content": q["content"],
                    "question_type": "MCQ",
                    "difficulty": q["difficulty"],
                    "options": q["options"],
                    "correct_option": q["correct_option"]
                }
            )

        # Seed Coding Challenges
        coding_questions = [
            {
                "title": "Two Sum",
                "content": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice. You can return the answer in any order.\n\n### Example:\n```python\nInput: nums = [2,7,11,15], target = 9\nOutput: [0,1]\nExplanation: Because nums[0] + nums[1] == 9, we return [0, 1].\n```\n\n### Complete the function:\n```python\ndef two_sum(nums, target):\n    # Write your code here\n    pass\n```",
                "difficulty": "Easy",
                "test_cases": [
                    {"input": "[2, 7, 11, 15], 9", "expected": "[0, 1]", "function": "two_sum"},
                    {"input": "[3, 2, 4], 6", "expected": "[1, 2]", "function": "two_sum"},
                    {"input": "[3, 3], 6", "expected": "[0, 1]", "function": "two_sum"}
                ],
                "solution": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []"
            },
            {
                "title": "Integer Factorial",
                "content": "Implement a function `factorial(n)` that returns the factorial of a non-negative integer `n`.\n\nFactorial of `n` is `1 * 2 * ... * n` (with `factorial(0) = 1`).\n\n### Example:\n```python\nInput: 5\nOutput: 120\n```\n\n### Complete the function:\n```python\ndef factorial(n):\n    # Write your code here\n    pass\n```",
                "difficulty": "Easy",
                "test_cases": [
                    {"input": "0", "expected": "1", "function": "factorial"},
                    {"input": "1", "expected": "1", "function": "factorial"},
                    {"input": "5", "expected": "120", "function": "factorial"},
                    {"input": "8", "expected": "40320", "function": "factorial"}
                ],
                "solution": "def factorial(n):\n    if n <= 1:\n        return 1\n    res = 1\n    for i in range(2, n + 1):\n        res *= i\n    return res"
            },
            {
                "title": "Valid Palindrome",
                "content": "Given a string `s`, return `True` if it is a palindrome, and `False` otherwise.\n\nA string is a palindrome if it reads the same forward and backward after removing all non-alphanumeric characters and converting it to lowercase.\n\n### Example:\n```python\nInput: \"A man, a plan, a canal: Panama\"\nOutput: True\n```\n\n### Complete the function:\n```python\ndef is_palindrome(s):\n    # Write your code here\n    pass\n```",
                "difficulty": "Medium",
                "test_cases": [
                    {"input": "'A man, a plan, a canal: Panama'", "expected": "true", "function": "is_palindrome"},
                    {"input": "'race a car'", "expected": "false", "function": "is_palindrome"},
                    {"input": "' '", "expected": "true", "function": "is_palindrome"}
                ],
                "solution": "def is_palindrome(s):\n    cleaned = ''.join(c.lower() for c in s if c.isalnum())\n    return cleaned == cleaned[::-1]"
            }
        ]

        for q in coding_questions:
            Question.objects.get_or_create(
                category=seeded_categories["coding"],
                title=q["title"],
                defaults={
                    "content": q["content"],
                    "question_type": "Coding",
                    "difficulty": q["difficulty"],
                    "test_cases": q["test_cases"],
                    "sample_solution": q["solution"]
                }
            )

        # Seed HR/Behavioral questions
        behavioral_questions = [
            {
                "title": "Tell Me About Yourself",
                "content": "Walk me through your background. Introduce your technical interests, notable academic projects, and professional goals.",
                "difficulty": "Easy",
                "solution": "Structure: Present (Current semester/college/degree) -> Past (Key achievements, project accomplishments, internships) -> Future (Interest in target role/technology)."
            },
            {
                "title": "Handling Team Conflicts",
                "content": "Describe a situation where you had a disagreement with a team member during a project. How did you handle it, and what was the outcome?",
                "difficulty": "Medium",
                "solution": "Use the STAR method: Situation (What project/conflict), Task (What role/challenge needed resolution), Action (What communication/empathy steps you took), Result (How you solved it and what you learned)."
            },
            {
                "title": "Navigating Technical Failures",
                "content": "Tell me about a time a project did not go according to plan due to a technical hurdle or failure. What did you do, and how did you pivot?",
                "difficulty": "Hard",
                "solution": "Use the STAR method: detail technical diagnosis, cross-collaboration, root-cause analysis, and preventative setups implemented."
            }
        ]

        for q in behavioral_questions:
            Question.objects.get_or_create(
                category=seeded_categories["behavioral"],
                title=q["title"],
                defaults={
                    "content": q["content"],
                    "question_type": "STAR",
                    "difficulty": q["difficulty"],
                    "sample_solution": q["solution"]
                }
            )

        self.stdout.write(self.style.SUCCESS("Interviews database seeding completed!"))
