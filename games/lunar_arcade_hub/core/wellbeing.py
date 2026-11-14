"""Astronaut psychological-wellbeing check-in: questions, scoring, feedback.

Self-reported indicators only.  Nothing here diagnoses a disorder or produces
a single "mental health score": each dimension is scored and displayed
separately, with negatively worded items reverse-scored into a favourable
(positive) percentage.

Scoring convention
------------------
* Answers use a 1-5 agreement scale.
* Negatively worded items (``positive=False``) describe difficulty, so their
  raw answer is the difficulty score.
* Positively worded items are reversed: difficulty = 6 - answer.
* A dimension's favourable score is the mean of its positive item scores,
  expressed as 0-100 % (higher = more favourable).
"""

SCALE = [
    (1, "Strongly disagree", "STRONGLY\nDISAGREE"),
    (2, "Disagree", "DISAGREE"),
    (3, "Neutral", "NEUTRAL"),
    (4, "Agree", "AGREE"),
    (5, "Strongly agree", "STRONGLY\nAGREE"),
]

DIMENSIONS = [
    {
        "key": "workload",
        "title": "Cognitive workload",
        "short": "WORKLOAD",
        "questions": [1, 2, 3],
        "description": "Mental load, concentration and mental fatigue today.",
    },
    {
        "key": "emotional",
        "title": "Emotional wellbeing",
        "short": "EMOTIONAL",
        "questions": [4, 5, 6, 7],
        "description": "Mood, loneliness and emotional connection.",
    },
    {
        "key": "motivation",
        "title": "Motivation & mission adjustment",
        "short": "MOTIVATION",
        "questions": [8, 9, 10, 11],
        "description": "Purpose, drive and patience with mission demands.",
    },
    {
        "key": "social",
        "title": "Social connection & isolation",
        "short": "SOCIAL",
        "questions": [12, 13, 14],
        "description": "Connection with Earth and available support.",
    },
    {
        "key": "resilience",
        "title": "Psychological resilience",
        "short": "RESILIENCE",
        "questions": [15, 16, 17],
        "description": "Mood lift, recovery and outlook over coming days.",
    },
]

QUESTIONS = [
    {"id": 1, "dimension": "workload", "positive": False,
     "text": "I feel mentally overloaded by the number of tasks and "
             "responsibilities I have today."},
    {"id": 2, "dimension": "workload", "positive": False,
     "text": "I find it difficult to concentrate because too many thoughts "
             "are competing for my attention."},
    {"id": 3, "dimension": "workload", "positive": True,
     "text": "I feel mentally refreshed and capable of handling my daily "
             "responsibilities."},
    {"id": 4, "dimension": "emotional", "positive": True,
     "text": "I have felt emotionally positive during most of today."},
    {"id": 5, "dimension": "emotional", "positive": False,
     "text": "I have experienced feelings of loneliness or isolation during "
             "this mission."},
    {"id": 6, "dimension": "emotional", "positive": True,
     "text": "I feel emotionally connected to people and places on Earth."},
    {"id": 7, "dimension": "emotional", "positive": False,
     "text": "I have felt frustrated or emotionally overwhelmed recently."},
    {"id": 8, "dimension": "motivation", "positive": True,
     "text": "I feel motivated to complete my daily mission objectives."},
    {"id": 9, "dimension": "motivation", "positive": False,
     "text": "Today's mission demands more mental effort than I feel "
             "capable of giving."},
    {"id": 10, "dimension": "motivation", "positive": True,
     "text": "I feel that my daily activities have a meaningful purpose."},
    {"id": 11, "dimension": "motivation", "positive": True,
     "text": "I have enough patience to deal with unexpected challenges "
             "today."},
    {"id": 12, "dimension": "social", "positive": False,
     "text": "I miss having ordinary social interactions with people "
             "outside the spacecraft."},
    {"id": 13, "dimension": "social", "positive": False,
     "text": "I would like more opportunities to connect with Earth and the "
             "people I care about."},
    {"id": 14, "dimension": "social", "positive": True,
     "text": "I feel that I have sufficient social and emotional support "
             "during this mission."},
    {"id": 15, "dimension": "resilience", "positive": True,
     "text": "I experienced at least one moment today that improved my "
             "mood."},
    {"id": 16, "dimension": "resilience", "positive": True,
     "text": "I feel capable of recovering emotionally after a difficult "
             "day."},
    {"id": 17, "dimension": "resilience", "positive": True,
     "text": "I have something to look forward to during the coming days."},
]

BY_ID = {q["id"]: q for q in QUESTIONS}
DIM_BY_KEY = {d["key"]: d for d in DIMENSIONS}
TOTAL_QUESTIONS = len(QUESTIONS)


def normalise_answers(answers):
    """Return {int question_id: int 1-5} for valid answers only."""
    clean = {}
    for key, value in (answers or {}).items():
        try:
            qid = int(key)
            score = int(value)
        except (TypeError, ValueError):
            continue
        if qid in BY_ID and 1 <= score <= 5:
            clean[qid] = score
    return clean


def is_complete(answers):
    return len(normalise_answers(answers)) == TOTAL_QUESTIONS


def dimension_progress(answers):
    answers = normalise_answers(answers)
    return {
        d["key"]: sum(1 for q in d["questions"] if q in answers)
        for d in DIMENSIONS
    }


def unanswered_questions(answers):
    answers = normalise_answers(answers)
    return [q["id"] for q in QUESTIONS if q["id"] not in answers]


def _label(percent):
    if percent >= 70:
        return "Favorable"
    if percent >= 50:
        return "Mixed"
    if percent >= 35:
        return "Strained"
    return "Low"


