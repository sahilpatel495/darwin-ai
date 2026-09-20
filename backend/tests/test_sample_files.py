"""Looking inside the sample data: the listing, one download, the zip, and the 404s.

The folder is a tmp_path stand-in rather than the real demo_data/, so these tests do not
break when someone adds or renames a sample file.
"""

from __future__ import annotations

import dataclasses
import io
import zipfile

import pytest
from app import main, sample_files
from fastapi.testclient import TestClient

EMPLOYEES = "emp_id,name\n000123,Asha Rao\n"
SECRET = "this must never leave the folder\n"


@pytest.fixture
def demo(tmp_path, monkeypatch):
    """A demo_data_dir with one CSV, one XLSX, and the things the listing must ignore."""
    folder = tmp_path / "demo"
    (folder / "_clean").mkdir(parents=True)
    (folder / "employees.csv").write_text(EMPLOYEES, encoding="utf-8")
    (folder / "Salary_Register_2025.xlsx").write_bytes(b"PK\x03\x04 pretend spreadsheet")
    (folder / "starters.json").write_text("[]", encoding="utf-8")  # not a data file
    (folder / "README.md").write_text("# Demo data\n", encoding="utf-8")
    (folder / "_clean" / "employees.csv").write_text(SECRET, encoding="utf-8")  # the answer key
    monkeypatch.setattr(sample_files, "settings",
                        dataclasses.replace(sample_files.settings, demo_data_dir=folder))
    return folder


@pytest.fixture
def client():
    return TestClient(main.app)


def test_listing_is_the_data_files_in_the_folder(client, demo):
    listed = client.get("/api/sample/files").json()
    assert [f["name"] for f in listed] == ["Salary_Register_2025.xlsx", "employees.csv"]
    assert [f["kind"] for f in listed] == ["xlsx", "csv"]
    employees = listed[1]
    assert employees["size_bytes"] == len(EMPLOYEES.encode("utf-8"))
    assert "leading zero" in employees["description"]  # the known files explain their mess


def test_unknown_file_names_get_no_description(client, demo):
    (demo / "mystery.csv").write_text("a\n1\n", encoding="utf-8")
    listed = {f["name"]: f["description"] for f in client.get("/api/sample/files").json()}
    assert listed["mystery.csv"] == ""


def test_a_file_downloads_as_an_attachment_with_its_own_bytes(client, demo):
    response = client.get("/api/sample/files/employees.csv")
    assert response.status_code == 200
    assert response.content == EMPLOYEES.encode("utf-8")
    assert "attachment" in response.headers["content-disposition"]
    assert "employees.csv" in response.headers["content-disposition"]


@pytest.mark.parametrize("name", ["../.env", "..%2F.env", "/etc/passwd", "_clean/employees.csv",
                                  "..\\.env", "nosuchfile.csv"])
def test_anything_but_an_exact_listed_name_is_a_human_404(client, demo, name):
    response = client.get(f"/api/sample/files/{name}")
    assert response.status_code == 404
    assert set(response.json()) == {"message", "next_step"}
    assert SECRET not in response.text


def test_zip_holds_exactly_the_listed_files_and_the_readme(client, demo):
    response = client.get("/api/sample/download")
    assert response.status_code == 200
    assert "verity-sample-hr-data.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["README.md", "Salary_Register_2025.xlsx", "employees.csv"]
        assert archive.read("employees.csv") == EMPLOYEES.encode("utf-8")


def test_a_missing_folder_is_an_empty_list_and_an_empty_zip(client, demo, monkeypatch):
    monkeypatch.setattr(sample_files, "settings",
                        dataclasses.replace(sample_files.settings, demo_data_dir=demo / "gone"))
    assert client.get("/api/sample/files").json() == []
    with zipfile.ZipFile(io.BytesIO(client.get("/api/sample/download").content)) as archive:
        assert archive.namelist() == []
