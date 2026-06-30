import io

import openpyxl

_MAX_ROWS = 150


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                lines.append(" | ".join(str(cell) for cell in row if cell is not None))
                if len(lines) >= _MAX_ROWS:
                    lines.append(
                        f"[truncado: el extracto supera {_MAX_ROWS} filas — procesando solo las primeras]"
                    )
                    return "\n".join(lines)
    return "\n".join(lines)
