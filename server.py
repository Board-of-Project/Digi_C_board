"""
Web server for the AI Exam Grader.

Run:  uvicorn server:app --reload
Open: http://127.0.0.1:8000
"""
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.genai.errors import APIError
from pydantic import BaseModel, Field
from tenacity import RetryError

from src.ai import evaluate_with_question_paper_pdf
from src.database import StudentDatabase
from src.ingest import convert_pdf_to_images

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AI Exam Grader")
db = StudentDatabase()


def make_id(roll_number):
    """Roll number made safe for URLs; random id when no roll number was read."""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", roll_number or "").strip("-.")
    return slug or f"student_{uuid.uuid4().hex[:8]}"


def with_totals(data: dict) -> dict:
    """Adds totals computed from the per-question marks so the UI can flag
    cases where the model's reported total does not add up."""
    evals = data.get("evaluations") or []
    got = round(sum(e.get("marks_awarded") or 0 for e in evals), 2)
    mx = round(sum(e.get("max_marks") or 0 for e in evals), 2)
    data["computed_total"] = got
    data["computed_max"] = mx
    data["totals_match"] = (not evals) or (
        abs(got - (data.get("total_marks_obtained") or 0)) < 0.01
        and abs(mx - (data.get("total_max_marks") or 0)) < 0.01
    )
    return data


def save_upload(upload: UploadFile, dest: str):
    if not (upload.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, f"'{upload.filename}' is not a PDF.")
    with open(dest, "wb") as out:
        shutil.copyfileobj(upload.file, out)


@app.get("/api/health")
def health():
    return {
        "gemini_key": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "poppler": shutil.which("pdftoppm") is not None,
        "stored": db.count(),
    }


@app.post("/api/grade")
def grade(
    question_paper: UploadFile = File(...),
    answer_sheet: UploadFile = File(...),
    marking_scheme: str = Form(""),
    dpi: int = Form(200),
):
    dpi = max(100, min(dpi, 300))

    with tempfile.TemporaryDirectory() as tmp:
        qp_path = os.path.join(tmp, "question_paper.pdf")
        ans_path = os.path.join(tmp, "answer_sheet.pdf")
        save_upload(question_paper, qp_path)
        save_upload(answer_sheet, ans_path)
        try:
            qp_images = convert_pdf_to_images(qp_path, dpi=dpi)
            answer_images = convert_pdf_to_images(ans_path, dpi=dpi)
        except Exception as e:
            raise HTTPException(
                422,
                f"Could not turn the PDFs into images. Check that the files are valid "
                f"and that Poppler is installed. ({e})",
            )

    try:
        result = evaluate_with_question_paper_pdf(
            qp_images, answer_images, marking_scheme.strip() or None
        )
    except RetryError:
        raise HTTPException(503, "Gemini is overloaded right now. Try again in a minute.")
    except APIError as e:
        if getattr(e, "code", None) == 429:
            raise HTTPException(429, "Gemini rate limit reached. Wait a moment and try again.")
        raise HTTPException(502, f"Gemini returned an error: {e}")
    except Exception as e:
        raise HTTPException(500, f"Grading failed: {e}")

    if result is None:
        raise HTTPException(502, "Gemini returned a response that could not be read. Try grading again.")

    student_id = make_id(result.roll_number)
    db.store_submission(result, student_id=student_id)
    return with_totals(db.get_submission(student_id))


@app.get("/api/submissions")
def list_submissions():
    return db.list_submissions()


@app.get("/api/submissions/{student_id}")
def get_submission(student_id: str):
    data = db.get_submission(student_id)
    if data is None:
        raise HTTPException(404, "Submission not found.")
    return with_totals(data)


@app.delete("/api/submissions/{student_id}")
def delete_submission(student_id: str):
    if not db.delete_submission(student_id):
        raise HTTPException(404, "Submission not found.")
    return {"deleted": student_id}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    n: int = Field(5, ge=1, le=20)


@app.post("/api/search")
def search(req: SearchRequest):
    count = db.count()
    if count == 0:
        return []
    res = db.query_submissions(req.query, n_results=min(req.n, count))
    hits = []
    for i, sid in enumerate(res["ids"][0]):
        meta = res["metadatas"][0][i]
        doc = res["documents"][0][i]
        excerpt = re.sub(r"^Student Name:.*?Roll Number:[^.]*\.\s*", "", doc)[:260]
        hits.append(
            {
                "id": sid,
                "student_name": meta.get("student_name"),
                "roll_number": meta.get("roll_number"),
                "total_marks": meta.get("total_marks"),
                "max_marks": meta.get("max_marks"),
                "excerpt": excerpt,
            }
        )
    return hits


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
