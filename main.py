import os
from src.ingest import convert_pdf_to_images
from src.ai import evaluate_with_question_paper_pdf
from src.database import StudentDatabase


def main():
    qp_pdf_path = "questions.pdf"
    answer_pdf_path = "answers.pdf"

    if not os.path.exists(qp_pdf_path) or not os.path.exists(answer_pdf_path):
        print(
            f"Please ensure both '{qp_pdf_path}' and '{answer_pdf_path}' exist in your root directory."
        )
        return

    print("Step 1: Converting Question Paper PDF to images...")
    qp_images = convert_pdf_to_images(qp_pdf_path, dpi=300)

    print("Step 2: Converting Student Answer Sheet PDF to images...")
    answer_images = convert_pdf_to_images(answer_pdf_path, dpi=300)

    # Optional general marking guidelines (if any)
    marking_scheme = """
    General Rules:
    - Award partial credit for correct intermediate steps in mathematical or conceptual questions.
    - Deduct up to 0.5 marks for minor spelling or notation errors if the core concept is correct.
    """

    print("Step 3: Sending both documents to Gemini for evaluation...")
    submission_result = evaluate_with_question_paper_pdf(
        qp_images, answer_images, marking_scheme
    )

    print("\n--- Evaluation Results ---")
    print(f"Student Name: {submission_result.student_name}")
    print(f"Roll Number: {submission_result.roll_number}")
    print(
        f"Total Marks: {submission_result.total_marks_obtained} / {submission_result.total_max_marks}"
    )
    for eval_item in submission_result.evaluations:
        print(f"\nQuestion {eval_item.question_number}:")
        print(f"  Transcribed: {eval_item.transcribed_answer}")
        print(f"  Marks: {eval_item.marks_awarded} / {eval_item.max_marks}")
        print(f"  Feedback: {eval_item.feedback}")

    print("\nStep 4: Storing submission into ChromaDB...")
    db = StudentDatabase()
    student_id = submission_result.roll_number or "student_001"
    db.store_submission(submission_result, student_id=student_id)
    print("Submission successfully indexed and stored in ChromaDB!")


if __name__ == "__main__":
    main()
