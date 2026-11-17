# AI Exam Grader

An AI-powered grading tool. It takes a question paper PDF and a student's handwritten answer sheet PDF, uses Gemini to read, transcribe and grade the answers, explains every mistake in detail, and stores each result in a ChromaDB vector database for later semantic search.

It comes with a web app (FastAPI) and a command-line script. A Streamlit version is also included.

## Features

- Handwriting transcription and grading against the question paper and an optional marking scheme.
- **Batch grading.** Upload several answer sheet PDFs at once. They are graded one by one against the same question paper, with a live queue and a batch summary.
- **Detailed mistake descriptions** for every question: what the student wrote, why it is wrong, the correct approach, marks lost, and the topic to revise.
- **Multiple API keys with automatic fallback.** Add several Gemini keys in the UI. When one reaches its quota, grading switches to the next.
- Per-question status, strengths, expected answer, an overall review, weak topics and study recommendations.
- Results saved to ChromaDB, with a submissions list, semantic search, and CSV and JSON export.
- Totals are recomputed from the per-question marks, and the UI flags any mismatch with the model's own total.

## How it works

1. Convert the question paper and the answer sheet PDFs to images.
2. Send both image sets to Gemini with the marking scheme. Gemini decides the marks per question, transcribes each handwritten answer, awards marks, and lists each mistake with an explanation and a fix.
3. If a key fails because of quota, an invalid key, or an overloaded model, the next key is tried automatically.
4. Show the result: score, per-question breakdown, mistake cards and an overall review.
5. Store the submission in ChromaDB, keyed by roll number (or a random id if none was read).

## Project structure

```
.
├── server.py          # FastAPI web server and API
├── main.py            # Command-line pipeline
├── static/
│   └── index.html     # Web UI (Grade, Submissions, Search, API keys)
├── src/
│   ├── ingest.py      # PDF -> images (pdf2image)
│   ├── ai.py          # Gemini evaluation, API key pool and fallback
│   ├── models.py      # Pydantic schemas for evaluation results
│   ├── database.py    # ChromaDB storage and semantic search
│   └── app.py         # Optional Streamlit app
└── README.md
```

## Requirements

