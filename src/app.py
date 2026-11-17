import os
import streamlit as st
from PIL import Image
from .ingest import convert_pdf_bytes_to_images
from .ai import evaluate_with_question_paper_pdf
from .database import StudentDatabase

# Page Configuration
st.set_page_config(
    page_title="Digi-C-Board: AI Answer Sheet Evaluator", page_icon="📝", layout="wide"
)

# Initialize Database
db = StudentDatabase()

st.title("📝 Digi-C-Board: Intelligent Handwritten Answer Evaluator")
st.markdown(
    "Upload the official Question Paper and a student's handwritten Answer Sheet PDF to automate grading and vector indexing."
)

# Sidebar for API Key & Search
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key_input = st.text_input(
        "Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", "")
    )
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input

    st.divider()
    st.header("🔍 Search Past Submissions")
    search_query = st.text_input("Search query (e.g., 'Student name' or topic)")
    if search_query:
        results = db.query_submissions(search_query, n_results=3)
        st.subheader("Results:")
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            st.info(
                f"**{meta['student_name']}** (Roll: {meta['roll_number']})\nScore: {meta['total_marks']}/{meta['max_marks']}\n\n{doc[:200]}..."
            )

# Main Layout - Two Columns for Uploads
col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Question Paper PDF")
    qp_file = st.file_uploader("Upload Question Paper", type=["pdf"], key="qp")

with col2:
    st.subheader("2️⃣ Student Answer Sheet PDF")
    answer_file = st.file_uploader(
        "Upload Handwritten Answer Sheet", type=["pdf"], key="ans"
    )

# Marking Scheme / Rubric Input
st.subheader("3️⃣ Marking Scheme / Rubric Guidelines")
marking_scheme = st.text_area(
    "Enter marking guidelines, step-wise weightage, or rules:",
    value="""General Rules:
- Award partial credit for correct intermediate steps.
- Deduct marks for factual errors or incomplete explanations.
- Check clarity of handwritten derivations or diagrams.""",
)

# Evaluation Trigger Button
if st.button("🚀 Evaluate Answer Sheet", type="primary"):
    if not os.environ.get("GEMINI_API_KEY"):
        st.error(
            "Please enter your Gemini API Key in the sidebar or set it in your environment variables."
        )
    elif not qp_file or not answer_file:
        st.warning(
            "Please upload both the Question Paper and the Student Answer Sheet PDFs."
        )
    else:
        with st.spinner("Converting PDFs and running multimodal AI evaluation..."):
            try:
                # Convert uploaded files (bytes) to images
                qp_images = convert_pdf_bytes_to_images(qp_file.read(), dpi=300)
                answer_images = convert_pdf_bytes_to_images(answer_file.read(), dpi=300)

                # Run Gemini Evaluation
                result = evaluate_with_question_paper_pdf(
                    qp_images, answer_images, marking_scheme
                )

                # Store in ChromaDB automatically
                student_id = result.roll_number or f"student_{os.urandom(4).hex()}"
                db.store_submission(result, student_id=student_id)

                st.success("Evaluation complete and successfully stored in ChromaDB!")

                # Display Scorecard Metrics
                st.divider()
                st.header("📊 Evaluation Scorecard")

                m1, m2, m3 = st.columns(3)
                m1.metric("Student Name", result.student_name or "Not Specified")
                m2.metric("Roll Number", result.roll_number or "Not Specified")
                m3.metric(
                    "Total Score",
                    f"{result.total_marks_obtained} / {result.total_max_marks}",
                )

                st.subheader("Question-by-Question Breakdown")
                for eval_item in result.evaluations:
                    with st.expander(
                        f"Question {eval_item.question_number} — Score: {eval_item.marks_awarded}/{eval_item.max_marks} marks"
                    ):
                        st.markdown(
                            f"**Transcribed Answer:**\n> {eval_item.transcribed_answer}"
                        )
                        st.markdown(f"**AI Feedback:**\n{eval_item.feedback}")

            except Exception as e:
                st.error(f"An error occurred during evaluation: {e}")
