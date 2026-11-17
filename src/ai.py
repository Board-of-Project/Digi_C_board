"""
Gemini evaluation with a pool of API keys.

Keys are tried in the order given. When a key runs out of quota (HTTP 429), is
invalid, or the model is overloaded, the next key is tried automatically. A key
that hit its quota is put on a cooldown so later requests skip it.
"""

import hashlib
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError
from PIL import Image
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import StudentSubmission

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

QUOTA_COOLDOWN_BASE = 60  # seconds; doubles on each repeat, capped at 1 hour
QUOTA_COOLDOWN_MAX = 3600
OVERLOAD_COOLDOWN = 20


class KeyPoolError(Exception):
    """No key in the pool could complete the request."""

    def __init__(self, message: str, report: List[dict], all_quota: bool = False):
        super().__init__(message)
        self.report = report
        self.all_quota = all_quota


class NoKeysError(KeyPoolError):
    """No API key was supplied and none is set in the environment."""


# fingerprint -> (cooldown_until_timestamp, consecutive_quota_strikes)
_cooldowns: Dict[str, Tuple[float, int]] = {}
_lock = threading.Lock()


def _fp(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def classify_error(e: Exception) -> str:
    """Returns 'quota', 'invalid', 'overloaded' or 'other'."""
    code = getattr(e, "code", None)
    text = str(e).lower()
    if (
        "api key not valid" in text
        or "api_key_invalid" in text
        or "api key expired" in text
        or code == 401
        or (code == 403 and "quota" not in text)
    ):
        return "invalid"
    if code == 429 or "resource_exhausted" in text or "quota" in text:
        return "quota"
    if isinstance(e, ServerError) or code in (500, 502, 503, 504):
        return "overloaded"
    return "other"


def _cooldown_left(key: str) -> float:
    with _lock:
        entry = _cooldowns.get(_fp(key))
    if not entry:
        return 0
    return max(0.0, entry[0] - time.time())


def _mark_failed(key: str, kind: str):
    fp = _fp(key)
    with _lock:
        strikes = _cooldowns.get(fp, (0, 0))[1]
        if kind == "invalid":
            _cooldowns[fp] = (float("inf"), strikes)
        elif kind == "quota":
            wait = min(QUOTA_COOLDOWN_BASE * (2**strikes), QUOTA_COOLDOWN_MAX)
            _cooldowns[fp] = (time.time() + wait, strikes + 1)
        elif kind == "overloaded":
            _cooldowns[fp] = (time.time() + OVERLOAD_COOLDOWN, strikes)


def _mark_ok(key: str):
    with _lock:
        _cooldowns.pop(_fp(key), None)


def _build_pool(api_keys: Optional[List[str]]) -> List[Tuple[int, str, str]]:
    """[(index, label, key)]. UI keys keep their position as index; the
    environment key goes last with index -1."""
    pool, seen = [], set()
    for i, k in enumerate(api_keys or []):
        k = (k or "").strip()
        if k and k not in seen:
            seen.add(k)
            pool.append((i, f"Key {i + 1}", k))
    env = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if env and env not in seen:
        pool.append((-1, "Server key", env))
    return pool


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _generate(key: str, contents: list):
    client = genai.Client(api_key=key)
    return client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StudentSubmission,
            temperature=0.1,
        ),
    )


PROMPT = """
You are an expert, fair and encouraging academic evaluator. You are grading one
student's handwritten answer sheet against the question paper.

Process:
1. Read every question in the Question Paper images. Decide the marks for each
   question from the paper (use printed marks if shown) and work out what a
   full-marks answer contains.
2. Read the Student Answer Sheet images and transcribe each handwritten answer
   faithfully. Mark unreadable parts as [illegible]. Do not silently correct the
   student's errors in the transcription.
3. Grade each question and apply the marking scheme. Give partial credit for
   correct method and correct intermediate steps.
4. Include every question in the paper. If a question was not attempted, set its
   status to not_attempted, award 0 and add one mistake of type incomplete saying
   it was left blank.

How to describe mistakes (this is the most important part):
- List every distinct mistake as its own entry. Do not merge unrelated errors.
- what_student_wrote: quote or closely summarise the exact faulty line, value or
  claim. Never write a vague phrase such as "the answer is wrong".
- why_wrong: say specifically what is wrong and why, in plain language a student
  understands. Name the exact concept, rule, formula or step involved.
- correct_approach: show the correct line, formula or worked step, not just
  "revise this". For calculations show the corrected working and final value.
- mistake_type: choose the most accurate category. Use conceptual only when the
  student misunderstood the idea, calculation for slips in arithmetic or algebra,
  wrong_formula for a wrong method, missing_step for skipped working or
  justification, units_or_notation for units, symbols and labels.
- marks_lost: marks lost for that mistake alone. For each question the marks_lost
  values must add up to max_marks minus marks_awarded.
- topic_to_revise: a short, specific topic name, such as "Conservation of
  momentum", not a whole subject.
- strengths: name what the student did right, so the feedback is balanced.
- Do not invent mistakes in correct answers. A fully correct answer has an empty
  mistakes list.

Overall review:
- overall_summary: 3 to 5 sentences covering strengths, the biggest recurring
  problems, and what to fix first.
- weak_topics: topics where marks were lost repeatedly or heavily, most serious
  first. Base this on the mistakes you listed.
- recommendations: 3 to 5 concrete study actions tied to those weak topics.

Make sure total_marks_obtained and total_max_marks equal the sums over the
questions.
"""


