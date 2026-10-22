import json
from datetime import datetime, timezone
from typing import List, Optional

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
        The full structured result is kept in metadata so the web UI can reopen it later.
        """
        full_text = f"Student Name: {submission.student_name}, Roll Number: {submission.roll_number}. "
        for eval_item in submission.evaluations:
            full_text += f"Q{eval_item.question_number}: {eval_item.transcribed_answer} (Marks: {eval_item.marks_awarded}/{eval_item.max_marks}) Feedback: {eval_item.feedback} "

        metadata = {
            "student_name": submission.student_name or "Unknown",
            "roll_number": submission.roll_number or "Unknown",
            "total_marks": submission.total_marks_obtained,
            "max_marks": submission.total_max_marks,
            "graded_at": datetime.now(timezone.utc).isoformat(),
            "result_json": submission.model_dump_json(),
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

    # ---- Used by the web app -------------------------------------------------

    def count(self) -> int:
        return self.collection.count()

    def list_submissions(self) -> List[dict]:
        """Lightweight rows for the history table, newest first."""
        data = self.collection.get(include=["metadatas"])
        rows = []
        for sid, meta in zip(data["ids"], data["metadatas"]):
            rows.append(
                {
                    "id": sid,
                    "student_name": meta.get("student_name"),
                    "roll_number": meta.get("roll_number"),
                    "total_marks": meta.get("total_marks"),
                    "max_marks": meta.get("max_marks"),
                    "graded_at": meta.get("graded_at"),
                }
            )
        rows.sort(key=lambda r: r["graded_at"] or "", reverse=True)
        return rows

    def get_submission(self, student_id: str) -> Optional[dict]:
        """Full stored result. Records saved before the web app existed have no
        per-question detail, so they come back with an empty evaluations list."""
        data = self.collection.get(ids=[student_id], include=["metadatas"])
        if not data["ids"]:
            return None
        meta = data["metadatas"][0]
        raw = meta.get("result_json")
        if raw:
            result = json.loads(raw)
        else:
            result = {
                "student_name": meta.get("student_name"),
                "roll_number": meta.get("roll_number"),
                "evaluations": [],
                "total_marks_obtained": meta.get("total_marks", 0),
                "total_max_marks": meta.get("max_marks", 0),
            }
        result["id"] = student_id
        result["graded_at"] = meta.get("graded_at")
        return result

    def delete_submission(self, student_id: str) -> bool:
        if not self.collection.get(ids=[student_id])["ids"]:
            return False
        self.collection.delete(ids=[student_id])
        return True
