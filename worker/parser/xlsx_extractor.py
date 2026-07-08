import io

import openpyxl

_MAX_ROWS = 2000


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines: list[str] = []
    row_count = 0
    for sheet in workbook.worksheets:
        sheet_header_added = False
        for row in sheet.iter_rows(values_only=True):
            if not any(cell is not None for cell in row):
                continue
            if not sheet_header_added:
                # Marca de qué hoja viene cada fila — sin esto, un reporte multi-hoja
                # (ej. Renta Financiera: Boletos, Resultado Ventas, Rentas y Dividendos,
                # Resultado cauciones) queda como texto plano indistinguible entre hojas.
                lines.append(f"=== Hoja: {sheet.title} ===")
                sheet_header_added = True
            lines.append(" | ".join(str(cell) for cell in row if cell is not None))
            row_count += 1
            if row_count >= _MAX_ROWS:
                lines.append(
                    f"[truncado: el archivo supera {_MAX_ROWS} filas — procesando solo las primeras]"
                )
                return "\n".join(lines)
    return "\n".join(lines)