- Python 3.11+
- [Poppler](https://poppler.freedesktop.org/) (required by `pdf2image`)
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`
  - Windows: install Poppler and add its `bin` folder to `PATH`
- One or more Gemini API keys from [Google AI Studio](https://aistudio.google.com/)

## Installation

With [uv](https://docs.astral.sh/uv/) (the project includes a `uv.lock`):

```bash
git clone <your-repo-url>
cd <your-repo-folder>
uv sync
```

Or with pip:

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the web app

```bash
uvicorn server:app --reload      # with uv: uv run uvicorn server:app --reload
```

Open http://127.0.0.1:8000.

1. Open the **API keys** tab and add at least one Gemini key (or set `GEMINI_API_KEY`, see below).
2. Open the **Grade** tab, upload the question paper, then one or more answer sheet PDFs, and click **Grade**.
3. Grading can take a minute or more per sheet for handwriting.
4. Use **Submissions** to reopen past results and **Search** to find them by topic, mistake or phrase.

## Grading several answer sheets

Drop or choose multiple PDFs in the answer sheets box. You can add more files before you start, and remove any file from the queue.

- Sheets are graded one at a time, in the order listed. Each result appears as soon as it finishes.
- The queue shows each sheet as Queued, Grading, Done (with its score) or Failed (with the reason). A failed sheet does not stop the rest.
- If every API key runs out of quota or fails, the batch pauses and the remaining sheets stay queued. Add or fix a key and press the grade button to continue.
- **Stop after this sheet** ends the batch once the current sheet finishes. **Retry failed** requeues failed sheets.
- With two or more sheets, a **Batch summary** shows each student's score and the class average, and lets you download all results as one CSV.
- Saved submissions are keyed by roll number. If two sheets have the same roll number (or the model misreads one), the later one replaces the earlier one in the Submissions tab. The summary warns you when this happens.

The question paper is converted again for each sheet, so large batches take a little longer than strictly necessary.

## API keys and automatic fallback

You can provide keys in two ways.

**In the UI (recommended).** Open the **API keys** tab to add, name, reorder, test and remove keys. Keys are saved in your browser's localStorage and sent with each grading request. The server uses them for that request only and does not store or log them. If you deploy the app, serve it over HTTPS.

**On the server.** Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) before starting the server:

```bash
export GEMINI_API_KEY="your-api-key"
```

### How a key is chosen

Keys are tried in a fixed order: UI keys from top to bottom, then the server key last. The first key that succeeds is used, so key #1 handles every request while it works. Use the arrows in the API keys tab to change the priority.

| Failure | What happens |
|---|---|
| Quota reached (429) | The next key is tried. The key cools down for 60 seconds, doubling on each repeat, up to 1 hour. |
| Model busy or overloaded | Retried up to 3 times on that key, then the next key is tried. 20 second cooldown. |
| Invalid or expired key | Skipped until the server restarts. |
| Other errors (for example a corrupt PDF) | Grading stops and the error is shown, because another key would not help. |

If every available key fails, keys that are still cooling down get one last try, since cooldowns are estimates. If all keys fail, the error lists what happened to each one.

After each grading, the UI shows which key was used and updates each key's badge (Working, Quota reached, Invalid key, Busy).

Cooldown state is kept in server memory and is shared by all users of that server. It resets when the server restarts.

### Choosing the model

The default model is `gemini-3.5-flash-lite`. Override it with the `GEMINI_MODEL` environment variable.

## Mistake descriptions

For each question the result includes:

- `question_text`, `transcribed_answer` and `expected_answer`
- `status`: correct, partially correct, incorrect or not attempted
- `marks_awarded`, `max_marks` and `strengths`
- `mistakes`: a list where each entry has
  - `mistake_type`: conceptual, calculation, wrong formula, missing step, incomplete, units or notation, off-topic, presentation, other
  - `what_student_wrote`
  - `why_wrong`
  - `correct_approach`
  - `marks_lost`
  - `topic_to_revise`
- `feedback`: a short overall comment

For the whole sheet it adds `overall_summary`, `weak_topics` and `recommendations`.

`question_number` is text, so labels such as `2(b)` work. Submissions saved before this version still open and simply have no mistake details.

## Command-line usage

1. Place `questions.pdf` and `answers.pdf` in the project root, or change the paths in `main.py`.
2. Set `GEMINI_API_KEY`.
3. Run:

```bash
python main.py
```

The command-line script uses the server key only. Use the web app for multiple keys.

## Streamlit app (optional)

```bash
streamlit run src/app.py
```

It uses a single key from the sidebar. It does not yet have multi-key fallback or the detailed mistake display.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Server key, Poppler and stored count |
| POST | `/api/grade` | Grade one sheet (the UI calls it once per sheet). Form fields: `question_paper`, `answer_sheet`, `marking_scheme`, `dpi`, `api_keys` (JSON list of keys in priority order) |
| POST | `/api/keys/test` | Check one key. Body: `{"key": "..."}` |
| GET | `/api/submissions` | List stored submissions |
| GET | `/api/submissions/{id}` | One full submission |
| DELETE | `/api/submissions/{id}` | Delete a submission |
| POST | `/api/search` | Semantic search. Body: `{"query": "...", "n": 5}` |

## Modules

### `src/ai.py`
`evaluate_with_question_paper_pdf(question_paper_images, answer_sheet_images, marking_scheme=None, api_keys=None, key_report=None)` sends the images and prompt to Gemini (temperature 0.1) and requests JSON matching the `StudentSubmission` schema. It rotates through the keys as described above. `key_report`, if given, is filled with one entry per key tried. `test_key(key)` backs the Test button.

### `src/models.py`
`Mistake`, `QuestionEvaluation` and `StudentSubmission` Pydantic schemas.

### `src/database.py`
`StudentDatabase` wraps a persistent ChromaDB collection (`student_submissions`, stored in `./chroma_db`). Each submission is stored as one document that includes the answers, feedback, mistakes and weak topics, with the full result kept in metadata so it can be reopened.

### `src/ingest.py`
`convert_pdf_to_images(pdf_path, dpi)` and `convert_pdf_bytes_to_images(pdf_bytes, dpi)` convert PDFs into PIL images.

## Customizing the marking scheme

In the web app, edit the marking scheme box on the Grade tab. For the command-line script, edit the `marking_scheme` string in `main.py`.

## Known limitations

- There is no answer key. Gemini decides the marks distribution from the question paper, so grading can vary between runs. Review results before using them for real marks.
- The marks lost across a question's mistakes are requested to add up to the marks missed, but this is not verified in code.
- Batch grading is sequential, not parallel, and runs from the open browser tab. Closing the tab stops the batch.
- Keys are used in priority order, not rotated evenly, so the first working key takes all the load.
- Cooldowns cannot tell a per-minute limit from a daily one.
- Each submission is stored as a single document, so semantic search is coarse.

## Roadmap

- Round-robin key rotation option
- Per-key usage counters
- Parallel batch grading and a server-side job queue
- Cache the converted question paper across a batch
- Support a fixed rubric or answer key
- Per-question documents in ChromaDB
- PDF report export
- Streamlit app parity with the web app
- Tests

## License

Add a license of your choice.