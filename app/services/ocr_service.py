"""OCR service for handwritten notes using DeepSeek OCR via Gradio."""

import os
import tempfile
from typing import List, Tuple

import fitz  # PyMuPDF

from app.core.logging import logger

# Gradio space configuration
DEEPSEEK_OCR_SPACE = "khang119966/DeepSeek-OCR-DEMO"
MODEL_SIZE = "Gundam (Recommended)"
TASK_TYPE = "📄 Convert to Markdown"


class OCRService:
    """Service for extracting text from handwritten notes via DeepSeek OCR."""

    def pdf_pages_to_images(self, pdf_bytes: bytes, dpi: int = 200) -> List[Tuple[int, bytes]]:
        """
        Convert each page of a PDF into a PNG image.

        Args:
            pdf_bytes: Raw PDF file content.
            dpi: Resolution for rendering (higher = better OCR, slower).

        Returns:
            List of (page_number, png_bytes) tuples.
        """
        images = []
        zoom = dpi / 72  # 72 is the default PDF DPI
        matrix = fitz.Matrix(zoom, zoom)

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page_num, page in enumerate(doc, start=1):
                pixmap = page.get_pixmap(matrix=matrix)
                png_bytes = pixmap.tobytes("png")
                images.append((page_num, png_bytes))
                logger.debug(f"Rendered page {page_num} to PNG ({len(png_bytes)} bytes)")

        return images

    def ocr_image(self, image_bytes: bytes, filename: str = "page.png") -> str:
        """
        Run OCR on a single image using DeepSeek OCR via Gradio.

        Args:
            image_bytes: Raw image data (PNG/JPEG).
            filename: Filename hint for the temp file.

        Returns:
            Extracted markdown text.
        """
        # Import here to avoid slow import at startup
        from gradio_client import Client, handle_file

        # Write image to temp file (gradio_client needs a file path)
        tmp_path = None
        try:
            suffix = os.path.splitext(filename)[1] or ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            client = Client(DEEPSEEK_OCR_SPACE)
            result = client.predict(
                image=handle_file(tmp_path),
                model_size=MODEL_SIZE,
                task_type=TASK_TYPE,
                ref_text="",
                api_name="/process_ocr_task",
            )

            logger.debug(f"OCR result for {filename}: {len(result)} chars")
            return result

        except Exception as e:
            logger.error(f"OCR failed for {filename}: {e}")
            raise RuntimeError(
                f"OCR processing failed: {e}. "
                "The DeepSeek OCR service may be temporarily unavailable."
            ) from e

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def ocr_pdf(self, pdf_bytes: bytes) -> str:
        """
        Full pipeline: convert PDF pages to images, OCR each, combine results.

        Args:
            pdf_bytes: Raw PDF file content.

        Returns:
            Combined markdown text from all pages.
        """
        pages = self.pdf_pages_to_images(pdf_bytes)
        logger.info(f"OCR: processing {len(pages)} page(s)")

        all_text = []
        for page_num, image_bytes in pages:
            logger.info(f"OCR: processing page {page_num}/{len(pages)}...")
            text = self.ocr_image(image_bytes, filename=f"page_{page_num}.png")
            if text.strip():
                all_text.append(f"## Page {page_num}\n\n{text.strip()}")

        combined = "\n\n---\n\n".join(all_text)
        logger.info(f"OCR complete: {len(combined)} chars extracted from {len(pages)} page(s)")
        return combined


# Singleton instance
ocr_service = OCRService()
