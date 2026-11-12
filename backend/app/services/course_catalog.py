"""Small, authored in-app starter curriculum; not external course listings."""
from copy import deepcopy

COURSES = [
    {
        "id": "fraction-foundations",
        "title": "Fraction Foundations",
        "description": "Build confidence with equivalent fractions, unlike denominators, and fractions of quantities.",
        "provider": "BHASHALEARN AI",
        "content_type": "in_app",
        "language": "mixed",
        "level": "Beginner",
        "estimated_minutes": 40,
        "prerequisites": [],
        "skills": ["Equivalent fractions", "Addition", "Reasoning with quantities"],
        "lessons": [
            {"id": "equivalent-fractions", "title": "Equivalent fractions", "estimated_minutes": 12, "objective": "Explain why multiplying the numerator and denominator by the same non-zero number preserves value.", "content_en": "An equivalent fraction names the same amount in a different way. For example, 1/2 = 2/4 because the numerator and denominator are both multiplied by 2. The whole is split into more pieces, but the shaded share stays the same.", "content_te": "సమాన భిన్నం అదే పరిమాణాన్ని మరో రూపంలో చూపిస్తుంది. ఉదాహరణకు, లవం మరియు హారాన్ని 2తో గుణిస్తే 1/2 = 2/4. ముక్కలు ఎక్కువైనా, మొత్తం లోని భాగం మారదు.", "quiz_topic": "equivalent fractions"},
            {"id": "add-unlike-denominators", "title": "Add unlike denominators", "estimated_minutes": 15, "objective": "Rewrite fractions with a common denominator before adding.", "content_en": "To add 1/2 + 1/4, first use fourths: 1/2 = 2/4. Then add the numerators: 2/4 + 1/4 = 3/4. Keep the shared denominator because the pieces are fourths.", "content_te": "1/2 + 1/4 కలపడానికి ముందుగా ఒకే హారం తీసుకోండి. 1/2 = 2/4. ఇప్పుడు లవాలను కలపండి: 2/4 + 1/4 = 3/4. ముక్కలు నాలుగో వంతులు కాబట్టి హారం 4గానే ఉంటుంది.", "quiz_topic": "equivalent fractions"},
            {"id": "fraction-of-quantity", "title": "Find a fraction of a quantity", "estimated_minutes": 13, "objective": "Find a fraction of a whole number by dividing, then multiplying.", "content_en": "To find 3/4 of 20, divide 20 into 4 equal groups: 20 ÷ 4 = 5. Take 3 groups: 5 × 3 = 15. So 3/4 of 20 is 15.", "content_te": "20లో 3/4 కనుక్కోవడానికి, ముందుగా 20ను 4 సమాన భాగాలుగా విభజించండి: 20 ÷ 4 = 5. తర్వాత 3 భాగాలు తీసుకోండి: 5 × 3 = 15. కాబట్టి 20లో 3/4 = 15.", "quiz_topic": "equivalent fractions"},
        ],
    },
    {
        "id": "python-foundations",
        "title": "Python Foundations",
        "description": "Learn variables, decisions, and loops through short, runnable examples.",
        "provider": "BHASHALEARN AI",
        "content_type": "in_app",
        "language": "english",
        "level": "Beginner",
        "estimated_minutes": 45,
        "prerequisites": ["Basic computer use"],
        "skills": ["Variables", "Conditionals", "Loops"],
        "lessons": [
            {"id": "values-and-variables", "title": "Values and variables", "estimated_minutes": 15, "objective": "Store and inspect a value using a descriptive variable name.", "content_en": "A variable is a name bound to a value. Example: score = 8. print(score) displays 8. Python infers the value's type, so score is an integer here.", "content_te": "వేరియబుల్ అనేది ఒక విలువకు పెట్టే పేరు. ఉదాహరణ: score = 8. print(score) చేస్తే 8 కనిపిస్తుంది. ఇక్కడ score ఒక integer.", "quiz_topic": None},
            {"id": "make-decisions", "title": "Make decisions with if", "estimated_minutes": 15, "objective": "Use a condition to choose which block of code runs.", "content_en": "An if statement runs its indented block when a condition is true. Example: if score >= 5: print('keep going'). The comparison produces True or False.", "content_te": "షరతు True అయినప్పుడు if లోని ఇండెంట్ చేసిన కోడ్ నడుస్తుంది. ఉదాహరణ: if score >= 5: print('keep going'). పోలిక ఫలితం True లేదా False అవుతుంది.", "quiz_topic": None},
            {"id": "repeat-with-loops", "title": "Repeat work with loops", "estimated_minutes": 15, "objective": "Use a for loop to repeat an action for each item.", "content_en": "A for loop visits items one at a time. Example: for number in [1, 2, 3]: print(number). The indented print runs once for each list item.", "content_te": "for loop ఒక జాబితాలోని అంశాలను ఒక్కొక్కటిగా తీసుకుంటుంది. ఉదాహరణ: for number in [1, 2, 3]: print(number). ఇండెంట్ చేసిన print ప్రతి అంశానికి ఒకసారి నడుస్తుంది.", "quiz_topic": None},
        ],
    },
]


def all_courses():
    return deepcopy(COURSES)


def find_course(course_id: str):
    return next((deepcopy(course) for course in COURSES if course["id"] == course_id), None)
