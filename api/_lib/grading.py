import re
import unicodedata


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def grade(q: dict, answer: str) -> dict:
    """Return {correct, your_answer, correct_answer} for one stored question."""
    answer = (answer or "").strip()
    if q["answer_mode"] == "options":
        correct_text = q["options"][q["correct_index"]]
        try:
            idx = int(answer)
            ok = idx == q["correct_index"]
            yours = q["options"][idx] if 0 <= idx < len(q["options"]) else ""
        except ValueError:
            ok, yours = False, ""
        return {"correct": ok, "your_answer": yours, "correct_answer": correct_text}
    accepted = [normalize(a) for a in q["accepted"]]
    ok = normalize(answer) in accepted and normalize(answer) != ""
    return {"correct": ok, "your_answer": answer, "correct_answer": q["accepted"][0]}


def public_question(q: dict) -> dict:
    return {
        "id": q["id"],
        "type": q["type"],
        "text": q["text"],
        "image_url": q.get("image_url"),
        "answer_mode": q["answer_mode"],
        "options": q.get("options", []),
        "points": q["points"],
    }
