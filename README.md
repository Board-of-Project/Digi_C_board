# AI Exam Grader

An AI-powered grading pipeline. It takes a question paper PDF and a student's handwritten answer sheet PDF, uses Gemini to read, transcribe and grade the answers, and stores each result in a ChromaDB vector database for later semantic search.

## How it works

1. Convert the question paper PDF to images (300 DPI).
2. Convert the student's answer sheet PDF to images (300 DPI).
3. Send both image sets to Gemini with a general marking scheme. Gemini decides the marks per question, transcribes each handwritten answer, awards marks and writes feedback.
4. Print the results: student name, roll number, total marks, and per-question transcription, marks and feedback.
5. Store the submission in ChromaDB, keyed by roll number (falls back to `student_001`).

## Project structure

```
.
├── main.py            # Entry point: runs the full pipeline
├── src/
│   ├── ingest.py      # PDF -> images (pdf2image)
│   ├── ai.py          # Gemini evaluation with structured output and retries
│   ├── models.py      # Pydantic schemas for evaluation results
│   └── database.py    # ChromaDB storage and semantic search
└── README.md
```

## Requirements

- Python 3.10+
- [Poppler](https://poppler.freedesktop.org/) (required by `pdf2image`)
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`
  - Windows: install Poppler and add its `bin` folder to `PATH`
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## Installation

```bash
git clone <your-repo-url>
cd <your-repo-folder>
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install pdf2image pillow google-genai pydantic tenacity chromadb
```

## Configuration

Set your Gemini API key as an environment variable (the Google GenAI client reads it automatically):

```bash
export GEMINI_API_KEY="your-api-key"
```

## Usage

1. Place the question paper and the student's answer sheet PDFs in the project root.
2. Update the file paths in `main.py`:

```python
   qp_pdf_path = "questions.pdf"
   answer_pdf_path = "answers.pdf"
```

3. Run:

```bash
   python main.py
```

Example output:

```
--- Evaluation Results ---
Student Name: ...
Roll Number: ...
Total Marks: 18 / 25

Question 1:
  Transcribed: ...
  Marks: 4 / 5
  Feedback: ...
```

## Modules

### `src/ingest.py`
`convert_pdf_to_images(pdf_path, dpi=300)` converts a PDF into a list of PIL images. Raises `FileNotFoundError` if the file does not exist.

### `src/ai.py`
`evaluate_with_question_paper_pdf(question_paper_images, answer_sheet_images, marking_scheme=None)` sends the images and prompt to `gemini-3.5-flash-lite` (temperature 0.1) and requests JSON matching the `StudentSubmission` schema. Retries up to 5 times with exponential backoff on server errors such as 503.

### `src/models.py`
- `QuestionEvaluation`: question number, transcribed answer, marks awarded, max marks, feedback.
- `StudentSubmission`: student name, roll number, list of evaluations, total obtained, total max.

### `src/database.py`
`StudentDatabase` wraps a persistent ChromaDB collection (`student_submissions`, stored in `./chroma_db`).
- `store_submission(submission, student_id)`: flattens a submission into one document with metadata and upserts it.
- `query_submissions(query_text, n_results=3)`: semantic search across stored submissions.

## Customizing the marking scheme

Edit the `marking_scheme` string in `main.py`. The current default awards partial credit for correct intermediate steps and deducts up to 0.5 marks for minor spelling or notation errors.

## Known limitations

- File paths and marking scheme are hardcoded; there is no CLI or batch mode.
- There is no answer key, so Gemini decides the marks distribution itself and grading may vary between runs.
- Totals returned by the model are not verified against the sum of per-question marks.
- Only `ServerError` is retried; rate limits and other API errors are not handled.
- Each submission is stored as a single document, so semantic search is coarse.

## Roadmap

- Accept file paths via CLI arguments
- Batch grading for multiple students
- Support a fixed rubric or answer key
- Validate totals against per-question marks
- Per-question documents in ChromaDB
- Report export and a teacher-facing UI
- Tests

## License

Add a license of your choice.