def evaluate_with_question_paper_pdf(
    question_paper_images: List[Image.Image],
    answer_sheet_images: List[Image.Image],
    marking_scheme: Optional[str] = None,
    api_keys: Optional[List[str]] = None,
    key_report: Optional[List[dict]] = None,
) -> StudentSubmission:
    """
    Sends the question paper and answer sheet images to Gemini, rotating through
    the supplied API keys (then the GEMINI_API_KEY environment key) on quota,
    invalid-key or overload errors.

    key_report, if given, is filled with one entry per key tried:
    {"index", "label", "status", "message"} where index is the key's position in
    api_keys (-1 for the server key) and status is one of
    used, quota, invalid, overloaded, cooldown, unreadable.
    """
    report: List[dict] = key_report if key_report is not None else []
    pool = _build_pool(api_keys)
    if not pool:
        raise NoKeysError(
            "No Gemini API key available. Add one in the API keys tab or set GEMINI_API_KEY.",
            report,
        )

    prompt = PROMPT
    if marking_scheme:
        prompt += f"\nAdditional Marking Scheme / Rubric:\n{marking_scheme}"
    contents = list(question_paper_images) + list(answer_sheet_images) + [prompt]

    # Pass 1: keys not cooling down. Pass 2: keys whose cooldown has not expired
    # yet, in case the cooldown estimate was too cautious. Invalid keys never retry.
    first = [p for p in pool if _cooldown_left(p[2]) == 0]
    second = [p for p in pool if 0 < _cooldown_left(p[2]) < float("inf")]
    kinds_seen = []

    for passno, group in enumerate((first, second)):
        for index, label, key in group:
            try:
                response = _generate(key, contents)
            except Exception as e:  # noqa: BLE001
                kind = classify_error(e)
                if kind == "other":
                    report.append(
                        {
                            "index": index,
                            "label": label,
                            "status": "error",
                            "message": str(e)[:200],
                        }
                    )
                    raise  # not a key problem, switching keys will not help
                _mark_failed(key, kind)
                kinds_seen.append(kind)
                report.append(
                    {
                        "index": index,
                        "label": label,
                        "status": kind,
                        "message": str(e)[:200],
                    }
                )
                continue

            if response.parsed is None:
                kinds_seen.append("unreadable")
                report.append(
                    {
                        "index": index,
                        "label": label,
                        "status": "unreadable",
                        "message": "The response could not be parsed.",
                    }
                )
                continue

            _mark_ok(key)
            report.append(
                {"index": index, "label": label, "status": "used", "message": ""}
            )
            return response.parsed

    # also list keys that were skipped entirely because they are invalid
    tried = {r["index"] for r in report}
    for index, label, key in pool:
        if index not in tried:
            report.append(
                {
                    "index": index,
                    "label": label,
                    "status": "invalid",
                    "message": "Skipped: this key was rejected earlier.",
                }
            )

    all_quota = bool(kinds_seen) and all(k == "quota" for k in kinds_seen)
    if all_quota:
        msg = "Every API key has reached its quota. Add another key or wait for the limits to reset."
    else:
        msg = "None of the API keys could complete the request. See the per-key status below."
    raise KeyPoolError(msg, report, all_quota=all_quota)


def test_key(key: str) -> dict:
    """Cheap check used by the 'Test' button. Returns {"status", "message"}
    where status is ok, quota, invalid or error."""
    try:
        client = genai.Client(api_key=key.strip())
        client.models.generate_content(
            model=MODEL,
            contents="Reply with the single word OK.",
            config=types.GenerateContentConfig(max_output_tokens=8, temperature=0),
        )
        return {"status": "ok", "message": "Key works."}
    except Exception as e:  # noqa: BLE001
        kind = classify_error(e)
        status = {"quota": "quota", "invalid": "invalid"}.get(kind, "error")
        text = {
            "quota": "This key has reached its quota right now.",
            "invalid": "Google rejected this key. Check that it was copied correctly.",
        }.get(status, f"Could not check the key: {str(e)[:160]}")
        return {"status": status, "message": text}
