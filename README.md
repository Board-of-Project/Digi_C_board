# AI Exam Grader

Grades handwritten answer sheets with Gemini. Upload a question paper PDF and a student's answer sheet PDF; the app transcribes each answer, awards marks, writes feedback, and stores the result in ChromaDB for review and semantic search. Use it through the web app or the original command-line script.

## Structure

```
.
├── main.py            # CLI entry point
├── server.py          # FastAPI server and JSON API
├── static/index.html  # Web UI (single file, no build step)
├── src/
│   ├── ingest.py      # PDF -> images (pdf2image)
│   ├── ai.py          # Gemini grading with structured output and retries
│   ├── models.py      # Pydantic schemas
│   └── database.py    # ChromaDB storage, listing, search
└── requirements.txt
```

## Setup

Requires Python 3.10+, [Poppler](https://poppler.freedesktop.org/) (`brew install poppler` or `sudo apt install poppler-utils`; on Windows add its `bin` folder to `PATH`), and a Gemini API key from [Google AI Studio](https://aistudio.google.com/).

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-api-key"
```

## Usage

**Web app**

```bash
uvicorn server:app --reload
```

Open http://127.0.0.1:8000.

- **Grade:** upload both PDFs, edit the marking scheme, choose a scan quality, and download the result as CSV or JSON.
- **Submissions:** browse, reopen or delete past results.
- **Search:** semantic search across stored submissions.

The page flags results where Gemini's total doesn't match the sum of the question marks, or where a question is awarded more than its maximum.

**Command line:** set `qp_pdf_path` and `answer_pdf_path` in `main.py`, then run `python main.py`.

## API

Interactive docs are served at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check API key, Poppler, and stored count |
| `POST` | `/api/grade` | Form fields `question_paper`, `answer_sheet`, optional `marking_scheme`, `dpi` (100 to 300) |
| `GET` | `/api/submissions` | List submissions |
| `GET` / `DELETE` | `/api/submissions/{id}` | Fetch or delete one |
| `POST` | `/api/search` | `{"query": "...", "n": 5}` |

## Customizing the marking scheme

Edit the box on the Grade page, or the `marking_scheme` string in `main.py` for the CLI.

## Known limitations

- No answer key: Gemini sets the marks distribution, so grading can vary between runs.
- Totals are checked only in the web app.
- One sheet at a time; re-grading a roll number overwrites it.
- No login: run on a trusted machine or network only.
- Only server errors are retried automatically.
- Each submission is one ChromaDB document, so search is coarse.

## Roadmap

Batch grading, fixed rubric or answer key, per-question search documents, editable marks in the UI, scanned pages beside the transcription, authentication, tests.
