from pdf2image import convert_from_path
from typing import List
from PIL import Image
import os


def convert_pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    images = convert_from_path(pdf_path, dpi=dpi)
    return images
