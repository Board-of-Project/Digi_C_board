from pydantic import BaseModel, Field
from typing import List, Optional


class QuestionEvaluation(BaseModel):
    question_number: int = Field(description="The question number being answered.")
    transcribed_answer: str = Field(
        description="Exact transcription of the student's handwritten answer."
    )
    marks_awarded: float = Field(
        description="Marks awarded for this question based on the answer key."
    )
    max_marks: float = Field(description="Maximum possible marks for this question.")
    feedback: Optional[str] = Field(
        description="Feedback explaining why marks were cut or noting errors."
    )


class StudentSubmission(BaseModel):
    student_name: Optional[str] = Field(
        description="Name of the student written on the sheet, if present."
    )
    roll_number: Optional[str] = Field(
        description="Student roll number or ID, if present."
    )
    evaluations: List[QuestionEvaluation] = Field(
        description="Breakdown of evaluation for each answered question."
    )
    total_marks_obtained: float = Field(
        description="Total marks obtained across all questions."
    )
    total_max_marks: float = Field(description="Total maximum possible marks.")
