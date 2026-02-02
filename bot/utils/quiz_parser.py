from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedQuiz:
    question: str
    options: list[str]
    correct_index: int  # 1-based
    points: int


_KEYVAL_RE = re.compile(r"^\s*([a-zA-Z_]+)\s*=\s*(.+?)\s*$")


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1]) and s[0] in {"'", '"'}):
        return s[1:-1].strip()
    return s


def parse_quiz_set(text: str) -> ParsedQuiz:
    """
    Accepts:
      /quiz_set "Question" | "A" | "B" | "C" | correct=2 | points=10
    """
    raw = (text or "").strip()
    if not raw.lower().startswith("/quiz_set"):
        raise ValueError("Not a /quiz_set command")

    payload = raw[len("/quiz_set") :].strip()
    if not payload:
        raise ValueError('Missing quiz content. Example: /quiz_set "Q" | "A" | "B" | correct=1 | points=10')

    parts = [p.strip() for p in payload.split("|")]
    parts = [p for p in parts if p]  # drop empties

    if len(parts) < 3:
        raise ValueError("You must provide at least: question | option1 | option2")

    question = _strip_quotes(parts[0])
    if not question:
        raise ValueError("Question cannot be empty")

    # Collect options until key=val tokens start
    options: list[str] = []
    correct_index: int | None = None
    points: int = 10

    for token in parts[1:]:
        m = _KEYVAL_RE.match(token)
        if m:
            key = m.group(1).strip().lower()
            val = _strip_quotes(m.group(2))

            if key == "correct":
                # allow 1-based int
                try:
                    correct_index = int(val)
                except ValueError as e:
                    raise ValueError("correct must be an integer like correct=2") from e
            elif key == "points":
                try:
                    points = int(val)
                except ValueError as e:
                    raise ValueError("points must be an integer like points=10") from e
            else:
                raise ValueError(f"Unknown setting: {key}. Allowed: correct, points")
        else:
            opt = _strip_quotes(token)
            if opt:
                options.append(opt)

    if len(options) < 2:
        raise ValueError("You must provide at least 2 options")

    if correct_index is None:
        raise ValueError("Missing correct index. Add: correct=1 (1 = first option)")

    if correct_index < 1 or correct_index > len(options):
        raise ValueError(f"correct must be between 1 and {len(options)}")

    if points < 0 or points > 10_000:
        raise ValueError("points out of allowed range")

    return ParsedQuiz(question=question, options=options, correct_index=correct_index, points=points)
