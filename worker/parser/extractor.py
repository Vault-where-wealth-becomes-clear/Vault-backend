from worker.parser.pdf_extractor import extract_text_from_pdf
from worker.parser.xlsx_extractor import extract_text_from_xlsx


def extract_text(file_bytes: bytes, s3_key: str) -> str:
    if s3_key.lower().endswith(".xlsx"):
        return extract_text_from_xlsx(file_bytes)
    return extract_text_from_pdf(file_bytes)
