import chromadb
from .models import StudentSubmission


class StudentDatabase:
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="student_submissions"
        )

    def store_submission(self, submission: StudentSubmission, student_id: str):
        """
        Stores a parsed student submission into ChromaDB for semantic retrieval and tracking.
        """
        full_text = f"Student Name: {submission.student_name}, Roll Number: {submission.roll_number}. "
        for eval_item in submission.evaluations:
            full_text += f"Q{eval_item.question_number}: {eval_item.transcribed_answer} (Marks: {eval_item.marks_awarded}/{eval_item.max_marks}) Feedback: {eval_item.feedback} "

        metadata = {
            "student_name": submission.student_name or "Unknown",
            "roll_number": submission.roll_number or "Unknown",
            "total_marks": submission.total_marks_obtained,
            "max_marks": submission.total_max_marks,
        }

        self.collection.upsert(
            documents=[full_text], metadatas=[metadata], ids=[student_id]
        )

    def query_submissions(self, query_text: str, n_results: int = 3):
        """
        Performs a semantic search across stored student submissions.
        """
        results = self.collection.query(query_texts=[query_text], n_results=n_results)
        return results
