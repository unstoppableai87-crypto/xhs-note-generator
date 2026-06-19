"""Deterministic 违禁词 (banned/risky word) checker for Xiaohongshu (XHS) notes.

Pure rule-based scan against banned_words.json - no AI involved, so results
are consistent and auditable. Edit banned_words.json to tune the word list.
"""
import json
import re
from pathlib import Path

BANNED_WORDS_PATH = Path(__file__).parent / "banned_words.json"


def load_banned_words():
    with open(BANNED_WORDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_text(text, banned_words=None):
    """Scan text for banned/risky words and contact-info leakage patterns.

    Returns a list of {"word": str, "category": str, "position": int} matches.
    """
    if not text:
        return []
    if banned_words is None:
        banned_words = load_banned_words()

    matches = []
    lower_text = text.lower()

    for category, words in banned_words.get("categories", {}).items():
        for word in words:
            pos = lower_text.find(word.lower())
            if pos != -1:
                matches.append({"word": word, "category": category, "position": pos})

    for pattern_def in banned_words.get("patterns", []):
        for m in re.finditer(pattern_def["regex"], text):
            matches.append({
                "word": m.group(0),
                "category": pattern_def["category"],
                "position": m.start(),
            })

    matches.sort(key=lambda m: m["position"])
    return matches


def check_note(title, content, hashtags):
    """Run the banned-word check across all three fields of a note.

    Returns dict: {"title": [...], "content": [...], "hashtags": [...]}
    """
    banned_words = load_banned_words()
    hashtags_text = " ".join(hashtags) if isinstance(hashtags, list) else str(hashtags)
    return {
        "title": check_text(title, banned_words),
        "content": check_text(content, banned_words),
        "hashtags": check_text(hashtags_text, banned_words),
    }


def total_hits(check_result):
    return sum(len(v) for v in check_result.values())
