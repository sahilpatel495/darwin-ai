"""Security review, upload parsers: a small hostile file must cost bounded memory and end in a
sentence. Each workbook here is an honest one whose sheet XML was swapped inside the zip, which
is how such files are made."""

import zipfile
from pathlib import Path

import openpyxl
import pytest

from app.ingest import readers
from app.ingest.errors import IngestError
from app.ingest.readers import MAX_CELL_CHARS, read_raw_tables

SHEET = "xl/worksheets/sheet1.xml"


def _workbook_with(tmp_path: Path, name: str, change) -> Path:
    """An .xlsx with one data cell, PLACEHOLDER, whose sheet XML is passed through `change`."""
    seed = tmp_path / "seed.xlsx"
    book = openpyxl.Workbook()
    book.active.append(["emp_id", "note"])
    book.active.append(["E1", "PLACEHOLDER"])
    book.save(seed)
    out = tmp_path / name
    with zipfile.ZipFile(seed) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            target.writestr(item, change(data) if item.filename == SHEET else data)
    return out


def _with_doctype(doctype: bytes, entity: bytes):
    return lambda xml: b'<?xml version="1.0"?>' + doctype + xml.replace(b"PLACEHOLDER", entity)


def test_a_tiny_workbook_that_unpacks_to_one_huge_cell_is_refused_before_it_is_opened(tmp_path, monkeypatch):
    path = _workbook_with(tmp_path, "bomb.xlsx", lambda xml: xml.replace(b"PLACEHOLDER", b"A" * 5_000_000))
    assert path.stat().st_size < 50_000  # 5 MB of cell in a few kilobytes of upload
    monkeypatch.setattr(readers, "MAX_UNZIPPED_BYTES", 1_000_000)
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **k: pytest.fail("the workbook was opened"))
    with pytest.raises(IngestError, match="too large to open safely"):
        read_raw_tables(path, "bomb.xlsx")


def test_the_unpacked_allowance_follows_the_upload_cap_of_the_host():
    assert readers.MAX_UNZIPPED_BYTES == 8 * readers.settings.max_upload_mb * 1024 * 1024


@pytest.mark.parametrize("name", ["long.xlsx", "long.csv"])
def test_a_cell_longer_than_excel_allows_is_refused_by_name(tmp_path, name):
    cell = "A" * (MAX_CELL_CHARS + 1)
    if name.endswith(".csv"):
        path = tmp_path / name
        path.write_text(f"emp_id,note\nE1,{cell}\n", encoding="utf-8")
    else:
        path = _workbook_with(tmp_path, name, lambda xml: xml.replace(b"PLACEHOLDER", cell.encode()))
    with pytest.raises(IngestError, match="more than 32,767 characters"):
        read_raw_tables(path, name)


def test_a_cell_of_exactly_the_excel_limit_is_read(tmp_path):
    path = tmp_path / "edge.csv"
    path.write_text("emp_id,note\nE1," + "A" * MAX_CELL_CHARS + "\n", encoding="utf-8")
    assert len(read_raw_tables(path, "edge.csv")[0].grid[1][1]) == MAX_CELL_CHARS


def test_xml_entity_expansion_is_refused_not_expanded(tmp_path):
    entities = b"".join(b'<!ENTITY l%d "%s">' % (i, b"&l%d;" % (i - 1) * 10) for i in range(1, 9))
    doctype = b'<!DOCTYPE lolz [<!ENTITY l0 "lolololololololol">' + entities + b"]>"
    path = _workbook_with(tmp_path, "laughs.xlsx", _with_doctype(doctype, b"&l8;"))
    with pytest.raises(IngestError, match="could not be opened"):
        read_raw_tables(path, "laughs.xlsx")


def test_an_external_entity_cannot_read_a_server_file(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-SERVER-FILE", encoding="utf-8")
    doctype = b'<!DOCTYPE x [<!ENTITY xxe SYSTEM "file://' + str(secret).encode() + b'">]>'
    path = _workbook_with(tmp_path, "xxe.xlsx", _with_doctype(doctype, b"&xxe;"))
    try:
        cells = [cell for table in read_raw_tables(path, "xxe.xlsx") for row in table.grid for cell in row]
    except IngestError as refused:
        cells = [str(refused)]
    assert not any("TOP-SECRET" in (cell or "") for cell in cells)


def test_a_zip_that_is_not_a_workbook_is_refused_with_a_sentence(tmp_path):
    path = tmp_path / "notes.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "not a workbook")
    with pytest.raises(IngestError, match="could not be opened") as caught:
        read_raw_tables(path, "notes.xlsx")
    assert "Traceback" not in str(caught.value) and str(tmp_path) not in str(caught.value)
