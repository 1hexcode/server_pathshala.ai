"""PDF text extraction and cleanup service for ML training data."""

import re
import unicodedata
import uuid
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF


class PDFService:
    """Service for PDF text extraction and processing for ML training."""

    def __init__(self, output_dir: str = "extracted_texts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract all text from a PDF file."""
        text_parts = []

        with fitz.open(stream=pdf_content, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(page_text)

        return "\n\n".join(text_parts)

    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode characters to ASCII equivalents."""
        # Normalize to NFKC form (compatibility decomposition + canonical composition)
        text = unicodedata.normalize("NFKC", text)

        # Replace common unicode characters with ASCII equivalents
        replacements = {
            # Quotes
            """: '"', """: '"', "„": '"', "‟": '"',
            "'": "'", "'": "'", "‚": "'", "‛": "'",
            "«": '"', "»": '"',
            # Dashes
            "—": "-", "–": "-", "−": "-", "‐": "-", "‑": "-",
            # Spaces
            "\u00a0": " ",  # Non-breaking space
            "\u2002": " ",  # En space
            "\u2003": " ",  # Em space
            "\u2009": " ",  # Thin space
            "\u200b": "",   # Zero-width space
            "\ufeff": "",   # BOM
            # Bullets
            "•": "-", "·": "-", "●": "-", "○": "-",
            "■": "-", "□": "-", "▪": "-", "▫": "-",
            "►": "-", "▸": "-", "‣": "-",
            # Ellipsis
            "…": "...",
            # Math symbols
            "×": "x", "÷": "/",
            # Other
            "™": "", "®": "", "©": "",
            "°": " degrees ",
            "€": "EUR ", "£": "GBP ", "¥": "JPY ",
            "½": "1/2", "¼": "1/4", "¾": "3/4",
            "²": "2", "³": "3",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _remove_headers_footers(self, text: str) -> str:
        """Remove repetitive headers and footers."""
        lines = text.split("\n")

        if len(lines) < 20:
            return text

        # Find lines that appear multiple times (likely headers/footers)
        line_counts = Counter(line.strip() for line in lines if line.strip())
        threshold = max(3, len(lines) // 50)  # Lines appearing more than threshold times

        repeated_lines = {
            line for line, count in line_counts.items()
            if count >= threshold and len(line) < 100
        }

        # Filter out repeated lines
        filtered_lines = [
            line for line in lines
            if line.strip() not in repeated_lines
        ]

        return "\n".join(filtered_lines)

    def _remove_page_numbers(self, text: str) -> str:
        """Remove standalone page numbers."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip lines that are just numbers (page numbers)
            if stripped.isdigit():
                continue
            # Skip common page number patterns
            if re.match(r"^(page\s*)?\d+(\s*of\s*\d+)?$", stripped, re.IGNORECASE):
                continue
            if re.match(r"^-\s*\d+\s*-$", stripped):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _fix_hyphenated_words(self, text: str) -> str:
        """Rejoin words split by hyphens at line breaks."""
        # Pattern: word ending with hyphen followed by newline and continuation
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
        return text

    def _clean_whitespace(self, text: str) -> str:
        """Normalize all whitespace."""
        # Replace tabs with spaces
        text = text.replace("\t", " ")

        # Remove multiple spaces
        text = re.sub(r" +", " ", text)

        # Remove spaces at the beginning and end of lines
        text = "\n".join(line.strip() for line in text.split("\n"))

        # Remove excessive newlines (more than 2)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _remove_special_patterns(self, text: str) -> str:
        """Remove special patterns not useful for training."""
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"www\.\S+", "", text)

        # Remove email addresses
        text = re.sub(r"\S+@\S+\.\S+", "", text)

        # Remove file paths
        text = re.sub(r"[A-Za-z]:\\[\w\\]+", "", text)
        text = re.sub(r"/[\w/]+\.\w+", "", text)

        # Remove common document artifacts
        text = re.sub(r"\[?\d+\]", "", text)  # Citation numbers like [1] or 1
        text = re.sub(r"fig(ure)?\.?\s*\d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"table\s*\d+", "", text, flags=re.IGNORECASE)

        return text

    def _remove_short_lines(self, text: str, min_length: int = 3) -> str:
        """Remove very short lines that are likely artifacts."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            # Keep empty lines (paragraph separators) and lines above min length
            if not stripped or len(stripped) >= min_length:
                # But skip lines that are just punctuation
                if stripped and re.match(r"^[\W\d]+$", stripped):
                    continue
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _normalize_sentences(self, text: str) -> str:
        """Normalize sentence structure for better training data."""
        # Ensure proper spacing after punctuation
        text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)

        # Fix missing space after commas
        text = re.sub(r",([A-Za-z])", r", \1", text)

        # Remove multiple punctuation
        text = re.sub(r"([.!?]){2,}", r"\1", text)

        # Normalize ellipsis
        text = re.sub(r"\.{2,}", "...", text)

        return text

    def _join_broken_paragraphs(self, text: str) -> str:
        """Join lines that are part of the same paragraph."""
        lines = text.split("\n")
        result = []
        current_paragraph = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                # Empty line = paragraph break
                if current_paragraph:
                    result.append(" ".join(current_paragraph))
                    current_paragraph = []
                continue

            # Check if this line continues the previous paragraph
            if current_paragraph:
                prev_line = current_paragraph[-1]
                # If previous line doesn't end with sentence-ending punctuation,
                # this line is likely a continuation
                if not re.search(r"[.!?:]\s*$", prev_line):
                    current_paragraph.append(stripped)
                    continue

            # Start new paragraph or sentence
            if current_paragraph:
                result.append(" ".join(current_paragraph))
            current_paragraph = [stripped]

        # Don't forget the last paragraph
        if current_paragraph:
            result.append(" ".join(current_paragraph))

        return "\n\n".join(result)

    def cleanup_text(self, text: str) -> str:
        """
        Clean up extracted text for ML model training.

        Pipeline:
        1. Normalize unicode characters
        2. Fix hyphenated words across line breaks
        3. Remove headers/footers
        4. Remove page numbers
        5. Remove special patterns (URLs, emails, etc.)
        6. Clean whitespace
        7. Remove short artifact lines
        8. Normalize sentences
        9. Join broken paragraphs
        """
        # Step 1: Unicode normalization
        text = self._normalize_unicode(text)

        # Step 2: Fix hyphenated words
        text = self._fix_hyphenated_words(text)

        # Step 3: Remove headers/footers
        text = self._remove_headers_footers(text)

        # Step 4: Remove page numbers
        text = self._remove_page_numbers(text)

        # Step 5: Remove special patterns
        text = self._remove_special_patterns(text)

        # Step 6: Clean whitespace
        text = self._clean_whitespace(text)

        # Step 7: Remove short lines
        text = self._remove_short_lines(text)

        # Step 8: Normalize sentences
        text = self._normalize_sentences(text)

        # Step 9: Join broken paragraphs
        text = self._join_broken_paragraphs(text)

        # Final whitespace cleanup
        text = self._clean_whitespace(text)

        return text

    def save_text_to_file(self, text: str, original_filename: str) -> str:
        """Save extracted text to a file and return the filepath."""
        # Generate unique filename
        base_name = Path(original_filename).stem
        unique_id = uuid.uuid4().hex[:8]
        output_filename = f"{base_name}_{unique_id}.txt"
        output_path = self.output_dir / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        return str(output_path)

    def process_pdf(self, pdf_content: bytes, original_filename: str) -> dict:
        """Extract, clean, and save text from a PDF for ML training."""
        # Extract text
        raw_text = self.extract_text_from_pdf(pdf_content)

        # Clean up text for training
        cleaned_text = self.cleanup_text(raw_text)

        # Save to file
        output_path = self.save_text_to_file(cleaned_text, original_filename)

        # Count paragraphs
        paragraphs = [p for p in cleaned_text.split("\n\n") if p.strip()]

        return {
            "original_filename": original_filename,
            "output_path": output_path,
            "character_count": len(cleaned_text),
            "word_count": len(cleaned_text.split()),
            "paragraph_count": len(paragraphs),
            "preview": cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text,
        }


# Singleton instance
pdf_service = PDFService()