def score_submission(answers, previous=None):
    """Score each dimension separately.

    ``previous`` may be a previous scores list to add per-dimension deltas.
    Raises ValueError if the questionnaire is incomplete.
    """
    answers = normalise_answers(answers)
    if len(answers) != TOTAL_QUESTIONS:
        raise ValueError("All 17 questions must be answered before scoring.")
    previous_map = {d["key"]: d for d in (previous or [])}
    result = []
    for dim in DIMENSIONS:
        positive_values = []
        difficulty_values = []
        for qid in dim["questions"]:
            raw = answers[qid]
            positive = raw if BY_ID[qid]["positive"] else 6 - raw
            positive_values.append(positive)
            difficulty_values.append(6 - positive)
        positive_mean = sum(positive_values) / len(positive_values)
        difficulty_mean = sum(difficulty_values) / len(difficulty_values)
        percent = int(round((positive_mean - 1) / 4 * 100))
        entry = {
            "key": dim["key"],
            "title": dim["title"],
            "short": dim["short"],
            "positive_mean": round(positive_mean, 2),
            "difficulty_mean": round(difficulty_mean, 2),
            "percent": percent,
            "label": _label(percent),
        }
        prev = previous_map.get(dim["key"])
        if prev and prev.get("percent") is not None:
            entry["delta"] = percent - int(prev["percent"])
        result.append(entry)
    return result


def build_feedback(scores, previous=None):
    """Supportive, response-specific feedback; never a diagnosis."""
    by_key = {d["key"]: d for d in scores}
    prev = {d["key"]: d for d in (previous or [])}
    low = [d for d in scores if d["percent"] < 50]
    mixed = [d for d in scores if 50 <= d["percent"] < 70]
    very_low = [d for d in scores if d["percent"] <= 30]
    recommendations = []
    if by_key["workload"]["percent"] < 50:
        recommendations.append(
            "Cognitive load looks elevated: group tasks into short blocks, "
            "schedule brief breaks and avoid unnecessary multitasking.")
    if by_key["emotional"]["percent"] < 50:
        recommendations.append(
            "Emotional wellbeing looks strained: plan a restorative activity "
            "and a meaningful conversation with someone you trust.")
    if by_key["social"]["percent"] < 50:
        recommendations.append(
            "Connection may be running low: schedule time with family, "
            "friends or mission-support personnel.")
    if by_key["motivation"]["percent"] < 50:
        recommendations.append(
            "Motivation looks low: set one achievable short-term goal and "
            "include a recreational activity you value.")
    if by_key["resilience"]["percent"] < 50:
        recommendations.append(
            "Resilience looks stretched: use a relaxation routine and protect "
            "structured recovery time.")
    if not recommendations:
        recommendations.append(
            "Your dimensions are broadly steady today. Keep protecting sleep, "
            "breaks, social contact and meaningful routines.")

    persistent = [d for d in very_low
                  if prev.get(d["key"], {}).get("percent", 100) <= 40]
    urgent = None
    if persistent:
        urgent = (
            "Several dimensions have been low across more than one check-in. "
            "Consider speaking with a qualified mental-health professional or "
            "mission medical support for a confidential review.")
    elif len(very_low) >= 3:
        urgent = (
            "Several dimensions are very low today. Consider a repeat "
            "check-in soon; if this persists, speak with a qualified "
            "mental-health professional or mission medical support.")
    elif very_low:
        urgent = (
            "One dimension is notably low today. If it remains low on your "
            "next check-in, consider talking with qualified support staff.")
    if urgent:
        recommendations.insert(0, urgent)

    if low:
        names = ", ".join(d["title"].lower() for d in low)
        summary = ("This self-report suggests strain in: " + names +
                   ". These are indicators, not a diagnosis.")
    elif mixed:
        names = ", ".join(d["title"].lower() for d in mixed)
        summary = ("This self-report is mixed: " + names +
                   " sit below the favourable range today. These are "
                   "indicators, not a diagnosis.")
    else:
        summary = ("This self-report is broadly favourable across all five "
                   "dimensions. These are indicators, not a diagnosis.")

    improved = [d for d in scores
                if d.get("delta") is not None and d["delta"] >= 10]
    declined = [d for d in scores
                if d.get("delta") is not None and d["delta"] <= -10]
    if improved:
        summary += " Improved since the last check-in: " + ", ".join(
            d["title"].lower() for d in improved) + "."
    if declined:
        summary += " Lower than the last check-in: " + ", ".join(
            d["title"].lower() for d in declined) + "."

    pattern = None
    if persistent:
        pattern = ("Persistent low scores (not a single response): " +
                   ", ".join(d["title"] for d in persistent) + ".")
    elif len(very_low) >= 3:
        pattern = ("Several dimensions are low together today; a repeat "
                   "check-in can confirm whether this is a persistent pattern.")
    elif improved:
        pattern = "Improvement is visible compared with the previous check-in."
    return {
        "summary": summary,
        "recommendations": recommendations[:5],
        "pattern": pattern,
        "note": ("Self-reported wellbeing indicators. This is not a clinical "
                 "assessment, diagnosis or treatment recommendation."),
    }


def trend_series(submissions):
    """Return chart points per dimension for submitted rows (oldest first).

    ``submissions`` rows must contain a parsed ``scores`` list under the
    ``scores_data`` key (added by the database helper).
    """
    series = {d["key"]: [] for d in DIMENSIONS}
    for row in submissions:
        scores = row.get("scores_data") or []
        by_key = {s.get("key"): s for s in scores}
        for dim in DIMENSIONS:
            entry = by_key.get(dim["key"])
            if entry and entry.get("percent") is not None:
                series[dim["key"]].append(int(entry["percent"]))
    return series


def flatten_answers(answers):
    return {str(qid): int(value) for qid, value in
            normalise_answers(answers).items()}
