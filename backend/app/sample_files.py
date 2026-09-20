"""Let a visitor look inside the sample HR data before they load it.

The UI offers "Try with sample HR data" but nothing shows what is in those files, so the
demo asks for trust it has not earned yet. These routes list the files, hand over one, or
zip the lot with the README that explains every defect we planted.

The folder is on the server and the file name comes from the browser, so the only safe
lookup is an exact match against the listing: no path is ever built from user text.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

from app.config import settings
from app.contracts import ErrorResponse

router = APIRouter(prefix="/api/sample", tags=["sample"])

ZIP_NAME = "darwinlens-sample-hr-data.zip"

# One plain sentence per file, saying what it is and where it is deliberately messy
# (demo_data/README.md has the full list). A file nobody has described gets "".
DESCRIPTIONS: dict[str, str] = {
    "employees.csv": "500 employees past and present, straight out of an HRMS: IDs keep their "
    "leading zeros, dates are day-first like 21/06/2022, some locations end in a stray space, "
    "and blanks are written as NA or -.",
    "Salary_Register_2025.xlsx": "Every 2025 payslip plus a Bonuses sheet, buried under three "
    "merged title rows, with pay written as text like ₹1,20,000, six payslips exported twice, "
    "and a Grand Total line at the bottom.",
    "attendance_q1.csv": "Attendance for January to March 2025; same columns as attendance_q2.csv, "
    "so the two are meant to be read as one table.",
    "attendance_q2.csv": "Attendance for April to June 2025; the other half of attendance_q1.csv.",
    "performance_reviews.xlsx": "Two 2025 review cycles rated 1 to 5, where the employee column is "
    "called Employee ID and ten reviews say Not Rated instead of a number.",
    "sales.csv": "800 product orders with nothing to do with HR, to show DarwinLens is not wired "
    "to HR data in particular.",
}


def _data_files() -> list[Path]:
    """The files the sample loads: .csv and .xlsx directly in the folder.

    Same rule as Session.load_sample, so the listing cannot promise a file the demo skips,
    and _clean/ (the answer key) stays out of reach.
    """
    folder = settings.demo_data_dir
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in (".csv", ".xlsx")
                  and not p.name.startswith(("~$", ".")))


def _not_found() -> JSONResponse:
    """The app's human error shape, built here rather than imported: app.main imports this
    module, so importing its _problem back would be a cycle. Nothing of the request is
    echoed, so a crafted name cannot be reflected at the visitor."""
    return JSONResponse(ErrorResponse(
        message="There is no sample file by that name.",
        next_step="Open /api/sample/files to see which sample files you can download.",
    ).model_dump(), status_code=404)


@router.get("/files")
def list_sample_files() -> list[dict[str, str | int]]:
    """What is in the sample, with sizes, so nobody has to download to find out."""
    return [{"name": p.name, "size_bytes": p.stat().st_size, "kind": p.suffix.lower().lstrip("."),
             "description": DESCRIPTIONS.get(p.name, "")} for p in _data_files()]


@router.get("/download")
def download_all() -> Response:
    """All of it as one zip, README included: the mess only makes sense with its explanation.

    Rebuilt per request because the files total well under a megabyte; a cache would cost
    more code than it saves, and would go stale when the data is regenerated.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in _data_files():
            archive.write(path, path.name)
        readme = settings.demo_data_dir / "README.md"
        if readme.is_file():
            archive.write(readme, readme.name)
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{ZIP_NAME}"'})


@router.get("/files/{name:path}")
def download_sample_file(name: str) -> Response:
    """One file, by the exact name the listing gave. `:path` so that a name carrying a
    slash ("_clean/employees.csv", "/etc/passwd") reaches this route and is refused here,
    instead of falling through to the single-page app."""
    match = next((p for p in _data_files() if p.name == name), None)
    if match is None:
        return _not_found()
    return FileResponse(match, filename=match.name, media_type="application/octet-stream")


@router.get("/{rest:path}", include_in_schema=False)
def unknown_sample_path(rest: str) -> JSONResponse:
    """Anything else under /api/sample. A browser or client collapses "files/../.env" to
    ".env" before it is sent, and without this the app's catch-all would answer that
    traversal attempt with index.html and a 200."""
    return _not_found()
