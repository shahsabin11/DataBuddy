"""Upload content checks: size, type, CSV/XLSX injection, macros."""

from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook

from app.upload_validation import (
    UploadValidationError,
    assert_size_allowed,
    validate_upload,
)

MAX = 500 * 1024 * 1024


def test_oversize_rejected():
    with pytest.raises(UploadValidationError) as exc:
        assert_size_allowed(MAX + 1, MAX)
    assert exc.value.code == "file_too_large"

    with pytest.raises(UploadValidationError) as exc2:
        validate_upload(b"x" * 10, filename="a.csv", max_bytes=5)
    assert exc2.value.code == "file_too_large"


def test_wrong_type_rejected():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    with pytest.raises(UploadValidationError) as exc:
        validate_upload(png, filename="chart.png", max_bytes=MAX)
    assert exc.value.code == "invalid_type"

    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32
    with pytest.raises(UploadValidationError) as exc2:
        validate_upload(ole, filename="old.xls", max_bytes=MAX)
    assert exc2.value.code == "invalid_type"


@pytest.mark.parametrize(
    "cell",
    ["=1+1", "+2", "-3", "@SUM(A1)", "\t=CMD|'/c calc'!A0"],
)
def test_csv_formula_injection_rejected(cell: str):
    data = f"name,value\nalice,{cell}\n".encode()
    with pytest.raises(UploadValidationError) as exc:
        validate_upload(data, filename="bad.csv", max_bytes=MAX)
    assert exc.value.code == "formula_injection"


def test_clean_csv_accepted():
    data = b"name,score\nalice,10\nbob,12\n"
    result = validate_upload(data, filename="scores.csv", max_bytes=MAX)
    assert result.kind == "csv"
    assert result.row_count == 3
    assert result.column_count == 2


def _xlsx_bytes(rows: list[list[object]], *, with_macro: bool = False) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    raw = buf.getvalue()
    if not with_macro:
        return raw
    # Inject a fake VBA project entry into the zip.
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as src, zipfile.ZipFile(
        out, "w"
    ) as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename))
        dst.writestr("xl/vbaProject.bin", b"fake-vba")
    return out.getvalue()


def test_xlsx_formula_injection_rejected():
    data = _xlsx_bytes([["name", "value"], ["alice", "=1+2"]])
    with pytest.raises(UploadValidationError) as exc:
        validate_upload(data, filename="bad.xlsx", max_bytes=MAX)
    assert exc.value.code == "formula_injection"


def test_xlsx_macros_rejected():
    data = _xlsx_bytes([["a", "b"], [1, 2]], with_macro=True)
    with pytest.raises(UploadValidationError) as exc:
        validate_upload(data, filename="macro.xlsx", max_bytes=MAX)
    assert exc.value.code == "macros_forbidden"


def test_clean_xlsx_accepted():
    data = _xlsx_bytes([["name", "score"], ["alice", 10], ["bob", 12]])
    result = validate_upload(data, filename="scores.xlsx", max_bytes=MAX)
    assert result.kind == "xlsx"
    assert result.row_count >= 3
