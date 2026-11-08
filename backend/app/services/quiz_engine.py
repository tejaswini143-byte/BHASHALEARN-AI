"""Curated, bilingual assessment content and deterministic grading helpers.

The repository currently has no structured, curriculum-grounded quiz generation
provider. This catalog therefore reuses the existing objective bank and adds only
reviewable deterministic questions for its two supported topics.
"""
from dataclasses import dataclass
import re

from backend.app.services.assessment_bank import BANK
from backend.app.services.adaptive_learning import normalize_topic


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    topic: str
    question_type: str
    difficulty: str
    prompt_en: str
    prompt_te: str
    choices: tuple[tuple[str, str], ...]
    accepted: tuple[str, ...]
    explanation_en: str
    explanation_te: str
    source: str


def _choice_question(topic: str, question_id: str, difficulty: str, prompt: str,
                     options: tuple[str, ...], answer: str, explanation: str) -> QuizQuestion:
    telugu = {
        "fractions-01": ("1/2కు సమానమైన భిన్నం ఏది?", "1/2 యొక్క లవం, హారాన్ని 2తో గుణిస్తే 2/4 వస్తుంది."),
        "fractions-02": ("3/4కు సమానమైన భిన్నం ఏది?", "3, 4 రెండింటినీ 2తో గుణిస్తే 6/8 వస్తుంది."),
        "fractions-03": ("2/3కు సమానమైన భిన్నం ఏది?", "లవం, హారం రెండింటినీ 2తో గుణిస్తే 4/6 వస్తుంది."),
        "dijkstra-01": ("ఇచ్చిన గ్రాఫ్‌లో Aను సందర్శించిన తర్వాత, సందర్శించని నోడ్‌లలో అతి తక్కువ తాత్కాలిక దూరం ఉన్నది ఏది?", "A నుండి C దూరం 2; B దూరం 4. కాబట్టి ముందుగా Cను ఎంచుకోవాలి."),
        "dijkstra-02": ("ఇచ్చిన గ్రాఫ్‌లో Aను సందర్శించిన తర్వాత A నుండి B వరకు తాత్కాలిక దూరం ఎంత?", "A–B ప్రత్యక్ష edge బరువు 4."),
        "dijkstra-03": ("A నుండి Cకు వెళ్లిన తర్వాత, C ద్వారా Bకు మెరుగైన తాత్కాలిక దూరం ఎంత?", "A నుండి Cకు 2, C నుండి Bకు 1; మొత్తం దూరం 3."),
    }
    prompt_te, explanation_te = telugu.get(question_id, (prompt, explanation))
    return QuizQuestion(
        question_id, topic, "multiple_choice", difficulty, prompt, prompt_te,
        tuple((option, option) for option in options), (answer,), explanation,
        explanation_te, "curated",
    )


_fractions = tuple(
    _choice_question("equivalent fractions", item.id, ("beginner", "intermediate", "advanced")[index % 3],
                     item.prompt, item.options, item.answer, item.explanation)
    for index, item in enumerate(BANK["equivalent fractions"])
)
_dijkstra = tuple(
    _choice_question("dijkstra shortest path", item.id, ("beginner", "intermediate", "advanced")[index % 3],
                     item.prompt, item.options, item.answer, item.explanation)
    for index, item in enumerate(BANK["dijkstra shortest path"])
)

_EXTRA = (
    QuizQuestion("fractions-tf-01", "equivalent fractions", "true_false", "beginner",
                 "Multiplying the numerator and denominator by the same nonzero number makes an equivalent fraction.",
                 "లవం, హారాన్ని ఒకే సున్నా కాని సంఖ్యతో గుణిస్తే సమాన భిన్నం వస్తుంది. (True/False)",
                 (("True", "True / నిజం"), ("False", "False / తప్పు")), ("true",),
                 "The numerator and denominator scale together, preserving the value.",
                 "లవం, హారం రెండూ ఒకే నిష్పత్తిలో మారుతాయి కాబట్టి విలువ మారదు.", "deterministic_fallback"),
    QuizQuestion("fractions-blank-01", "equivalent fractions", "fill_blank", "intermediate",
                 "Multiply both parts of 1/2 by 3 to get ___.", "1/2 లోని లవం, హారాన్ని 3తో గుణిస్తే ___ వస్తుంది.",
                 (), ("3/6", "three sixths"), "1×3 / 2×3 = 3/6.", "1×3 / 2×3 = 3/6.", "deterministic_fallback"),
    QuizQuestion("fractions-short-01", "equivalent fractions", "short_answer", "advanced",
                 "Give one fraction equivalent to 2/5.", "2/5 కు సమానమైన ఒక భిన్నాన్ని రాయండి.",
                 (), ("4/10", "6/15", "8/20", "10/25"),
                 "Multiply the numerator and denominator by the same number; for example, 2/5 = 4/10.",
                 "లవం, హారాన్ని ఒకే సంఖ్యతో గుణించండి; ఉదాహరణకు 2/5 = 4/10.", "deterministic_fallback"),
    QuizQuestion("dijkstra-tf-01", "dijkstra shortest path", "true_false", "beginner",
                 "Dijkstra's algorithm repeatedly selects the unvisited node with the smallest tentative distance.",
                 "Dijkstra అల్గోరిథం అతి తక్కువ తాత్కాలిక దూరం ఉన్న సందర్శించని నోడ్‌ను ఎంచుకుంటుంది. (True/False)",
                 (("True", "True / నిజం"), ("False", "False / తప్పు")), ("true",),
                 "That greedy selection is the core step for nonnegative edge weights.",
                 "సున్నా లేదా ధనాత్మక edge weights కోసం ఇదే ప్రధాన ఎంపిక దశ.", "deterministic_fallback"),
    QuizQuestion("dijkstra-blank-01", "dijkstra shortest path", "fill_blank", "intermediate",
                 "In the built-in graph, the direct edge from A to B has weight ___.", "ఇచ్చిన గ్రాఫ్‌లో A నుండి B వరకు ప్రత్యక్ష edge బరువు ___.",
                 (), ("4",), "The built-in graph defines the A–B edge with weight 4.",
                 "ఇచ్చిన గ్రాఫ్‌లో A–B edge బరువు 4.", "deterministic_fallback"),
    QuizQuestion("dijkstra-short-01", "dijkstra shortest path", "short_answer", "advanced",
                 "What is the improved distance from A to B through C? Give the number.",
                 "C ద్వారా A నుండి B వరకు మెరుగైన దూరం ఎంత? సంఖ్యను రాయండి.", (), ("3",),
                 "A to C costs 2 and C to B costs 1, so the path total is 3.",
                 "A నుండి C వరకు 2, C నుండి B వరకు 1; మొత్తం 3.", "deterministic_fallback"),
)

