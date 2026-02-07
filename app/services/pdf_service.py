"""PDF text extraction and cleanup service."""

import re
import unicodedata
from collections import Counter

import fitz  # PyMuPDF


class PDFService:
    """Service for extracting and cleaning text from PDFs."""

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
        text = unicodedata.normalize("NFKC", text)

        replacements = {
            # Quotes
            "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
            "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
            "\u00ab": '"', "\u00bb": '"',
            # Dashes
            "\u2014": "-", "\u2013": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
            # Spaces
            "\u00a0": " ", "\u2002": " ", "\u2003": " ", "\u2009": " ",
            "\u200b": "", "\ufeff": "",
            # Bullets
            "\u2022": "-", "\u00b7": "-", "\u25cf": "-", "\u25cb": "-",
            "\u25a0": "-", "\u25a1": "-", "\u25aa": "-", "\u25ab": "-",
            "\u25ba": "-", "\u25b8": "-", "\u2023": "-",
            # Ellipsis
            "\u2026": "...",
            # Math symbols
            "\u00d7": "x", "\u00f7": "/",
            # Other
            "\u2122": "", "\u00ae": "", "\u00a9": "",
            "\u00b0": " degrees ",
            "\u20ac": "EUR ", "\u00a3": "GBP ", "\u00a5": "JPY ",
            "\u00bd": "1/2", "\u00bc": "1/4", "\u00be": "3/4",
            "\u00b2": "2", "\u00b3": "3",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _remove_headers_footers(self, text: str) -> str:
        """Remove repetitive headers and footers."""
        lines = text.split("\n")

        if len(lines) < 20:
            return text

        line_counts = Counter(line.strip() for line in lines if line.strip())
        threshold = max(3, len(lines) // 50)

        repeated_lines = {
            line for line, count in line_counts.items()
            if count >= threshold and len(line) < 100
        }

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
            if stripped.isdigit():
                continue
            if re.match(r"^(page\s*)?\d+(\s*of\s*\d+)?$", stripped, re.IGNORECASE):
                continue
            if re.match(r"^-\s*\d+\s*-$", stripped):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _fix_hyphenated_words(self, text: str) -> str:
        """Rejoin words split by hyphens at line breaks."""
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
        return text

    def _clean_whitespace(self, text: str) -> str:
        """Normalize all whitespace."""
        text = text.replace("\t", " ")
        text = re.sub(r" +", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text

    def _remove_special_patterns(self, text: str) -> str:
        """Remove URLs, emails, file paths, and document artifacts."""
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"www\.\S+", "", text)
        text = re.sub(r"\S+@\S+\.\S+", "", text)
        text = re.sub(r"[A-Za-z]:\\[\w\\]+", "", text)
        text = re.sub(r"/[\w/]+\.\w+", "", text)
        text = re.sub(r"\[?\d+\]", "", text)
        text = re.sub(r"fig(ure)?\.?\s*\d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"table\s*\d+", "", text, flags=re.IGNORECASE)
        return text

    def _remove_short_lines(self, text: str, min_length: int = 3) -> str:
        """Remove very short lines that are likely artifacts."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or len(stripped) >= min_length:
                if stripped and re.match(r"^[\W\d]+$", stripped):
                    continue
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _normalize_sentences(self, text: str) -> str:
        """Normalize sentence structure."""
        text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)
        text = re.sub(r",([A-Za-z])", r", \1", text)
        text = re.sub(r"([.!?]){2,}", r"\1", text)
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
                if current_paragraph:
                    result.append(" ".join(current_paragraph))
                    current_paragraph = []
                continue

            if current_paragraph:
                prev_line = current_paragraph[-1]
                if not re.search(r"[.!?:]\s*$", prev_line):
                    current_paragraph.append(stripped)
                    continue

            if current_paragraph:
                result.append(" ".join(current_paragraph))
            current_paragraph = [stripped]

        if current_paragraph:
            result.append(" ".join(current_paragraph))

        return "\n\n".join(result)

    def cleanup_text(self, text: str) -> str:
        """
        Clean up extracted PDF text through a multi-step pipeline:
        unicode normalization → hyphen fix → header/footer removal →
        page numbers → special patterns → whitespace → short lines →
        sentence normalization → paragraph joining.
        """
        text = self._normalize_unicode(text)
        text = self._fix_hyphenated_words(text)
        text = self._remove_headers_footers(text)
        text = self._remove_page_numbers(text)
        text = self._remove_special_patterns(text)
        text = self._clean_whitespace(text)
        text = self._remove_short_lines(text)
        text = self._normalize_sentences(text)
        text = self._join_broken_paragraphs(text)
        text = self._clean_whitespace(text)
        return text


# Singleton instance
pdf_service = PDFService()
