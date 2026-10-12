import os
from typing import List, Optional
from PIL import Image
from google import genai
from google.genai import types
from .models import StudentSubmission
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from google.genai.errors import ServerError


@retry(
    stop=stop_after_attempt(5),  # Try up to 5 times
    wait=wait_exponential(
        multiplier=1, min=2, max=10
    ),  # Wait 2s, 4s, 8s... between retries
    retry=retry_if_exception_type(ServerError),  # Only retry on ServerError (like 503)
)
def evaluate_with_question_paper_pdf(
    question_paper_images: List[Image.Image],
    answer_sheet_images: List[Image.Image],
    marking_scheme: Optional[str] = None,
) -> StudentSubmission:
    """
    Sends both the question paper PDF images and the student answer sheet PDF images
    to Gemini along with an optional marking scheme.
    """
    client = genai.Client()

    prompt = """
    You are an expert academic evaluator. 
    
    1. First, review the provided Question Paper images to understand the questions, structure, and decide the marks for each question yourself.
    2. Second, review the Student Answer Sheet images to read the handwritten responses.
    3. Accurately transcribe each handwritten answer, evaluate it against the questions, and apply the marking scheme/guidelines you had decided.
    """

    if marking_scheme:
        prompt += f"\nAdditional Marking Scheme / Rubric:\n{marking_scheme}"

    # Pass question paper images first, then answer sheet images, followed by the text prompt
    contents = list(question_paper_images) + list(answer_sheet_images) + [prompt]

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StudentSubmission,
            temperature=0.1,
        ),
    )

    return response.parsed