CATALOG = {
    "equivalent fractions": _fractions + tuple(item for item in _EXTRA if item.topic == "equivalent fractions"),
    "dijkstra shortest path": _dijkstra + tuple(item for item in _EXTRA if item.topic == "dijkstra shortest path"),
}
SUBJECTS = {"equivalent fractions": "Mathematics", "dijkstra shortest path": "Computer Science"}


def available_questions(topic: str, difficulty: str | None = None) -> tuple[QuizQuestion, ...]:
    key = normalize_topic(topic)
    questions = CATALOG.get(key, ())
    if difficulty:
        questions = tuple(item for item in questions if item.difficulty == difficulty)
    return questions


def normalize_answer(value: str) -> str:
    normalized = value.strip().casefold().replace("−", "-")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def answer_is_valid(question: QuizQuestion, answer: str) -> bool:
    if question.question_type == "multiple_choice":
        return any(normalize_answer(answer) == normalize_answer(en) or normalize_answer(answer) == normalize_answer(te)
                   for en, te in question.choices)
    if question.question_type == "true_false":
        return normalize_answer(answer) in {"true", "false", "true/నిజం", "false/తప్పు", "నిజం", "తప్పు"}
    return True


def grade_answer(question: QuizQuestion, answer: str) -> bool:
    normalized = normalize_answer(answer)
    accepted = {normalize_answer(value) for value in question.accepted}
    if question.question_type == "true_false":
        aliases = {"true": "true", "true/నిజం": "true", "నిజం": "true",
                   "false": "false", "false/తప్పు": "false", "తప్పు": "false"}
        return aliases.get(normalized, normalized) in accepted
    return normalized in accepted


def localized(question: QuizQuestion, language: str) -> tuple[str, list[str], str]:
    prompt = question.prompt_te if language == "telugu" else question.prompt_en
    if language == "mixed":
        prompt = f"{question.prompt_en}\n{question.prompt_te}"
    if question.question_type == "true_false":
        options = [te if language != "english" else en for en, te in question.choices]
    else:
        options = [te if language != "english" else en for en, te in question.choices]
    explanation = question.explanation_te if language == "telugu" else question.explanation_en
    if language == "mixed":
        explanation = f"{question.explanation_en}\n{question.explanation_te}"
    return prompt, options, explanation


def localized_recommendation(strategy: str, recommendation: str, language: str) -> str:
    translations = {
        "diagnostic_practice": "చిన్న నిర్ధారణ ప్రశ్నతో ప్రారంభించండి.",
        "guided_practice": "కొన్ని ప్రశ్నలతో మార్గదర్శక అభ్యాసాన్ని కొనసాగించండి.",
        "misconception_review": "ముఖ్యమైన భావనను ఉదాహరణతో మళ్లీ పరిశీలించి, ఇలాంటి ప్రశ్నను ప్రయత్నించండి.",
        "prerequisite_review": "దశలవారీ ఉదాహరణతో ముందస్తు అంశాన్ని పునశ్చరణ చేయండి.",
        "challenge_practice": "కొత్త సందర్భంలో ఈ భావనను ఉపయోగించే ప్రశ్నను ప్రయత్నించండి.",
        "hinted_practice": "తదుపరి ఇలాంటి ప్రశ్నకు చిన్న సూచనను చూడండి.",
        "revision_review": "తదుపరి సవాలుకు ముందు ఈ అంశాన్ని చిన్నగా పునశ్చరణ చేయండి.",
    }
    telugu = translations.get(strategy, "మునుపటి అభ్యాసాన్ని కొనసాగించి మరో ప్రశ్నను ప్రయత్నించండి.")
    if language == "telugu":
        return telugu
    if language == "mixed":
        return f"{recommendation}\n{telugu}"
    return recommendation
