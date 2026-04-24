from __future__ import annotations

from typing import Any


def generate_batch_report_pdf(report_data: dict[str, Any]) -> bytes:
    lines = _build_report_lines(report_data)
    stream = "BT\n/F1 11 Tf\n50 790 Td\n14 TL\n"
    for line in lines:
        stream += f"({_escape_pdf_text(line)}) Tj\nT*\n"
    stream += "ET\n"
    stream_bytes = stream.encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n"
        + stream_bytes
        + b"endstream",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        b"trailer\n"
        + f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return pdf


def _build_report_lines(report_data: dict[str, Any]) -> list[str]:
    batch = report_data["batch"]
    statistics = report_data["statistics"]
    lines = [
        "Batch report",
        f"Batch number: {batch['batch_number']}",
        f"Batch date: {batch['batch_date']}",
        f"Closed: {batch['is_closed']}",
        f"Work center: {batch['work_center_name']}",
        f"Shift: {batch['shift']}",
        f"Team: {batch['team']}",
        f"Nomenclature: {batch['nomenclature']}",
        f"Shift start: {batch['shift_start']}",
        f"Shift end: {batch['shift_end']}",
        "",
        "Statistics",
        f"Total products: {statistics['total_products']}",
        f"Aggregated products: {statistics['aggregated_products']}",
        f"Remaining products: {statistics['remaining_products']}",
        f"Aggregation rate: {statistics['aggregation_rate']}%",
        "",
        "Products",
    ]
    for product in report_data["products"][:30]:
        aggregated = "yes" if product["is_aggregated"] else "no"
        lines.append(f"{product['unique_code']} | aggregated: {aggregated}")
    if len(report_data["products"]) > 30:
        lines.append(f"... and {len(report_data['products']) - 30} more")
    return lines


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
