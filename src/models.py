from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MistakeType = Literal[
    "conceptual",
    "calculation",
    "wrong_formula",
    "missing_step",
    "incomplete",
    "units_or_notation",
    "irrelevant",
    "presentation",
    "other",
]

AnswerStatus = Literal["correct", "partially_correct", "incorrect", "not_attempted"]


class Mistake(BaseModel):
    mistake_type: MistakeType = Field(
        description=(
            "Category of the mistake: conceptual (misunderstood idea), calculation "
            "(arithmetic or algebra slip), wrong_formula (wrong formula or method), "
            "missing_step (skipped a required step or justification), incomplete "
            "(stopped early or left out required points), units_or_notation (wrong or "
            "missing units, symbols, labels), irrelevant (off-topic), presentation "
            "(unclear diagram, illegible, poor structure), other."
        )
    )
    what_student_wrote: str = Field(
        description="The exact part of the student's answer that is wrong, quoted or closely summarised. Say 'Nothing written' if the point was missing."
    )
    why_wrong: str = Field(
        description="Plain-language explanation of what is wrong and why. Be specific to this answer, never generic."
    )
    correct_approach: str = Field(
        description="The correct statement, step or worked line the student should have written, concise but complete enough to learn from."
    )
    marks_lost: float = Field(
        description="Marks lost because of this specific mistake."
    )
    topic_to_revise: str = Field(
        description="Short name of the concept or chapter the student should revise for this mistake."
    )


class QuestionEvaluation(BaseModel):
    question_number: str = Field(
        description="The question label exactly as printed, for example '3' or '2(b)'."
    )
    question_text: str = Field(
        description="A short restatement of what the question asks, taken from the question paper."
    )
    transcribed_answer: str = Field(
        description="Exact transcription of the student's handwritten answer. Use [illegible] for unreadable parts."
    )
    expected_answer: str = Field(
        description="The key points, final answer or steps a full-marks answer needs."
    )
    status: AnswerStatus = Field(
        description="correct, partially_correct, incorrect, or not_attempted."
    )
    marks_awarded: float = Field(
        description="Marks awarded for this question based on the answer key."
    )
    max_marks: float = Field(description="Maximum possible marks for this question.")
    strengths: Optional[str] = Field(
        description="What the student did correctly. Null if nothing is worth crediting."
    )
    mistakes: List[Mistake] = Field(
        description=(
            "Every distinct mistake in this answer. Empty list for a fully correct "
            "answer. The marks_lost values must add up to max_marks minus marks_awarded."
        )
    )
    feedback: Optional[str] = Field(
        description="One or two sentence overall comment to the student on this answer."
    )


class StudentSubmission(BaseModel):
    student_name: Optional[str] = Field(
        description="Name of the student written on the sheet, if present."
    )
    roll_number: Optional[str] = Field(
        description="Student roll number or ID, if present."
    )
    evaluations: List[QuestionEvaluation] = Field(
        description="Breakdown of evaluation for each question in the paper."
    )
    total_marks_obtained: float = Field(
        description="Total marks obtained across all questions."
    )
    total_max_marks: float = Field(description="Total maximum possible marks.")
    overall_summary: str = Field(
        description="Three to five sentences on overall performance: strengths, the biggest recurring problems and the most important thing to fix first."
    )
    weak_topics: List[str] = Field(
        description="Topics where the student lost marks repeatedly or heavily, most serious first."
    )
    recommendations: List[str] = Field(
        description="Three to five concrete, actionable study steps for the student."
    )
