"""Six downloadable worlds for hand-testing DarwinLens, each a small self-contained pack.

Run from the repo root:
    uv run python test_files/packs/generate_packs.py          # write the packs and the zips
    PYTHONPATH=backend:. uv run python test_files/packs/generate_packs.py --check

Why. `demo_data/` is the golden set the eval scores against and `test_files/` is the second
messy HR set. Both are HR, both have been looked at a hundred times. These packs carry
columns neither set has (requisitions, leave balances, course enrolments, insurance
dependants, SKUs, OKRs) so an owner can drop a folder on the upload box and meet the
product cold, the way a stranger would.

Same two layers as `test_files/generate.py`, for the same reason: clean pandas frames
first, then the messy exports cut from them, and `EXPECTED.md` computed from the clean
frames with pandas. Expected answers taken from the app's own ingestion would agree with
the app's own bugs and prove nothing.

Everything is fictional and looks it: @example.com addresses, 555-01xx phone numbers,
invented company and people names.

Seeded, and the .xlsx files are written with fixed zip timestamps, so two runs produce
byte-identical files and `git status` stays quiet when nothing has changed.
"""

from __future__ import annotations

import csv
import io
import random
import re
import sys
import zipfile
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

SEED = 21
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_DOC_TIME = datetime(2026, 1, 5, 9, 0, 0)  # noqa: DTZ001 - a workbook property has no time zone

FIRST = ["Aarav", "Aditi", "Bhavya", "Chirag", "Devika", "Eshan", "Farida", "Gaurav", "Hiral",
         "Ishaan", "Jagriti", "Kabir", "Lavanya", "Mehul", "Nandini", "Omkar", "Prisha",
         "Qadir", "Rhea", "Sarthak", "Tanvi", "Udit", "Vaishali", "Yash", "Zara"]
LAST = ["Ahuja", "Barua", "Chandran", "Dixit", "Engineer", "Fernandes", "Ghosh", "Hegde",
        "Iyengar", "Joshi", "Kamath", "Lobo", "Mistry", "Nadkarni", "Oberoi", "Pillai",
        "Quadri", "Raman", "Sodhi", "Trivedi", "Ubale", "Vaidya", "Wadhwa", "Yadav"]
DEPARTMENTS = ["Sales", "Engineering", "Operations", "Finance", "Customer Success", "Marketing"]


# ---------------------------------------------------------------- shared writers


def inr(amount: float) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567. Copied from test_files/generate.py:
    both are scripts, not packages, and the older set must not change when this one does."""
    digits = f"{abs(round(amount)):d}"
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while head:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return ("-" if amount < 0 else "") + ",".join(pairs + [tail])


def _write_csv(path: Path, rows: list[list], encoding: str = "utf-8", delimiter: str = ",") -> None:
    with path.open("w", encoding=encoding, newline="") as handle:
        csv.writer(handle, delimiter=delimiter).writerows(rows)


def _save_workbook(book: Workbook, path: Path) -> None:
    """Save an .xlsx whose bytes depend only on its cells, so reruns are byte-identical."""
    book.properties.created = FIXED_DOC_TIME
    buffer = io.BytesIO()
    book.save(buffer)
    stamp = ('<dcterms:modified xsi:type="dcterms:W3CDTF">'
             f"{FIXED_DOC_TIME:%Y-%m-%dT%H:%M:%SZ}</dcterms:modified>")
    with zipfile.ZipFile(buffer) as source, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = re.sub(rb"<dcterms:modified[^>]*>.*?</dcterms:modified>", stamp.encode(), data)
            info = zipfile.ZipInfo(item.filename, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = item.external_attr
            out.writestr(info, data)


def _write_vendor_csv(path: Path, rows: list[list]) -> None:
    """The shape an old vendor system exports: semicolons and Windows-1252. cp1252 has no
    rupee sign, so these files write "Rs." with a non-breaking space (0xA0) - the byte that
    makes the file fail to decode as UTF-8 and forces the reader to fall back."""
    _write_csv(path, rows, encoding="cp1252", delimiter=";")


def rs(amount: float, paise: bool = True) -> str:
    return f"Rs. {inr(amount)}" + (".00" if paise else "")


def _sheet(book: Workbook, title: str, rows: list[list], first: bool = False):
    sheet = book.active if first else book.create_sheet()
    sheet.title = title
    for row in rows:
        sheet.append(row)
    return sheet


def dmy(d: date) -> str:
    return f"{d:%d-%m-%Y}"


def mdy(d: date) -> str:
    return f"{d:%m/%d/%Y}"


def iso(d: date) -> str:
    return f"{d:%Y-%m-%d}"


def longdate(d: date) -> str:
    return f"{d.day} {d:%b %Y}"  # "3 Mar 2025"


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def email(name: str, n: int) -> str:
    return f"{name.lower().replace(' ', '.')}{n}@example.com"


def phone(rng: random.Random) -> str:
    return f"+1-555-01{rng.randrange(10, 100)}"


def case_variant(rng: random.Random, value: str) -> str:
    """The same category typed four ways, as four different people typed it."""
    return rng.choice([value, value, value.lower() + " ", value.upper(), " " + value])


def blankish(rng: random.Random, value: object, odds: float = 0.06) -> object:
    """A gap, written the way a spreadsheet writes gaps: empty, N/A or a dash."""
    return rng.choice(["", "N/A", "-"]) if rng.random() < odds else value


def days(start: date, count: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(count)]


# ---------------------------------------------------------------- 1. recruitment


def build_recruitment(rng: random.Random) -> dict[str, pd.DataFrame]:
    reqs = []
    for i in range(40):
        opened = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 150))
        reqs.append({
            "req_id": f"{4500 + i * 7:06d}",  # leading zeros: "004500", and must stay text
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "hiring_manager": person(rng),
            "opened_on": opened,
            "target_close": opened + timedelta(days=rng.choice([45, 60, 90])),
            "budgeted_ctc": rng.randrange(6, 42) * 100_000,
            "status": rng.choices(["Open", "Closed", "On Hold"], [55, 35, 10])[0],
        })
    sources = ["Referral", "Job Board", "Agency", "Campus", "LinkedIn"]
    stages = ["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]
    candidates = []
    for i in range(420):
        applied = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 360))
        name = person(rng)
        candidates.append({
            "candidate_id": f"C{9000 + i}",
            "req_id": reqs[rng.randrange(len(reqs))]["req_id"],
            "source": rng.choices(sources, [30, 25, 15, 15, 15])[0],
            "applied_on": applied,
            "current_stage": rng.choices(stages, [20, 20, 20, 10, 12, 18])[0],
            "expected_ctc": rng.randrange(5, 40) * 100_000,
            "email": email(name, i),
            "phone": phone(rng),
            "half": "H1" if applied.month <= 6 else "H2",
        })
    interviews = []
    for n, cand in enumerate(c for c in candidates if c["current_stage"] in
                             {"Interview", "Offer", "Hired", "Rejected"}):
        for rnd in range(1, rng.randrange(2, 4)):
            interviews.append({
                "interview_id": f"IV{3000 + len(interviews)}",
                "candidate_id": cand["candidate_id"],
                "round": ["Screening", "Technical", "Manager"][rnd - 1],
                "interviewer": person(rng),
                "scheduled_at": cand["applied_on"] + timedelta(days=7 * rnd),
                "score_out_of_10": rng.randrange(3, 10),
                "outcome": rng.choices(["Pass", "Fail", "No Show"], [60, 32, 8])[0],
            })
        del n
    offers = []
    for cand in [c for c in candidates if c["current_stage"] in {"Offer", "Hired"}]:
        offered = round(cand["expected_ctc"] * rng.uniform(0.9, 1.15) / 10_000) * 10_000
        offer_date = cand["applied_on"] + timedelta(days=rng.randrange(25, 60))
        accepted = cand["current_stage"] == "Hired"
        offers.append({
            "offer_id": f"OF{700 + len(offers)}",
            "candidate_id": cand["candidate_id"],
            "offered_ctc": offered,
            "offer_date": offer_date,
            "accepted": accepted,
            "joining_date": offer_date + timedelta(days=rng.choice([30, 45, 60])) if accepted else None,
        })
    recruiters = [{"recruiter_id": f"REC{10 + i}", "recruiter_name": person(rng),
                   "desk": DEPARTMENTS[i % len(DEPARTMENTS)],
                   "office": rng.choice(["Pune Campus", "Bengaluru HQ", "Remote"]),
                   "open_reqs": rng.randrange(2, 9),
                   "joined_ta_on": date(2021, 1, 1) + timedelta(days=rng.randrange(0, 1400))}
                  for i in range(12)]
    spend = [{"channel": ch, "month": date(2025, m, 1), "spend": rng.randrange(20, 180) * 1000,
              "applications": rng.randrange(20, 400)}
             for ch in ("Job Board", "Agency", "Campus", "LinkedIn", "Referral Bonus")
             for m in range(1, 7)]
    return {name: pd.DataFrame(rows) for name, rows in
            [("requisitions", reqs), ("candidates", candidates),
             ("interviews", interviews), ("offers", offers),
             ("recruiters", recruiters), ("spend", spend)]}


def write_recruitment(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    reqs = clean["requisitions"]
    rows = [["Hirewell Talent Acquisition - Open Requisitions FY25", None, None, None, None, None, None, None],
            ["Extracted 12-07-2025 by TA Ops", None, None, None, None, None, None, None],
            ["Requisition ID", "Department", "Hiring Manager", "Opened On", "Target Close",
             "Budgeted CTC", "Status", "Recruiter Notes"]]
    for r in reqs.itertuples():
        rows.append([r.req_id, case_variant(rng, r.department), r.hiring_manager, dmy(r.opened_on),
                     blankish(rng, dmy(r.target_close)), f"Rs. {inr(r.budgeted_ctc)}", r.status, ""])
    rows.append(["Total", None, None, None, None, f"Rs. {inr(int(reqs.budgeted_ctc.sum()))}", None, None])
    _write_csv(out / "requisitions.csv", rows)

    book = Workbook()
    header = ["candidate_id", "req_id", "source", "applied_on", "current_stage",
              "expected_ctc", "email", "phone"]
    for n, half in enumerate(("H1", "H2")):
        part = clean["candidates"][clean["candidates"].half == half]
        rows = [header]
        for c in part.itertuples():
            rows.append([c.candidate_id, c.req_id, case_variant(rng, c.source), iso(c.applied_on),
                         c.current_stage, c.expected_ctc, c.email, c.phone])
        if half == "H2":  # a recruiter pasted the same three applications in twice
            rows += rows[1:4]
            # and one application quotes a requisition that was deleted before it landed
            rows.append(["C9999", "009999", "Agency", "2025-11-14", "Screening", 1_800_000,
                         "orphan.applicant@example.com", "+1-555-0199"])
        _sheet(book, f"Applied 2025 {half}", rows, first=n == 0)
    _save_workbook(book, out / "candidates.xlsx")

    rows = [["interview_id", "candidate_id", "round", "interviewer", "scheduled_at",
             "score_out_of_10", "outcome"]]
    for i in clean["interviews"].itertuples():
        rows.append([i.interview_id, i.candidate_id, i.round, i.interviewer,
                     longdate(i.scheduled_at), blankish(rng, i.score_out_of_10, 0.05), i.outcome])
    _write_csv(out / "interviews.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    rows = [["offer_id", "candidate_id", "offered_ctc", "offer_date", "accepted", "joining_date"]]
    for o in clean["offers"].itertuples():
        rows.append([o.offer_id, o.candidate_id, f"₹{inr(o.offered_ctc)}", dmy(o.offer_date),
                     "Yes" if o.accepted else rng.choice(["No", "-"]),
                     dmy(o.joining_date) if o.joining_date is not None and not pd.isna(o.joining_date) else "N/A"])
    _write_csv(out / "offers.csv", rows)

    rows = [["recruiter_id", "recruiter_name", "desk", "office", "open_reqs", "joined_ta_on"]]
    for r in clean["recruiters"].itertuples():
        rows.append([r.recruiter_id, r.recruiter_name, case_variant(rng, r.desk), r.office,
                     r.open_reqs, mdy(r.joined_ta_on)])  # US-style dates in this file only
    _write_csv(out / "recruiters.csv", rows)

    spend = clean["spend"]
    rows = [["Sourcing Channel Spend - Jan to Jun 2025", None, None, None],
            ["channel", "month", "spend", "applications"]]
    for s in spend.itertuples():
        rows.append([s.channel, f"{s.month:%b-%Y}", rs(s.spend), s.applications])
    rows.append(["Total", None, rs(int(spend.spend.sum())), int(spend.applications.sum())])
    _write_vendor_csv(out / "job_boards_spend.csv", rows)


def answers_recruitment(c: dict[str, pd.DataFrame]) -> list[dict]:
    reqs, cand, iv, off = c["requisitions"], c["candidates"], c["interviews"], c["offers"]
    by_source = cand.source.value_counts()
    dept = cand.merge(reqs[["req_id", "department"]], on="req_id").department.value_counts()
    rounds = iv.groupby("round").score_out_of_10.mean().round(2).sort_index()
    accepted = off[off.accepted]
    return [
        {"q": "How many requisitions are still open?",
         "a": f"{int((reqs.status == 'Open').sum())} of {len(reqs)} requisitions.",
         "files": "requisitions.csv",
         "trap": "Two title rows above the header and a Total footer row. Counted in, the file has 43 rows."},
        {"q": "What is the total budgeted CTC across all requisitions?",
         "a": f"Rs. {inr(int(reqs.budgeted_ctc.sum()))} over {len(reqs)} requisitions.",
         "files": "requisitions.csv",
         "trap": "Footer double count: the Total row already holds this number, so a naive sum doubles it. "
                 "Amounts are text ('Rs. 12,50,000')."},
        {"q": "How many candidates applied in 2025?",
         "a": f"{len(cand)} real applications ({int((cand.half == 'H1').sum())} in H1, "
              f"{int((cand.half == 'H2').sum())} in H2). The file carries 424 rows: 3 pasted duplicates "
              "and 1 orphan row on top.",
         "files": "candidates.xlsx (both sheets)",
         "trap": "Two sheets with identical columns must combine, then duplicates must be dropped."},
        {"q": "Which source brought the most candidates?",
         "a": "\n".join(f"{n}. {k} {v}" for n, (k, v) in enumerate(by_source.items(), 1)),
         "files": "candidates.xlsx",
         "trap": "Spelling variants: 'Referral', 'referral ' and 'REFERRAL' are one source. Order matters."},
        {"q": "What is the average interview score by round?",
         "a": "\n".join(f"- {k}: {v}" for k, v in rounds.items()),
         "files": "interviews.csv",
         "trap": "Scores have 'N/A' and '-' gaps that must be skipped, not read as zero. "
                 "Dates are '3 Mar 2025' style. The file has a UTF-8 BOM."},
        {"q": "Which department received the most candidates?",
         "a": "\n".join(f"{n}. {k} {v}" for n, (k, v) in enumerate(dept.items(), 1)),
         "files": "candidates.xlsx + requisitions.csv",
         "trap": "Cross-file. The key is 'Requisition ID' in one file and 'req_id' in the other, and one "
                 "candidate points at requisition 009999, which does not exist."},
        {"q": "How many offers were accepted, and what was the average accepted CTC?",
         "a": f"{len(accepted)} accepted of {len(off)} offers ({len(accepted) / len(off):.0%}), "
              f"average accepted CTC Rs. {inr(int(round(accepted.offered_ctc.mean())))}.",
         "files": "offers.csv",
         "trap": "'accepted' holds Yes / No / '-', and joining_date holds 'N/A' for every declined offer."},
        {"q": "For candidates who got an offer, how did the offer compare with what they expected?",
         "a": f"Average expected Rs. {inr(int(round(cand[cand.candidate_id.isin(off.candidate_id)].expected_ctc.mean())))}, "
              f"average offered Rs. {inr(int(round(off.offered_ctc.mean())))}.",
         "files": "candidates.xlsx + offers.csv",
         "trap": "Cross-file on candidate_id, with currency text on both sides."},
        {"q": "What did we spend on sourcing, and what did each application cost?",
         "a": f"Rs. {inr(int(c['spend'].spend.sum()))} for {int(c['spend'].applications.sum())} "
              f"applications, Rs. {inr(int(round(c['spend'].spend.sum() / c['spend'].applications.sum())))} "
              "per application.\n" + "\n".join(
                  f"- {k}: Rs. {inr(int(v))}" for k, v in
                  c["spend"].groupby("channel").spend.sum().sort_values(ascending=False).items()),
         "files": "job_boards_spend.csv",
         "trap": "Semicolon-separated, Windows-1252, a title row and a Total footer. Amounts are "
                 "'Rs. 1,20,000.00' with a non-breaking space."},
        {"q": "How many strong candidates do we have?",
         "a": "CLARIFY. 'Strong' is not in the data. The app should ask what to use - interview score "
              "above a threshold, stage reached, or offer made - and not guess.",
         "files": "-", "trap": "Ambiguous term."},
        {"q": "How many candidates will we hire next quarter?",
         "a": "REFUSE. This is a forecast; the files hold no future data. Also try 'What is each "
              "candidate's notice period?' - there is no such column.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- 2. leave_and_shifts


def build_leave(rng: random.Random) -> dict[str, pd.DataFrame]:
    sites = ["Pune Campus", "Bengaluru HQ", "Remote", "Chennai Plant"]
    employees = []
    for i in range(120):
        name = person(rng)
        employees.append({
            "emp_code": f"{4000 + i * 3:06d}",
            "full_name": name,
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "reporting_manager": person(rng),
            "work_email": email(name, i),
            "date_of_joining": date(2018, 1, 1) + timedelta(days=rng.randrange(0, 2500)),
            "site": sites[i % len(sites)],
        })
    types = ["Earned Leave", "Sick Leave", "Casual Leave", "Comp Off", "Unpaid Leave"]
    requests = []
    for i in range(500):
        emp = employees[rng.randrange(len(employees))]
        start = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 270))
        length = rng.choices([1, 2, 3, 5, 7], [45, 25, 15, 10, 5])[0]
        requests.append({
            "request_id": f"LR{5000 + i}",
            "employee_id": emp["emp_code"],
            "leave_type": rng.choices(types, [35, 25, 20, 12, 8])[0],
            "from_date": start,
            "to_date": start + timedelta(days=length - 1),
            "days": length,
            "status": rng.choices(["Approved", "Rejected", "Pending", "Cancelled"], [70, 10, 12, 8])[0],
            "approver": emp["reporting_manager"],
        })
    balances = [{"emp_code": e["emp_code"], "leave_type": t,
                 "opening_balance": {"Earned Leave": 18, "Sick Leave": 12, "Casual Leave": 8}[t],
                 "availed": rng.randrange(0, 9)}
                for e in employees for t in ("Earned Leave", "Sick Leave", "Casual Leave")]
    for b in balances:
        b["closing_balance"] = b["opening_balance"] - b["availed"]
    shifts = ["General", "Morning", "Night", "Week Off"]
    roster = [{"date": day, "employee": e["emp_code"],
               "shift": rng.choices(shifts, [50, 25, 15, 10])[0], "site": e["site"]}
              for day in days(date(2025, 4, 1), 60) for e in employees[:60]]
    holidays = [{"holiday_date": d, "holiday_name": n, "location": loc, "optional": opt} for d, n, loc, opt in [
        (date(2025, 1, 1), "New Year", "All India", False), (date(2025, 1, 14), "Pongal", "Chennai Plant", True),
        (date(2025, 1, 26), "Republic Day", "All India", False), (date(2025, 3, 14), "Holi", "All India", False),
        (date(2025, 3, 31), "Id-ul-Fitr", "All India", False), (date(2025, 4, 14), "Ambedkar Jayanti", "All India", True),
        (date(2025, 5, 1), "Labour Day", "Pune Campus", False), (date(2025, 8, 15), "Independence Day", "All India", False),
        (date(2025, 10, 2), "Gandhi Jayanti", "All India", False), (date(2025, 10, 20), "Diwali", "All India", False),
        (date(2025, 11, 5), "Guru Nanak Jayanti", "All India", True), (date(2025, 12, 25), "Christmas", "All India", False),
    ]]
    site_rows = [{"site": s, "city": city, "seats": seats, "weekly_off": off,
                  "facility_manager": person(rng)}
                 for s, city, seats, off in [("Pune Campus", "Pune", 450, "Sat, Sun"),
                                             ("Bengaluru HQ", "Bengaluru", 800, "Sat, Sun"),
                                             ("Remote", "-", 0, "Sat, Sun"),
                                             ("Chennai Plant", "Chennai", 320, "Sun")]]
    return {name: pd.DataFrame(rows) for name, rows in
            [("employees", employees), ("leave_requests", requests), ("leave_balances", balances),
             ("shift_roster", roster), ("holidays", holidays), ("sites", site_rows)]}


def write_leave(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    rows = [["emp_code", "full_name", "department", "reporting_manager", "work_email",
             "date_of_joining", "site", "middle_name"]]
    for e in clean["employees"].itertuples():
        rows.append([e.emp_code, e.full_name, case_variant(rng, e.department), e.reporting_manager,
                     e.work_email, iso(e.date_of_joining), e.site, ""])  # middle_name: all empty
    _write_csv(out / "employees_lite.csv", rows)

    # The US-style file: this export was built in a spreadsheet defaulted to en-US.
    rows = [["Request ID", "Employee ID", "Leave Type", "From Date", "To Date", "Days",
             "Status", "Approver"]]
    for r in clean["leave_requests"].itertuples():
        rows.append([r.request_id, r.employee_id, case_variant(rng, r.leave_type), mdy(r.from_date),
                     mdy(r.to_date), r.days, r.status, blankish(rng, r.approver, 0.04)])
    rows.append(["LR9999", "009999", "Earned Leave", "12/01/2025", "12/03/2025", 3, "Approved",
                 "Unknown Manager"])  # orphan: no such employee
    rows.append(["Grand Total", None, None, None, None, int(clean["leave_requests"].days.sum()) + 3,
                 None, None])
    _write_csv(out / "leave_requests.csv", rows)

    book = Workbook()  # two sheets, same columns: FY25 and the frozen FY24 statement
    balances = clean["leave_balances"]
    for n, (title, factor) in enumerate((("Balances FY25", 1), ("Balances FY24", 0))):
        rows = [[f"Leave Balance Statement - {title.split()[-1]} - as on 30-09-2025",
                 None, None, None, None],
                ["emp_code", "leave_type", "opening_balance", "availed", "closing_balance"]]
        for b in balances.itertuples():
            availed = b.availed if factor else max(0, b.availed - 2)
            rows.append([b.emp_code, b.leave_type, b.opening_balance, availed,
                         b.opening_balance - availed])
        _sheet(book, title, rows, first=n == 0)
    _save_workbook(book, out / "leave_balances.xlsx")

    rows = [["site", "city", "seats", "weekly_off", "facility_manager"]]
    for s in clean["sites"].itertuples():
        rows.append([s.site, s.city, s.seats, s.weekly_off, s.facility_manager])
    _write_vendor_csv(out / "sites.csv", rows)

    rows = [["date", "employee", "shift", "site"]]
    roster = list(clean["shift_roster"].itertuples())
    for r in roster:
        rows.append([dmy(r.date), r.employee, r.shift, r.site])
    rows += rows[1:41]  # one day double-published by the ops team
    _write_csv(out / "shift_roster.csv", rows)

    rows = [["holiday_date", "holiday_name", "location", "optional"]]
    for h in clean["holidays"].itertuples():
        rows.append([longdate(h.holiday_date), h.holiday_name, h.location, "Yes" if h.optional else "No"])
    _write_csv(out / "holidays.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM


def answers_leave(c: dict[str, pd.DataFrame]) -> list[dict]:
    emp, req, bal, ros, hol = (c["employees"], c["leave_requests"], c["leave_balances"],
                               c["shift_roster"], c["holidays"])
    approved = req[req.status == "Approved"]
    by_type = approved.groupby("leave_type").days.sum().sort_values(ascending=False)
    merged = approved.merge(emp, left_on="employee_id", right_on="emp_code")
    by_dept = merged.groupby("department").days.sum().sort_values(ascending=False)
    top = bal.groupby("emp_code").closing_balance.sum().sort_values(ascending=False)
    night = ros[ros["shift"] == "Night"]  # .shift is a DataFrame method, so index by name
    return [
        {"q": "How many leave days were approved in 2025?",
         "a": f"{int(approved.days.sum())} days across {len(approved)} approved requests.",
         "files": "leave_requests.csv",
         "trap": "A Grand Total footer holds the same number plus the orphan row; counted in, the answer "
                 "roughly doubles. Dates are MM/DD/YYYY in this file only."},
        {"q": "Which leave type is used most?",
         "a": "\n".join(f"{n}. {k} {int(v)} days" for n, (k, v) in enumerate(by_type.items(), 1)),
         "files": "leave_requests.csv",
         "trap": "'Sick Leave', 'sick leave ' and 'SICK LEAVE' are one type. Order matters."},
        {"q": "Which department took the most approved leave?",
         "a": "\n".join(f"{n}. {k} {int(v)} days" for n, (k, v) in enumerate(by_dept.items(), 1)),
         "files": "leave_requests.csv + employees_lite.csv",
         "trap": "Cross-file, and the key has a different name on each side: employee_id vs emp_code. "
                 "One request (LR9999, employee 009999) has no matching employee and must be excluded."},
        {"q": "Who has the highest total leave balance left?",
         "a": "\n".join(f"{n}. {k} {int(v)} days" for n, (k, v) in enumerate(list(top.items())[:5], 1)),
         "files": "leave_balances.xlsx (sheet 'Balances FY25')",
         "trap": "A title row sits above the header, three rows per employee must be summed, and the "
                 "workbook has a second sheet ('Balances FY24') with identical columns. Combining both "
                 "sheets doubles every employee - the FY25 sheet alone is the answer."},
        {"q": "How many night shifts are on the roster?",
         "a": f"{len(night)} night shifts in the roster of {len(ros)} real assignments "
              f"(the file carries {len(ros) + 40} rows: 40 are a duplicated block).",
         "files": "shift_roster.csv",
         "trap": "Duplicated rows. Dates are DD-MM-YYYY here and MM/DD/YYYY in leave_requests.csv."},
        {"q": "How many public holidays are compulsory rather than optional?",
         "a": f"{int((~hol.optional).sum())} compulsory of {len(hol)} holidays.",
         "files": "holidays.csv",
         "trap": "Dates are written '14 Jan 2025'. 'optional' is Yes/No text, not a boolean."},
        {"q": "How many approved leave days fell on a company holiday?",
         "a": "This needs a date range on one side and a single date on the other. Expected: the app "
              "should either expand the range or say it cannot, not silently join from_date to holiday_date.",
         "files": "leave_requests.csv + holidays.csv",
         "trap": "Cross-file with no shared key - a genuine limit, and a good look at how it is explained."},
        {"q": "How many people were absent last month?",
         "a": "CLARIFY. 'Absent' could mean approved leave, a Week Off on the roster, or a missing roster "
              "row, and 'last month' has no anchor in a file that ends in September.",
         "files": "-", "trap": "Ambiguous term plus a floating date range."},
        {"q": "What will our leave liability be in December?",
         "a": "REFUSE. A forecast. Also try 'Show me each employee's leave encashment amount' - there is "
              "no such column.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- 3. learning


def build_learning(rng: random.Random) -> dict[str, pd.DataFrame]:
    cats = ["Compliance", "Leadership", "Technical", "Sales Skills", "Wellbeing"]
    vendors = ["Northlight Academy", "Brightpath Learning", "In-house", "Seaglass Institute"]
    courses = [{
        "course_code": f"CRS-{100 + i:03d}",
        "title": t,
        "category": cats[i % len(cats)],
        "mode": rng.choice(["Online", "Classroom", "Blended"]),
        "duration_hours": rng.choice([2, 4, 8, 16, 24]),
        "vendor": vendors[i % len(vendors)],
        "cost_per_seat": rng.randrange(5, 60) * 500,
    } for i, t in enumerate([
        "POSH Awareness", "Data Privacy Basics", "Anti-Bribery", "First-time Manager",
        "Coaching Conversations", "Difficult Feedback", "SQL for Analysts", "Python Foundations",
        "Cloud Security", "Kubernetes Basics", "Negotiation Skills", "Consultative Selling",
        "Account Planning", "Mindfulness at Work", "Ergonomics", "Financial Wellbeing",
        "Presentation Skills", "Design Thinking", "Incident Response", "Customer Empathy",
        "Time Management", "Business Writing", "Interviewing Skills", "Agile Essentials",
        "Excel Advanced"])]
    emp_codes = [f"{4000 + i * 3:06d}" for i in range(120)]
    enrollments = []
    for i in range(600):
        course = courses[rng.randrange(len(courses))]
        status = rng.choices(["Completed", "In Progress", "Dropped", "Not Started"], [55, 25, 10, 10])[0]
        enrollments.append({
            "enrollment_id": f"EN{2000 + i}",
            "emp_code": emp_codes[rng.randrange(len(emp_codes))],
            "course_code": course["course_code"],
            "enrolled_on": date(2025, 1, 1) + timedelta(days=rng.randrange(0, 300)),
            "status": status,
            "score_percent": rng.randrange(45, 100) if status == "Completed" else None,
            "hours_spent": course["duration_hours"] if status == "Completed"
            else round(course["duration_hours"] * rng.uniform(0.1, 0.8)),
        })
    certs = []
    for i in range(180):
        issued = date(2023, 1, 1) + timedelta(days=rng.randrange(0, 900))
        certs.append({
            "emp_code": emp_codes[rng.randrange(len(emp_codes))],
            "certification": rng.choice(["AWS Solutions Architect", "PMP", "CISSP", "Scrum Master",
                                         "Six Sigma Green Belt", "ITIL Foundation"]),
            "issued_on": issued,
            "expires_on": issued + timedelta(days=rng.choice([365, 730, 1095])),
            "issuing_body": rng.choice(vendors),
        })
    budget = [{"department": d, "quarter": q,
               "budget_amount": rng.randrange(2, 12) * 50_000,
               "spent_amount": rng.randrange(1, 10) * 45_000}
              for d in DEPARTMENTS for q in ("Q1 FY25", "Q2 FY25", "Q3 FY25", "Q4 FY25")]
    employees = [{"emp_code": code, "full_name": (name := person(rng)),
                  "department": DEPARTMENTS[i % len(DEPARTMENTS)],
                  "work_email": email(name, i), "grade": f"L{i % 5 + 1}",
                  "date_of_joining": date(2018, 1, 1) + timedelta(days=rng.randrange(0, 2500))}
                 for i, code in enumerate(emp_codes)]
    trainers = [{"trainer_id": f"TRN{20 + i}", "trainer_name": person(rng),
                 "vendor": vendors[i % len(vendors)],
                 "speciality": cats[i % len(cats)],
                 "day_rate": rng.randrange(10, 60) * 1000,
                 "rating_out_of_5": round(rng.uniform(3.2, 4.9), 1)} for i in range(14)]
    return {name: pd.DataFrame(rows) for name, rows in
            [("courses", courses), ("enrollments", enrollments),
             ("certifications", certs), ("training_budget", budget),
             ("employees", employees), ("trainers", trainers)]}


def write_learning(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    rows = [["course_code", "title", "category", "mode", "duration_hours", "vendor", "cost_per_seat"]]
    for c in clean["courses"].itertuples():
        rows.append([c.course_code, c.title, case_variant(rng, c.category), c.mode,
                     c.duration_hours, c.vendor, f"₹{inr(c.cost_per_seat)}"])
    _write_csv(out / "courses.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    rows = [["emp_code", "full_name", "department", "work_email", "grade", "date_of_joining"]]
    for e in clean["employees"].itertuples():
        rows.append([e.emp_code, e.full_name, case_variant(rng, e.department), e.work_email,
                     e.grade, iso(e.date_of_joining)])
    _write_csv(out / "employees_lite.csv", rows)

    rows = [["Empanelled Trainers FY25", None, None, None, None, None],
            ["trainer_id", "trainer_name", "vendor", "speciality", "day_rate", "rating_out_of_5"]]
    for t in clean["trainers"].itertuples():
        rows.append([t.trainer_id, t.trainer_name, t.vendor, t.speciality, rs(t.day_rate),
                     t.rating_out_of_5])
    _write_vendor_csv(out / "trainers.csv", rows)

    rows = [["enrollment_id", "emp_code", "course_code", "enrolled_on", "status",
             "score_percent", "hours_spent", "feedback_comment"]]
    for e in clean["enrollments"].itertuples():
        rows.append([e.enrollment_id, e.emp_code, e.course_code, dmy(e.enrolled_on), e.status,
                     "N/A" if e.score_percent is None or pd.isna(e.score_percent) else f"{int(e.score_percent)}%",
                     e.hours_spent, ""])  # feedback_comment: all empty
    rows.append(["EN9999", "004002", "CRS-999", "05-08-2025", "Completed", "88%", 8, ""])  # orphan course
    _write_csv(out / "enrollments.csv", rows)

    book = Workbook()
    rows = [["Certification Register - valid and expired", None, None, None, None],
            ["emp_code", "certification", "issued_on", "expires_on", "issuing_body"]]
    for c in clean["certifications"].itertuples():
        rows.append([c.emp_code, c.certification, iso(c.issued_on), iso(c.expires_on), c.issuing_body])
    _sheet(book, "Certifications", rows, first=True)
    _save_workbook(book, out / "certifications.xlsx")

    budget = clean["training_budget"]
    rows = [["department", "quarter", "budget_amount", "spent_amount", "utilisation_percent"]]
    for b in budget.itertuples():
        rows.append([case_variant(rng, b.department), b.quarter, f"₹{inr(b.budget_amount)}",
                     f"₹{inr(b.spent_amount)}", f"{b.spent_amount / b.budget_amount:.1%}"])
    rows.append(["Grand Total", None, f"₹{inr(int(budget.budget_amount.sum()))}",
                 f"₹{inr(int(budget.spent_amount.sum()))}",
                 f"{budget.spent_amount.sum() / budget.budget_amount.sum():.1%}"])
    _write_csv(out / "training_budget.csv", rows)


def answers_learning(c: dict[str, pd.DataFrame]) -> list[dict]:
    crs, enr, cert, bud = c["courses"], c["enrollments"], c["certifications"], c["training_budget"]
    done = enr[enr.status == "Completed"]
    by_cat = enr.merge(crs[["course_code", "category"]], on="course_code").category.value_counts()
    spend = bud.groupby("department")[["budget_amount", "spent_amount"]].sum()
    spend["util"] = spend.spent_amount / spend.budget_amount
    worst = spend.sort_values("util", ascending=False)
    expiring = cert[(cert.expires_on >= date(2025, 10, 1)) & (cert.expires_on <= date(2026, 3, 31))]
    seat_cost = done.merge(crs[["course_code", "cost_per_seat"]], on="course_code").cost_per_seat.sum()
    return [
        {"q": "How many enrolments were completed?",
         "a": f"{len(done)} completed of {len(enr)} real enrolments ({len(done) / len(enr):.0%}). "
              "The file has one extra row (EN9999) pointing at a course that does not exist.",
         "files": "enrollments.csv",
         "trap": "An all-empty 'feedback_comment' column, and 'N/A' scores on everything not completed."},
        {"q": "What is the average score of completed courses?",
         "a": f"{done.score_percent.mean():.1f}% across {len(done)} completed enrolments.",
         "files": "enrollments.csv",
         "trap": "Scores are percent strings ('82%'). 'N/A' must be skipped, not read as 0."},
        {"q": "Which course category has the most enrolments?",
         "a": "\n".join(f"{n}. {k} {v}" for n, (k, v) in enumerate(by_cat.items(), 1)),
         "files": "enrollments.csv + courses.csv",
         "trap": "Cross-file, plus 'Technical', 'technical ' and 'TECHNICAL' are one category. "
                 "The orphan course CRS-999 drops out."},
        {"q": "What did completed training cost us in seat fees?",
         "a": f"Rs. {inr(int(seat_cost))} - {len(done)} completed seats priced from courses.csv.",
         "files": "enrollments.csv + courses.csv",
         "trap": "Cross-file fan-out: one course row prices many enrolment rows. Costs are '₹2,500' text."},
        {"q": "Which department used the most of its training budget?",
         "a": "\n".join(f"{n}. {k} {v.util:.1%} (spent Rs. {inr(int(v.spent_amount))} "
                        f"of Rs. {inr(int(v.budget_amount))})" for n, (k, v) in enumerate(worst.iterrows(), 1)),
         "files": "training_budget.csv",
         "trap": "A Grand Total footer, four quarters per department to sum, and a utilisation column "
                 "already written as a percent string."},
        {"q": "How many certifications expire between October 2025 and March 2026?",
         "a": f"{len(expiring)} of {len(cert)} certifications.",
         "files": "certifications.xlsx",
         "trap": "A title row above the header, and two date columns where only one is the answer."},
        {"q": "Which department completed the most training hours?",
         "a": "\n".join(f"{n}. {k} {int(v)} hours" for n, (k, v) in enumerate(
             done.merge(c["employees"][["emp_code", "department"]], on="emp_code")
             .groupby("department").hours_spent.sum().sort_values(ascending=False).items(), 1)),
         "files": "enrollments.csv + employees_lite.csv",
         "trap": "Cross-file on emp_code (a leading-zero text id), plus department spelling variants."},
        {"q": "Who is trained?",
         "a": "CLARIFY. 'Trained' could mean any completed enrolment, a compliance course completed, "
              "or a live certification. The app should ask.",
         "files": "-", "trap": "Ambiguous term."},
        {"q": "Which employees are likely to drop out of their current course?",
         "a": "REFUSE. A prediction. Also try 'Show me the trainer's rating for each course' - there is "
              "no such column.",
         "files": "-", "trap": "Prediction and missing column."},
    ]


# ---------------------------------------------------------------- 4. benefits_and_claims


def build_benefits(rng: random.Random) -> dict[str, pd.DataFrame]:
    emp_codes = [f"{4000 + i * 3:06d}" for i in range(120)]
    types = ["Travel", "Internet", "Mobile", "Medical", "Meal", "Books & Periodicals"]
    claims = []
    for i in range(900):
        claims.append({
            "claim_id": f"CLM{10000 + i}",
            "emp_code": emp_codes[rng.randrange(len(emp_codes))],
            "claim_type": rng.choices(types, [25, 20, 20, 15, 12, 8])[0],
            "claim_date": date(2025, 1, 1) + timedelta(days=rng.randrange(0, 300)),
            "amount": rng.randrange(200, 60_000),
            "status": rng.choices(["Approved", "Rejected", "Pending"], [72, 12, 16])[0],
            "receipt_no": f"{rng.randrange(1, 999999):06d}",
        })
    plans = {"Base": (300_000, 6_500), "Plus": (500_000, 11_000), "Family Floater": (1_000_000, 19_500)}
    insurance = []
    for i, code in enumerate(emp_codes[:100]):
        plan = list(plans)[i % 3]
        sum_insured, premium = plans[plan]
        dependants = rng.randrange(0, 5)
        insurance.append({
            "emp_code": code, "plan": plan, "sum_insured": sum_insured,
            "dependants": dependants,
            "annual_premium": premium + dependants * 2_200,
            "enrolled_on": date(2025, 4, 1) + timedelta(days=rng.randrange(0, 45)),
        })
    allowances = [{"allowance_code": f"AL{i:03d}", "allowance_name": n, "monthly_limit": lim,
                   "taxable": tax, "applicable_grade": g}
                  for i, (n, lim, tax, g) in enumerate([
                      ("Travel Allowance", 12_000.50, False, "M1-M3"),
                      ("Internet Reimbursement", 1_500.00, False, "All"),
                      ("Mobile Reimbursement", 1_000.00, False, "All"),
                      ("Medical Reimbursement", 1_25_000.00, False, "All"),
                      ("Meal Card", 2_200.00, False, "All"),
                      ("Books & Periodicals", 2_500.00, False, "M2-M5"),
                      ("Fuel Allowance", 8_000.00, True, "M4-M5"),
                      ("Driver Allowance", 9_000.00, True, "M5"),
                      ("Leave Travel Allowance", 60_000.00, False, "All"),
                      ("Relocation Support", 1_50_000.00, True, "All"),
                      ("Gym Membership", 2_000.00, True, "All"),
                      ("Creche Support", 12_000.00, False, "All"),
                      ("Home Office Setup", 25_000.00, False, "All"),
                      ("Upskilling Grant", 40_000.00, False, "M2-M5"),
                      ("Wellness Wallet", 6_000.00, True, "All")], start=1)]
    approvals = []
    for claim in claims:
        if claim["status"] == "Pending":
            continue
        approved_amount = claim["amount"] if claim["status"] == "Approved" else 0
        approvals.append({
            "claim_id": claim["claim_id"],
            "approver": person(rng),
            "approved_on": claim["claim_date"] + timedelta(days=rng.randrange(2, 30)),
            "approved_amount": approved_amount,
            "remarks": "" if claim["status"] == "Approved" else
            rng.choice(["Receipt not legible", "Outside policy limit", "Duplicate claim", "Late submission"]),
        })
    employees = [{"employee_id": code, "full_name": (name := person(rng)),
                  "department": DEPARTMENTS[i % len(DEPARTMENTS)],
                  "grade": f"M{i % 5 + 1}", "work_email": email(name, i),
                  "mobile": phone(rng),
                  "date_of_joining": date(2017, 1, 1) + timedelta(days=rng.randrange(0, 2900))}
                 for i, code in enumerate(emp_codes)]
    return {name: pd.DataFrame(rows) for name, rows in
            [("claims", claims), ("insurance", insurance), ("allowances", allowances),
             ("approvals", approvals), ("employees", employees)]}


def write_benefits(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    # The payroll vendor's export: semicolons, Windows-1252, "Rs." with a non-breaking space.
    # cp1252 has no rupee sign, which is exactly why this file writes "Rs." and
    # allowances_master.csv (UTF-8) writes "₹".
    rows = [["Reimbursement Claims - FY25 - system export", None, None, None, None, None, None],
            ["claim_id", "emp_code", "claim_type", "claim_date", "amount", "status", "receipt_no"]]
    for c in clean["claims"].itertuples():
        amount = f"Rs. {inr(c.amount)}" if c.amount < 5000 else f"Rs. {inr(c.amount)}.00"
        rows.append([c.claim_id, c.emp_code, case_variant(rng, c.claim_type), dmy(c.claim_date),
                     amount, c.status, c.receipt_no])
    rows.append(["Total", None, None, None, f"Rs. {inr(int(clean['claims'].amount.sum()))}.00", None, None])
    _write_csv(out / "reimbursement_claims.csv", rows, encoding="cp1252", delimiter=";")

    book = Workbook()
    rows = [["Group Mediclaim - enrolment as on 15-05-2025", None, None, None, None, None],
            ["emp_code", "plan", "sum_insured", "dependants", "annual_premium", "enrolled_on"]]
    for i in clean["insurance"].itertuples():
        rows.append([i.emp_code, i.plan, i.sum_insured, i.dependants, i.annual_premium, iso(i.enrolled_on)])
    _sheet(book, "Enrolment", rows, first=True)
    _save_workbook(book, out / "insurance_enrolment.xlsx")

    rows = [["allowance_code", "allowance_name", "monthly_limit", "taxable", "applicable_grade"]]
    for a in clean["allowances"].itertuples():
        rows.append([a.allowance_code, a.allowance_name, f"₹{inr(int(a.monthly_limit))}.50"
                     if a.monthly_limit % 1 else f"₹{inr(int(a.monthly_limit))}.00",
                     "Yes" if a.taxable else "No", a.applicable_grade])
    _write_csv(out / "allowances_master.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    rows = [["employee_id", "full_name", "department", "grade", "work_email", "mobile",
             "date_of_joining"]]
    for e in clean["employees"].itertuples():
        rows.append([e.employee_id, e.full_name, case_variant(rng, e.department), e.grade,
                     e.work_email, e.mobile, iso(e.date_of_joining)])
    _write_csv(out / "employees_lite.csv", rows)

    rows = [["claim_id", "approver", "approved_on", "approved_amount", "remarks"]]
    for a in clean["approvals"].itertuples():
        rows.append([a.claim_id, a.approver, mdy(a.approved_on), f"₹{inr(a.approved_amount)}.00",
                     blankish(rng, a.remarks, 0.03)])
    rows.append(["CLM99999", "Unknown Approver", "09/30/2025", "₹5,000.00", "orphan row"])
    _write_csv(out / "claim_approvals.csv", rows)


def answers_benefits(c: dict[str, pd.DataFrame]) -> list[dict]:
    claims, ins, allow, appr = c["claims"], c["insurance"], c["allowances"], c["approvals"]
    approved = claims[claims.status == "Approved"]
    by_type = approved.groupby("claim_type").amount.sum().sort_values(ascending=False)
    rejected = appr[appr.approved_amount == 0]
    reasons = rejected.remarks.value_counts()
    prem_by_plan = ins.groupby("plan").agg(people=("emp_code", "size"),
                                           premium=("annual_premium", "sum"),
                                           dependants=("dependants", "sum"))
    top_claimers = approved.groupby("emp_code").amount.sum().sort_values(ascending=False).head(5)
    return [
        {"q": "What is the total value of approved claims?",
         "a": f"Rs. {inr(int(approved.amount.sum()))} across {len(approved)} approved claims "
              f"(of {len(claims)} claims worth Rs. {inr(int(claims.amount.sum()))} in total).",
         "files": "reimbursement_claims.csv",
         "trap": "A title row, a Total footer holding the all-status total, semicolon separators and "
                 "Windows-1252 encoding. Amounts are 'Rs. 4,500' text with a non-breaking space."},
        {"q": "Which claim type costs the most?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(v))}" for n, (k, v) in enumerate(by_type.items(), 1)),
         "files": "reimbursement_claims.csv",
         "trap": "'Travel', 'travel ' and 'TRAVEL' are one type. Approved claims only. Order matters."},
        {"q": "How many claims were rejected, and why?",
         "a": f"{len(rejected)} rejected.\n" + "\n".join(f"- {k}: {v}" for k, v in reasons.items()),
         "files": "claim_approvals.csv",
         "trap": "Dates are MM/DD/YYYY in this file and DD-MM-YYYY in the claims file. One approval "
                 "(CLM99999) refers to a claim that is not in the claims file."},
        {"q": "What is our annual insurance premium, by plan?",
         "a": "\n".join(f"- {k}: {int(v.people)} people, Rs. {inr(int(v.premium))}, "
                        f"{int(v.dependants)} dependants" for k, v in prem_by_plan.iterrows()) +
              f"\nTotal Rs. {inr(int(ins.annual_premium.sum()))} for {len(ins)} employees and "
              f"{int(ins.dependants.sum())} dependants.",
         "files": "insurance_enrolment.xlsx",
         "trap": "A title row above the header."},
        {"q": "Who claimed the most this year?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(v))}" for n, (k, v) in enumerate(top_claimers.items(), 1)),
         "files": "reimbursement_claims.csv",
         "trap": "emp_code is a leading-zero id ('004512') that must stay text; read as a number the "
                 "codes collide and the ranking is wrong."},
        {"q": "Which employees claimed more than their monthly allowance limit allows?",
         "a": f"Needs claim type matched to allowance name by hand: the two files share no key. "
              f"Allowance limits range from Rs. {inr(int(allow.monthly_limit.min()))} to "
              f"Rs. {inr(int(allow.monthly_limit.max()))}.",
         "files": "reimbursement_claims.csv + allowances_master.csv",
         "trap": "Cross-file with only a fuzzy text match available ('Travel' vs 'Travel Allowance'). "
                 "A good look at whether the app invents a join."},
        {"q": "Which department claims the most per head?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(v))} per head" for n, (k, v) in enumerate(
             (approved.merge(c["employees"][["employee_id", "department"]], left_on="emp_code",
                             right_on="employee_id").groupby("department").amount.sum()
              / c["employees"].groupby("department").size()).sort_values(ascending=False).items(), 1)),
         "files": "reimbursement_claims.csv + employees_lite.csv",
         "trap": "Cross-file where the key is emp_code on one side and employee_id on the other, "
                 "and the denominator is a head count from the other file, not a row count."},
        {"q": "How much have we settled in claims?",
         "a": "CLARIFY. 'Settled' could mean status Approved in the claims file or an approved_amount "
              "above zero in the approvals file; the two disagree because pending claims have no "
              "approval row at all.",
         "files": "-", "trap": "Ambiguous term that two files answer differently."},
        {"q": "What will claims cost us next quarter?",
         "a": "REFUSE. A forecast. Also try 'Show me the GST on each claim' - there is no such column.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- 5. retail_sales


def build_retail(rng: random.Random) -> dict[str, pd.DataFrame]:
    cities = [("Pune", "West"), ("Mumbai", "West"), ("Surat", "West"), ("Delhi", "North"),
              ("Jaipur", "North"), ("Lucknow", "North"), ("Bengaluru", "South"), ("Chennai", "South"),
              ("Kochi", "South"), ("Kolkata", "East"), ("Patna", "East"), ("Guwahati", "East")]
    stores = [{
        "store_id": f"{10 + i:04d}",  # "0010": leading zero, must stay text
        "city": city, "region": region,
        "opened_on": date(2019, 1, 1) + timedelta(days=rng.randrange(0, 2000)),
        "store_manager": person(rng),
    } for i, (city, region) in enumerate(cities * 2)]
    for n, store in enumerate(stores):
        store["store_id"] = f"{10 + n:04d}"
    cats = {"Beverages": (45, 250), "Snacks": (60, 120), "Personal Care": (30, 320),
            "Home Care": (25, 280), "Dairy": (70, 90), "Frozen": (20, 420)}
    brands = ["Amberleaf", "Bluecrest", "Coralpine", "Dunefield", "Everglow", "Foxglove"]
    products = []
    for i in range(120):
        cat = list(cats)[i % len(cats)]
        base = cats[cat][1]
        mrp = round(base * rng.uniform(0.6, 2.4) / 5) * 5
        products.append({
            "sku": f"SKU-{1000 + i * 3}",
            "product_name": f"{brands[i % len(brands)]} {cat.split()[0]} {['Classic', 'Fresh', 'Max', 'Mini', 'Pro'][i % 5]}",
            "category": cat, "brand": brands[i % len(brands)],
            "mrp": mrp, "cost": round(mrp * rng.uniform(0.45, 0.72), 2),
        })
    sales = []
    for quarter, start, length in (("Q1", date(2025, 1, 1), 90), ("Q2", date(2025, 4, 1), 91)):
        for day in days(start, length):
            weekend = 1.3 if day.weekday() >= 5 else 1.0
            for store in stores:
                for product in rng.sample(products, 28):
                    units = max(1, int(rng.gauss(cats[product["category"]][0], 12) * weekend / 8))
                    discount = rng.choices([0, 5, 10, 15], [55, 20, 15, 10])[0]
                    gross = units * product["mrp"]
                    sales.append({
                        "quarter": quarter, "date": day, "store_id": store["store_id"],
                        "sku": product["sku"], "units": units,
                        "net_amount": round(gross * (100 - discount) / 100, 2),
                        "discount_percent": discount,
                    })
    reasons = ["Damaged", "Wrong item", "Expired", "Changed mind", "Quality issue"]
    returns = [{
        "return_id": f"RET{5000 + i}",
        "return_date": date(2025, 1, 5) + timedelta(days=rng.randrange(0, 175)),
        "store_id": stores[rng.randrange(len(stores))]["store_id"],
        "sku": products[rng.randrange(len(products))]["sku"],
        "units_returned": rng.randrange(1, 4),
        "reason": rng.choices(reasons, [30, 25, 20, 15, 10])[0],
        "refund_amount": rng.randrange(50, 4000),
    } for i in range(1500)]
    roles = ["Store Manager", "Cashier", "Sales Associate", "Stock Associate"]
    staff = [{"store_id": store["store_id"], "role": role,
              "headcount": {"Store Manager": 1, "Cashier": rng.randrange(2, 5),
                            "Sales Associate": rng.randrange(4, 12),
                            "Stock Associate": rng.randrange(2, 6)}[role],
              "monthly_wage_bill": rng.randrange(60, 400) * 1000}
             for store in stores for role in roles]
    return {name: pd.DataFrame(rows) for name, rows in
            [("stores", stores), ("products", products),
             ("sales", pd.DataFrame(sales).to_dict("records")), ("returns", returns),
             ("staff", staff)]}


def write_retail(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    rows = [["store_id", "city", "region", "opened_on", "store_manager"]]
    for s in clean["stores"].itertuples():
        rows.append([s.store_id, s.city, case_variant(rng, s.region), dmy(s.opened_on), s.store_manager])
    _write_csv(out / "stores.csv", rows)

    book = Workbook()
    rows = [["sku", "product_name", "category", "brand", "mrp", "cost", "discontinued_on"]]
    for p in clean["products"].itertuples():
        rows.append([p.sku, p.product_name, case_variant(rng, p.category), p.brand,
                     p.mrp, p.cost, None])  # discontinued_on: all empty
    _sheet(book, "Master", rows, first=True)
    _save_workbook(book, out / "products.xlsx")

    sales = clean["sales"]
    header = ["date", "store_id", "sku", "units", "net_amount", "discount"]
    for quarter, name in (("Q1", "daily_sales_q1.csv"), ("Q2", "daily_sales_q2.csv")):
        part = sales[sales.quarter == quarter]
        rows = [header]
        for s in part.itertuples():
            rows.append([dmy(s.date), s.store_id, s.sku, s.units, f"{s.net_amount:.2f}",
                         f"{s.discount_percent}%"])
        if quarter == "Q2":  # the analyst left the subtotal line at the bottom
            rows.append(["Grand Total", None, None, int(part.units.sum()),
                         f"{part.net_amount.sum():.2f}", None])
        _write_csv(out / name, rows)

    rows = [["return_id", "return_date", "store_id", "sku", "units_returned", "reason", "refund_amount"]]
    for r in clean["returns"].itertuples():
        rows.append([r.return_id, mdy(r.return_date), r.store_id, r.sku, r.units_returned,
                     case_variant(rng, r.reason), f"₹{inr(r.refund_amount)}"])
    rows.append(["RET9999", "06/30/2025", "0099", "SKU-9999", 2, "Damaged", "₹1,200"])  # orphan sku + store
    _write_csv(out / "returns.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    staff = clean["staff"]
    rows = [["Store staffing and wage bill - June 2025", None, None, None],
            ["store_id", "role", "headcount", "monthly_wage_bill"]]
    for s in staff.itertuples():
        rows.append([s.store_id, s.role, s.headcount, rs(s.monthly_wage_bill)])
    rows.append(["Total", None, int(staff.headcount.sum()),
                 rs(int(staff.monthly_wage_bill.sum()))])
    _write_vendor_csv(out / "staff_by_store.csv", rows)


def answers_retail(c: dict[str, pd.DataFrame]) -> list[dict]:
    stores, prod, sales, ret = c["stores"], c["products"], c["sales"], c["returns"]
    total = sales.net_amount.sum()
    by_q = sales.groupby("quarter").net_amount.sum()
    by_region = sales.merge(stores[["store_id", "region"]], on="store_id").groupby(
        "region").net_amount.sum().sort_values(ascending=False)
    by_cat = sales.merge(prod[["sku", "category"]], on="sku").groupby(
        "category").net_amount.sum().sort_values(ascending=False)
    top_stores = sales.groupby("store_id").net_amount.sum().sort_values(ascending=False).head(5)
    top_stores = top_stores.to_frame().join(stores.set_index("store_id")[["city"]])
    discounted = sales[sales.discount_percent > 0]
    by_reason = ret.groupby("reason").refund_amount.sum().sort_values(ascending=False)
    return [
        {"q": "What were total net sales in the first half of 2025?",
         "a": f"Rs. {inr(int(round(total)))} over {len(sales):,} sale lines "
              f"(Q1 Rs. {inr(int(round(by_q['Q1'])))}, Q2 Rs. {inr(int(round(by_q['Q2'])))}).",
         "files": "daily_sales_q1.csv + daily_sales_q2.csv",
         "trap": "The two quarter files must combine, and daily_sales_q2.csv ends with a Grand Total "
                 "row that adds the whole quarter a second time."},
        {"q": "Which region sells the most?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(round(v)))}" for n, (k, v) in enumerate(by_region.items(), 1)),
         "files": "daily_sales_q1.csv + daily_sales_q2.csv + stores.csv",
         "trap": "Cross-file fan-out (one store row prices 60,000 sale lines) plus 'West', 'west ' and "
                 "'WEST' being one region. Order matters."},
        {"q": "Which product category earns the most?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(round(v)))}" for n, (k, v) in enumerate(by_cat.items(), 1)),
         "files": "daily_sales_q1.csv + daily_sales_q2.csv + products.xlsx",
         "trap": "Cross-file on sku, with case and trailing-space variants in the category column and "
                 "an all-empty 'discontinued_on' column in the workbook."},
        {"q": "Which five stores sell the most?",
         "a": "\n".join(f"{n}. {code} ({row.city}) Rs. {inr(int(round(row.net_amount)))}"
                        for n, (code, row) in enumerate(top_stores.iterrows(), 1)),
         "files": "daily_sales_q1.csv + daily_sales_q2.csv + stores.csv",
         "trap": "store_id is '0010' and must stay text; read as a number it loses the leading zero and "
                 "joins nothing."},
        {"q": "How much of our revenue came from discounted lines?",
         "a": f"Rs. {inr(int(round(discounted.net_amount.sum())))} from {len(discounted):,} discounted "
              f"lines, {discounted.net_amount.sum() / total:.1%} of net sales.",
         "files": "daily_sales_q1.csv + daily_sales_q2.csv",
         "trap": "'discount' is a percent string ('10%'), not a number."},
        {"q": "What did we refund, and for what reason?",
         "a": f"Rs. {inr(int(ret.refund_amount.sum()))} over {len(ret)} returns "
              f"(the file has {len(ret) + 1} rows: RET9999 points at a SKU and a store that do not exist).\n"
              + "\n".join(f"- {k}: Rs. {inr(int(v))}" for k, v in by_reason.items()),
         "files": "returns.csv",
         "trap": "Dates are MM/DD/YYYY here and DD-MM-YYYY in the sales files. UTF-8 BOM. Orphan keys "
                 "on two columns at once."},
        {"q": "Which store has the highest sales per head of store staff?",
         "a": "\n".join(f"{n}. {k} Rs. {inr(int(round(v)))} per head" for n, (k, v) in enumerate(
             (sales.groupby("store_id").net_amount.sum()
              / c["staff"].groupby("store_id").headcount.sum()).sort_values(ascending=False).head(5).items(), 1)),
         "files": "daily_sales_q1.csv + daily_sales_q2.csv + staff_by_store.csv",
         "trap": "Four staff rows per store must be summed before the division; joining first and "
                 "dividing after multiplies the sales by four (classic fan-out). staff_by_store.csv "
                 "is semicolon-separated Windows-1252 with a title row and a Total footer."},
        {"q": "How are our best stores doing?",
         "a": "CLARIFY. 'Best' could be net sales, units, sales per day open, or the lowest return rate. "
              "The app should ask which.",
         "files": "-", "trap": "Ambiguous term."},
        {"q": "What will sales be in Q3?",
         "a": "REFUSE. A forecast. Also try 'Show me the footfall per store' - there is no such column.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- 6. performance_and_engagement


SURVEY_QUESTIONS = [
    "I know what is expected of me at work",
    "I have the tools I need to do my job well",
    "My manager gives me useful feedback",
    "I can see a path to grow here",
    "I would recommend this company to a friend",
    "My workload is manageable",
    "I feel respected by my team",
    "Leadership communicates openly",
]


def build_performance(rng: random.Random) -> dict[str, pd.DataFrame]:
    managers = [{"manager_id": f"MGR{100 + i}", "manager_name": person(rng),
                 "department": DEPARTMENTS[i % len(DEPARTMENTS)],
                 "span_of_control": rng.randrange(3, 16),
                 "location": rng.choice(["Pune Campus", "Bengaluru HQ", "Remote", "Chennai Plant"])}
                for i in range(20)]
    emp_codes = [f"{4000 + i * 3:06d}" for i in range(120)]
    objectives = ["Grow new business", "Improve retention", "Ship the platform rewrite",
                  "Cut support backlog", "Raise NPS", "Close the books faster"]
    okrs = []
    for i in range(300):
        target = rng.choice([10, 25, 50, 100, 200])
        achieved = round(target * rng.uniform(0.35, 1.25))
        okrs.append({
            "okr_id": f"OKR{1000 + i}",
            "employee_id": emp_codes[rng.randrange(len(emp_codes))],
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "objective": objectives[i % len(objectives)],
            "key_result": f"Metric {i % 12 + 1}",
            "target": target, "achieved": achieved,
            "quarter": rng.choice(["Q1 FY25", "Q2 FY25", "Q3 FY25", "Q4 FY25"]),
        })
    reviews = []
    for i, code in enumerate(emp_codes):
        manager_rating = rng.choices([1, 2, 3, 4, 5], [4, 12, 45, 28, 11])[0]
        reviews.append({
            "emp_code": code, "employee_name": person(rng),
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "manager_rating": manager_rating,
            "self_rating": min(5, manager_rating + rng.choice([0, 0, 1, 1, -1])),
            "final_rating": manager_rating,
            "hike_percent": round(4 + manager_rating * 2.2 + rng.uniform(-1, 1), 1),
            "new_ctc": rng.randrange(6, 40) * 100_000,
        })
    survey = []
    for i in range(180):
        row = {"respondent_id": f"R{2000 + i}", "department": DEPARTMENTS[i % len(DEPARTMENTS)]}
        for n, q in enumerate(SURVEY_QUESTIONS, 1):
            row[f"q{n}"] = None if rng.random() < 0.07 else rng.choices([1, 2, 3, 4, 5],
                                                                       [5, 10, 25, 38, 22])[0]
        survey.append(row)
    exit_reasons = [
        "Got a better offer, nearly 40% more, could not match it.",
        "Relocating to my home town for family reasons.",
        'Manager changed three times in a year, "no clarity" on my goals.',
        "Joining a full-time masters programme.\nNo issues with the team.",
        "Commute became impossible after the office move.",
        "Wanted to move into product; no internal role was open.",
        "Health reasons, taking a break.",
        "Pay revision promised in April did not happen.",
    ]
    exits = []
    for i in range(45):
        lwd = date(2025, 1, 15) + timedelta(days=rng.randrange(0, 260))
        exits.append({
            "emp_code": emp_codes[rng.randrange(len(emp_codes))],
            "last_working_day": lwd,
            "reason": rng.choice(exit_reasons),
            "would_rehire": rng.choices([True, False], [72, 28])[0],
            "tenure_months": rng.randrange(6, 84),
        })
    employees = [{"emp_code": code, "full_name": person(rng),
                  "department": DEPARTMENTS[i % len(DEPARTMENTS)],
                  "manager_id": managers[i % len(managers)]["manager_id"],
                  "grade": f"L{i % 5 + 1}",
                  "date_of_joining": date(2017, 1, 1) + timedelta(days=rng.randrange(0, 2900))}
                 for i, code in enumerate(emp_codes)]
    return {name: pd.DataFrame(rows) for name, rows in
            [("okrs", okrs), ("reviews", reviews), ("survey", survey),
             ("exits", exits), ("managers", managers), ("employees", employees)]}


def write_performance(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    rows = [["okr_id", "employee_id", "department", "objective", "key_result", "target",
             "achieved", "progress_percent", "quarter"]]
    for o in clean["okrs"].itertuples():
        rows.append([o.okr_id, o.employee_id, case_variant(rng, o.department), o.objective,
                     o.key_result, o.target, o.achieved, f"{o.achieved / o.target:.0%}", o.quarter])
    _write_csv(out / "okrs.csv", rows)

    # A title row, then a two-row header: groups on one line, sub-columns on the next.
    book = Workbook()
    sheet = _sheet(book, "Cycle FY25", [
        ["Annual Review Cycle FY25 - HR Confidential", None, None, None, None, None, None, None],
        ["Employee", None, None, "Ratings", None, None, "Compensation", None],
        ["Emp Code", "Name", "Department", "Manager", "Self", "Final", "Hike %", "New CTC"],
    ], first=True)
    for start, end in ((1, 3), (4, 6), (7, 8)):  # Employee / Ratings / Compensation groups
        sheet.merge_cells(start_row=2, start_column=start, end_row=2, end_column=end)
    for r in clean["reviews"].itertuples():
        sheet.append([r.emp_code, r.employee_name, r.department, r.manager_rating, r.self_rating,
                      r.final_rating, f"{r.hike_percent}%", r.new_ctc])
    _save_workbook(book, out / "review_ratings.xlsx")

    header = ["respondent_id", "department"] + SURVEY_QUESTIONS
    rows = [header]
    for s in clean["survey"].itertuples(index=False):
        row = list(s)
        rows.append([row[0], case_variant(rng, row[1])] +
                    ["" if v is None or pd.isna(v) else int(v) for v in row[2:]])
    _write_csv(out / "engagement_survey.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    rows = [["emp_code", "last_working_day", "reason", "would_rehire", "tenure_months"]]
    for e in clean["exits"].itertuples():
        rows.append([e.emp_code, longdate(e.last_working_day), e.reason,
                     "Yes" if e.would_rehire else "No", e.tenure_months])
    rows.append(["009999", "3 Mar 2025", "Row kept from an older file, employee not in any master.",
                 "No", 14])
    _write_csv(out / "exit_interviews.csv", rows)

    rows = [["Manager Directory - FY25", None, None, None, None],
            ["manager_id", "manager_name", "department", "span_of_control", "location"]]
    for m in clean["managers"].itertuples():
        rows.append([m.manager_id, m.manager_name, case_variant(rng, m.department),
                     m.span_of_control, m.location])
    _write_vendor_csv(out / "managers.csv", rows)

    rows = [["emp_code", "full_name", "department", "manager_id", "grade", "date_of_joining"]]
    for e in clean["employees"].itertuples():
        rows.append([e.emp_code, e.full_name, case_variant(rng, e.department), e.manager_id,
                     e.grade, iso(e.date_of_joining)])
    _write_csv(out / "employees_lite.csv", rows)


def answers_performance(c: dict[str, pd.DataFrame]) -> list[dict]:
    okrs, rev, survey, exits, mgr = c["okrs"], c["reviews"], c["survey"], c["exits"], c["managers"]
    hit = okrs[okrs.achieved >= okrs.target]
    by_dept = okrs.assign(p=okrs.achieved / okrs.target).groupby("department").p.mean().sort_values(
        ascending=False)
    ratings = rev.final_rating.value_counts().sort_index()
    hike = rev.groupby("final_rating").hike_percent.mean().round(2)
    qcols = [f"q{n}" for n in range(1, len(SURVEY_QUESTIONS) + 1)]
    means = survey[qcols].mean().round(2)
    worst = means.idxmin()
    survey_dept = survey.groupby("department")[qcols].mean().mean(axis=1).round(2).sort_values()
    rehire = exits.would_rehire.value_counts()
    return [
        {"q": "How many OKRs hit their target?",
         "a": f"{len(hit)} of {len(okrs)} OKRs ({len(hit) / len(okrs):.0%}).",
         "files": "okrs.csv",
         "trap": "'progress_percent' is already a percent string; recomputing from target and achieved "
                 "is the safe route."},
        {"q": "Which department is furthest along on its OKRs?",
         "a": "\n".join(f"{n}. {k} {v:.0%} average progress" for n, (k, v) in enumerate(by_dept.items(), 1)),
         "files": "okrs.csv",
         "trap": "Department spelling variants. Average of ratios, not ratio of sums. Order matters."},
        {"q": "How are final ratings distributed?",
         "a": "\n".join(f"- {int(k)}: {v} people" for k, v in ratings.items()) +
              f"\nAverage final rating {rev.final_rating.mean():.2f} across {len(rev)} reviews.",
         "files": "review_ratings.xlsx",
         "trap": "A title row AND a two-row header with merged group cells above the real header. "
                 "If the app reads row 2 as the header, every column is called Ratings or None."},
        {"q": "What is the average hike by final rating?",
         "a": "\n".join(f"- rating {int(k)}: {v}%" for k, v in hike.items()),
         "files": "review_ratings.xlsx",
         "trap": "Hike is a percent string under a two-row header."},
        {"q": "Which engagement question scored the worst?",
         "a": f'"{SURVEY_QUESTIONS[qcols.index(worst)]}" at {means[worst]}/5.\n' +
              "\n".join(f"- {SURVEY_QUESTIONS[i]}: {means[q]}" for i, q in enumerate(qcols)),
         "files": "engagement_survey.csv",
         "trap": "Wide format: one column per question, with blanks that must be skipped rather than "
                 "counted as zero. The headers are whole sentences."},
        {"q": "Which department is least engaged?",
         "a": "\n".join(f"{n}. {k} {v}/5 average across all questions"
                        for n, (k, v) in enumerate(survey_dept.items(), 1)),
         "files": "engagement_survey.csv",
         "trap": "Wide format plus department spelling variants; the average has to run across eight "
                 "columns and then across rows."},
        {"q": "Why are people leaving, and would we rehire them?",
         "a": f"{len(exits)} exits (the file has {len(exits) + 1} rows: emp_code 009999 matches no "
              f"master file). Would rehire: {int(rehire.get(True, 0))} yes, {int(rehire.get(False, 0))} no. "
              f"Median tenure {exits.tenure_months.median():.0f} months. Reasons are free text - pay, "
              "relocation, manager churn, higher studies, commute.",
         "files": "exit_interviews.csv",
         "trap": "Free text with commas, quotes and newlines inside cells. Dates as '3 Mar 2025'. "
                 "An orphan emp_code."},
        {"q": "What is the average final rating by manager location?",
         "a": "\n".join(f"- {k}: {v:.2f}" for k, v in rev.merge(
             c["employees"][["emp_code", "manager_id"]], on="emp_code").merge(
             mgr[["manager_id", "location"]], on="manager_id").groupby(
             "location").final_rating.mean().sort_values(ascending=False).items()) +
              f"\n({len(mgr)} managers, average span of control {mgr.span_of_control.mean():.1f}.)",
         "files": "review_ratings.xlsx + employees_lite.csv + managers.csv",
         "trap": "Three files deep: ratings sit under a two-row header, employees_lite.csv carries the "
                 "manager_id, and managers.csv is semicolon-separated Windows-1252 with a title row."},
        {"q": "Who are our top performers?",
         "a": "CLARIFY. 'Top performer' could be final rating 5, OKR attainment above 100%, or the "
              "largest hike. The app should ask.",
         "files": "-", "trap": "Ambiguous term."},
        {"q": "Who is likely to resign next quarter?",
         "a": "REFUSE. A prediction about named people. Also try 'Show me each employee's flight risk "
              "score' - there is no such column.",
         "files": "-", "trap": "Prediction and missing column."},
    ]


# ---------------------------------------------------------------- 7. company_fintech_full


COST_CENTRES = ["CC-100 Lending", "CC-200 Payments", "CC-300 Risk", "CC-400 Technology",
                "CC-500 Customer Ops", "CC-600 Corporate"]
BANDS = ["B1", "B2", "B3", "B4", "B5", "B6"]
SEPARATION_REASONS = ["Better opportunity", "Compensation", "Relocation", "Higher studies",
                      "Performance", "Personal reasons"]


def build_fintech(rng: random.Random) -> dict[str, pd.DataFrame]:
    """Kifaya Finserv: 900 staff, the same KINDS of files as demo_data/ in a different vocabulary."""
    band_pay = {"B1": 420_000, "B2": 720_000, "B3": 1_150_000, "B4": 1_900_000,
                "B5": 3_200_000, "B6": 5_400_000}
    staff = []
    for i in range(900):
        band = rng.choices(BANDS, [26, 28, 22, 14, 7, 3])[0]
        joined = date(2015, 1, 1) + timedelta(days=rng.randrange(0, 3800))
        name = person(rng)
        # 2025 leavers, so an attrition rate for the year is a real question with a real answer.
        separated = (date(2025, 1, 1) + timedelta(days=rng.randrange(0, 330))
                     if rng.random() < 0.14 and joined < date(2025, 1, 1) else None)
        fixed = round(band_pay[band] * rng.uniform(0.85, 1.2) / 1000) * 1000
        usd = rng.random() < 0.08  # the Singapore desk is paid in dollars
        staff.append({
            "staff_no": f"{100000 + i * 7:06d}",
            "full_name": name,
            "work_email": email(name, i),
            "mobile": phone(rng),
            "cost_centre": COST_CENTRES[i % len(COST_CENTRES)],
            "band": band,
            "location": "Singapore" if usd else rng.choice(["Mumbai", "Bengaluru", "Pune", "Remote"]),
            "gender": rng.choices(["Female", "Male", "Not disclosed"], [42, 55, 3])[0],
            "date_of_joining": joined,
            "separation_date": separated,
            "separation_reason": rng.choice(SEPARATION_REASONS) if separated else None,
            "currency": "USD" if usd else "INR",
            "fixed_pay": round(fixed / 83 / 100) * 100 if usd else fixed,
            "variable_pay_percent": {"B1": 5, "B2": 8, "B3": 12, "B4": 18, "B5": 25, "B6": 35}[band],
            "manager_staff_no": f"{100000 + rng.randrange(0, 900) * 7:06d}",
        })
    payroll = []
    for month in range(1, 13):
        pay_month = date(2025, month, 1)
        for row in staff:
            if row["date_of_joining"] > pay_month:
                continue
            if row["separation_date"] and row["separation_date"] < pay_month:
                continue
            fixed = round(row["fixed_pay"] / 12, 2)
            variable = round(fixed * row["variable_pay_percent"] / 100, 2) if month in (3, 9) else 0.0
            deductions = round((fixed + variable) * rng.uniform(0.08, 0.14), 2)
            payroll.append({
                "staff_no": row["staff_no"], "pay_month": pay_month, "currency": row["currency"],
                "fixed_pay": fixed, "variable_pay": variable, "deductions": deductions,
                "net_pay": round(fixed + variable - deductions, 2),
                "half": "H1" if month <= 6 else "H2",
            })
    attendance = [{
        "staff_no": row["staff_no"], "month": date(2025, m, 1),
        "working_days": 22, "present_days": (p := rng.randrange(17, 23)),
        "wfh_days": rng.randrange(0, 23 - p + 1), "lop_days": max(0, 22 - p - rng.randrange(0, 3)),
    } for row in staff[:400] for m in range(1, 7)]
    reviews = [{
        "staff_no": row["staff_no"], "cycle": "FY25",
        "rating": (r := rng.choices([1, 2, 3, 4, 5], [3, 11, 46, 29, 11])[0]),
        "potential": rng.choice(["Emerging", "Core", "High"]),
        "promoted": r >= 4 and rng.random() < 0.35,
        "reviewer_staff_no": row["manager_staff_no"],
    } for row in staff if row["separation_date"] is None]
    targets = [{"cost_centre": cc, "quarter": q,
                "target_usd": (t := rng.randrange(200, 900) * 1000),
                "achieved_usd": round(t * rng.uniform(0.6, 1.3))}
               for cc in COST_CENTRES for q in ("Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025")]
    return {name: pd.DataFrame(rows) for name, rows in
            [("staff", staff), ("payroll", payroll), ("attendance", attendance),
             ("reviews", reviews), ("targets", targets)]}


def write_fintech(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    staff = clean["staff"]
    book = Workbook()  # two sheets, same columns: the HRIS splits active from separated
    header = ["staff_no", "full_name", "work_email", "mobile", "cost_centre", "band", "location",
              "gender", "date_of_joining", "separation_date", "separation_reason",
              "manager_staff_no"]
    for n, (title, active) in enumerate((("Active Staff", True), ("Separated 2025", False))):
        rows = [header]
        part = staff[staff.separation_date.isna()] if active else staff[staff.separation_date.notna()]
        for s in part.itertuples():
            rows.append([s.staff_no, s.full_name, s.work_email, s.mobile,
                         case_variant(rng, s.cost_centre), s.band, s.location, s.gender,
                         dmy(s.date_of_joining),
                         "" if s.separation_date is None else dmy(s.separation_date),
                         "" if s.separation_reason is None else s.separation_reason,
                         s.manager_staff_no])
        _sheet(book, title, rows, first=n == 0)
    _save_workbook(book, out / "staff_master.xlsx")

    payroll = clean["payroll"]
    for half, name in (("H1", "payroll_h1_2025.csv"), ("H2", "payroll_h2_2025.csv")):
        part = payroll[payroll.half == half]
        rows = [["staff_no", "pay_month", "currency", "fixed_pay", "variable_pay", "deductions",
                 "net_pay"]]
        for p in part.itertuples():
            # USD and INR in one amount column, with the currency named beside it: the dollar
            # rows are written bare, the rupee rows with a symbol, so the column parses cleanly
            # and summing it silently adds two units together. That is the trap.
            money = (lambda v: f"{v:,.2f}") if p.currency == "USD" else (lambda v: f"₹{inr(v)}.00")
            rows.append([p.staff_no, f"{p.pay_month:%b-%Y}", p.currency, money(p.fixed_pay),
                         money(p.variable_pay), money(p.deductions), money(p.net_pay)])
        if half == "H2":
            rows.append(["Grand Total", None, None, None, None, None,
                         f"₹{inr(int(part[part.currency == 'INR'].net_pay.sum()))}.00"])
        _write_csv(out / name, rows)

    rows = [["staff_no", "month", "working_days", "present_days", "wfh_days", "lop_days"]]
    for a in clean["attendance"].itertuples():
        rows.append([a.staff_no, iso(a.month), a.working_days, a.present_days, a.wfh_days,
                     blankish(rng, a.lop_days, 0.03)])
    rows += rows[1:31]  # the January extract was appended twice
    _write_csv(out / "attendance_monthly.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    rows = [["Performance Cycle FY25 - moderation complete", None, None, None, None],
            ["staff_no", "cycle", "rating", "potential", "promoted"]]
    for r in clean["reviews"].itertuples():
        rows.append([r.staff_no, r.cycle, r.rating, r.potential, "Yes" if r.promoted else "No"])
    rows.append(["999999", "FY25", 4, "Core", "No"])  # orphan: no such staff_no
    _write_csv(out / "performance_reviews.csv", rows)

    targets = clean["targets"]
    rows = [["Revenue targets by cost centre (USD)", None, None, None, None],
            ["cost_centre", "quarter", "target_usd", "achieved_usd", "attainment"]]
    for t in targets.itertuples():
        rows.append([t.cost_centre, t.quarter, f"$ {t.target_usd:,}", f"$ {t.achieved_usd:,}",
                     f"{t.achieved_usd / t.target_usd:.1%}"])
    rows.append(["Total", None, f"$ {int(targets.target_usd.sum()):,}",
                 f"$ {int(targets.achieved_usd.sum()):,}",
                 f"{targets.achieved_usd.sum() / targets.target_usd.sum():.1%}"])
    _write_vendor_csv(out / "revenue_targets.csv", rows)


def answers_fintech(c: dict[str, pd.DataFrame]) -> list[dict]:
    staff, pay, att, rev, tgt = c["staff"], c["payroll"], c["attendance"], c["reviews"], c["targets"]
    left = staff[staff.separation_date.notna()]
    active = staff[staff.separation_date.isna()]
    # Attrition the way HR computes it: leavers over the average of opening and closing headcount.
    opening = len(staff[staff.date_of_joining < date(2025, 1, 1)])
    attrition = len(left) / ((opening + len(active)) / 2)
    inr_pay = pay[pay.currency == "INR"]
    by_month = inr_pay.groupby("pay_month").net_pay.sum()
    # INR only: averaging the column as it stands adds dollar salaries to rupee ones.
    inr_active = active[active.currency == "INR"]
    by_band = inr_active.groupby("band").fixed_pay.mean().round(0)
    by_cc = active.cost_centre.value_counts()
    reasons = left.separation_reason.value_counts()
    ratings = rev.rating.value_counts().sort_index()
    attain = tgt.groupby("cost_centre").apply(
        lambda g: g.achieved_usd.sum() / g.target_usd.sum(), include_groups=False).sort_values(ascending=False)
    return [
        {"q": "What was our attrition rate in 2025?",
         "a": f"{attrition:.1%} - {len(left)} separations against an average headcount of "
              f"{(opening + len(active)) / 2:,.0f} (opening {opening}, closing {len(active)}).",
         "files": "staff_master.xlsx (both sheets)",
         "trap": "The leavers are on a second sheet. Read one sheet only and attrition is 0% or 100%. "
                 "'Average headcount' is the denominator; simple leavers/closing gives "
                 f"{len(left) / len(active):.1%} instead."},
        {"q": "How many people work here, by band?",
         "a": f"{len(active)} active staff.\n" + "\n".join(
             f"- {k}: {v}" for k, v in active.band.value_counts().sort_index().items()),
         "files": "staff_master.xlsx",
         "trap": "Two sheets: only the active one counts. staff_no is a six-digit text id, not a number."},
        {"q": "What is the average fixed pay by band?",
         "a": "Rupee-paid staff only (the Singapore desk is paid in USD):\n" +
              "\n".join(f"- {k}: Rs. {inr(int(v))}" for k, v in by_band.items()) +
              f"\n{len(inr_active)} of {len(active)} active staff are paid in INR; the other "
              f"{len(active) - len(inr_active)} are in USD and must not be averaged in.",
         "files": "staff_master.xlsx",
         "trap": "The pay column holds INR and USD amounts with a separate currency column. Averaging "
                 "without filtering on currency mixes two units - the honest answer names the split."},
        {"q": "What was the total net payroll in 2025, month by month?",
         "a": f"INR payroll only, Rs. {inr(int(by_month.sum()))} across "
              f"{len(inr_pay):,} INR payslips.\n" + "\n".join(
                  f"- {k:%b %Y}: Rs. {inr(int(v))}" for k, v in by_month.items()) +
              f"\n(USD payslips: {len(pay) - len(inr_pay):,}, $ {pay[pay.currency == 'USD'].net_pay.sum():,.2f}.)",
         "files": "payroll_h1_2025.csv + payroll_h2_2025.csv",
         "trap": "The two half-year files must combine, the Grand Total row at the foot of H2 must be "
                 "dropped, and USD rows must not be added to INR rows - the amount column holds both, "
                 "with the unit in the currency column beside it, so a plain SUM is a wrong number "
                 "that looks right. March and September carry variable pay, so those months are "
                 "higher on purpose."},
        {"q": "Which cost centre has the most people, and which hit its revenue target?",
         "a": "Headcount:\n" + "\n".join(f"{n}. {k} {v}" for n, (k, v) in enumerate(by_cc.items(), 1)) +
              "\n\nTarget attainment:\n" + "\n".join(
                  f"{n}. {k} {v:.1%}" for n, (k, v) in enumerate(attain.items(), 1)),
         "files": "staff_master.xlsx + revenue_targets.csv",
         "trap": "Cross-file on cost_centre, where the master has 'CC-200 Payments', 'cc-200 payments ' "
                 "and 'CC-200 PAYMENTS'. revenue_targets.csv is semicolon-separated Windows-1252 with a "
                 "title row and a Total footer."},
        {"q": "Why did people leave?",
         "a": "\n".join(f"{n}. {k} {v}" for n, (k, v) in enumerate(reasons.items(), 1)) +
              f"\n{len(left)} separations in total.",
         "files": "staff_master.xlsx (sheet 'Separated 2025')",
         "trap": "Only the separated sheet has a reason; the active sheet's column is empty throughout."},
        {"q": "How are performance ratings distributed?",
         "a": "\n".join(f"- {int(k)}: {v} people" for k, v in ratings.items()) +
              f"\nAverage {rev.rating.mean():.2f} across {len(rev)} reviewed staff. "
              f"{int(rev.promoted.sum())} promoted.",
         "files": "performance_reviews.csv",
         "trap": "A title row, and one orphan row (staff_no 999999) that matches nobody in the master."},
        {"q": "What is the average LOP per person per month?",
         "a": f"{att.lop_days.mean():.2f} days across {len(att):,} real attendance rows "
              f"({len(att) + 30:,} rows in the file: 30 are a duplicated January block).",
         "files": "attendance_monthly.csv",
         "trap": "Duplicated rows inflate the count; blanks and 'N/A' in lop_days must be skipped, not "
                 "read as zero. The file has a UTF-8 BOM."},
        {"q": "Who are our expensive people?",
         "a": "CLARIFY. 'Expensive' could mean fixed pay, fixed plus variable, or actual net pay "
              "drawn in 2025 - and the currency column means the comparison needs a unit first.",
         "files": "-", "trap": "Ambiguous term over a mixed-currency column."},
        {"q": "What will attrition be next year?",
         "a": "REFUSE. A forecast. Also try 'Show me each person's notice period' - there is no such "
              "column in any of these files.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- 8. company_manufacturing_full


PLANTS = ["Chakan Plant", "Hosur Plant", "Sanand Plant", "Haridwar Plant"]
SHOPS = ["Press Shop", "Weld Shop", "Paint Shop", "Assembly", "Quality", "Maintenance"]


def build_manufacturing(rng: random.Random) -> dict[str, pd.DataFrame]:
    """Girnar Auto Components: 2,500 workers across four plants, shift-based, with contractors."""
    contractors = ["Shakti Manpower", "Sahyadri Services", "Deccan Staffing", None]
    grade_wage = {"W1": 620, "W2": 780, "W3": 950, "S1": 1250, "S2": 1650, "E1": 2400}
    workers = []
    for i in range(2500):
        permanent = rng.random() < 0.62
        grade = rng.choices(list(grade_wage), [30, 26, 18, 14, 8, 4])[0]
        joined = date(2012, 1, 1) + timedelta(days=rng.randrange(0, 4700))
        leaving = (date(2025, 1, 1) + timedelta(days=rng.randrange(0, 330))
                   if rng.random() < (0.09 if permanent else 0.27) and joined < date(2025, 1, 1)
                   else None)
        workers.append({
            "ticket_no": f"{20000 + i * 3:06d}",
            "worker_name": person(rng),
            "plant": PLANTS[i % len(PLANTS)],
            "shop_floor": SHOPS[i % len(SHOPS)],
            "employment_type": "Permanent" if permanent else "Contractor",
            "contractor_name": None if permanent else contractors[i % 3],
            "grade": grade,
            "daily_wage": grade_wage[grade],
            "date_of_joining": joined,
            "date_of_leaving": leaving,
            "leaving_reason": rng.choice(["Absconding", "Better wages elsewhere", "Contract ended",
                                          "Medical", "Retirement"]) if leaving else None,
        })
    wages, attendance = [], []
    for month in range(1, 7):
        wage_month = date(2025, month, 1)
        for w in workers:
            if w["date_of_joining"] > wage_month or (w["date_of_leaving"] and w["date_of_leaving"] < wage_month):
                continue
            days_worked = rng.randrange(18, 27)
            overtime = round(rng.triangular(0, 40, 8), 1)
            basic = days_worked * w["daily_wage"]
            ot_wages = round(overtime * w["daily_wage"] / 8 * 2, 2)
            pf = round(basic * 0.12, 2) if w["employment_type"] == "Permanent" else 0.0
            esi = round((basic + ot_wages) * 0.0075, 2) if basic < 21000 else 0.0
            wages.append({
                "ticket_no": w["ticket_no"], "wage_month": wage_month, "days_worked": days_worked,
                "basic_wages": basic, "overtime_wages": ot_wages, "pf_deduction": pf,
                "esi_deduction": esi, "net_payable": round(basic + ot_wages - pf - esi, 2),
                "half": "H1",
            })
            attendance.append({
                "ticket_no": w["ticket_no"], "month": wage_month, "plant": w["plant"],
                "shift": rng.choices(["A (06-14)", "B (14-22)", "C (22-06)"], [45, 35, 20])[0],
                "days_present": days_worked, "overtime_hours": overtime,
                "absent_days": 26 - days_worked,
            })
    incidents = [{
        "incident_id": f"SI-{500 + i}",
        "plant": PLANTS[rng.randrange(len(PLANTS))],
        "incident_date": date(2025, 1, 1) + timedelta(days=rng.randrange(0, 180)),
        "incident_type": rng.choices(["Near Miss", "First Aid", "Lost Time Injury", "Property Damage"],
                                     [45, 30, 15, 10])[0],
        "severity": rng.choices(["Low", "Medium", "High"], [55, 33, 12])[0],
        "days_lost": rng.choices([0, 1, 3, 7, 21], [60, 15, 12, 9, 4])[0],
        "reported_by": person(rng),
    } for i in range(140)]
    production = [{
        "plant": plant, "month": date(2025, m, 1), "line": f"Line {line}",
        "target_units": (t := rng.randrange(8, 26) * 1000),
        "actual_units": round(t * rng.uniform(0.72, 1.14)),
    } for plant in PLANTS for m in range(1, 7) for line in (1, 2)]
    return {name: pd.DataFrame(rows) for name, rows in
            [("workers", workers), ("wages", wages), ("attendance", attendance),
             ("incidents", incidents), ("production", production)]}


def write_manufacturing(out: Path, clean: dict[str, pd.DataFrame], rng: random.Random) -> None:
    rows = [["Workforce Register - all plants - as on 30-06-2025", None, None, None, None, None,
             None, None, None, None, None],
            ["ticket_no", "worker_name", "plant", "shop_floor", "employment_type",
             "contractor_name", "grade", "daily_wage", "date_of_joining", "date_of_leaving",
             "leaving_reason"]]
    for w in clean["workers"].itertuples():
        rows.append([w.ticket_no, w.worker_name, case_variant(rng, w.plant), w.shop_floor,
                     w.employment_type, w.contractor_name or "N/A", w.grade, w.daily_wage,
                     dmy(w.date_of_joining),
                     "" if w.date_of_leaving is None else dmy(w.date_of_leaving),
                     w.leaving_reason or ""])
    _write_csv(out / "workforce_master.csv", rows)

    wages = clean["wages"]
    rows = [["ticket_no", "wage_month", "days_worked", "basic_wages", "overtime_wages",
             "pf_deduction", "esi_deduction", "net_payable"]]
    for w in wages.itertuples():
        rows.append([w.ticket_no, f"{w.wage_month:%b-%Y}", w.days_worked, rs(w.basic_wages),
                     rs(w.overtime_wages), rs(w.pf_deduction), rs(w.esi_deduction),
                     rs(w.net_payable)])
    rows.append(["Grand Total", None, int(wages.days_worked.sum()), rs(int(wages.basic_wages.sum())),
                 rs(int(wages.overtime_wages.sum())), rs(int(wages.pf_deduction.sum())),
                 rs(int(wages.esi_deduction.sum())), rs(int(wages.net_payable.sum()))])
    _write_vendor_csv(out / "wage_register_h1.csv", rows)

    att = clean["attendance"]
    rows = [["ticket_no", "month", "plant", "shift", "days_present", "overtime_hours",
             "absent_days", "remarks"]]
    for a in att.itertuples():
        rows.append([a.ticket_no, mdy(a.month), case_variant(rng, a.plant), a.shift,
                     a.days_present, a.overtime_hours, a.absent_days, ""])  # remarks: all empty
    rows += rows[1:51]  # the June upload ran twice
    rows.append(["099999", "06/01/2025", "Chakan Plant", "A (06-14)", 24, 12.0, 2, ""])  # orphan
    _write_csv(out / "shift_attendance.csv", rows)

    rows = [["incident_id", "plant", "incident_date", "incident_type", "severity", "days_lost",
             "reported_by"]]
    for i in clean["incidents"].itertuples():
        rows.append([i.incident_id, i.plant, longdate(i.incident_date), i.incident_type,
                     i.severity, i.days_lost, i.reported_by])
    _write_csv(out / "safety_incidents.csv", rows, encoding="utf-8-sig")  # UTF-8 BOM

    book = Workbook()  # one sheet per plant, same columns: they should combine into one view
    production = clean["production"]
    for n, plant in enumerate(PLANTS):
        part = production[production.plant == plant]
        rows = [[f"{plant} - production plan vs actual", None, None, None, None],
                ["plant", "month", "line", "target_units", "actual_units"]]
        for p in part.itertuples():
            rows.append([p.plant, f"{p.month:%b-%Y}", p.line, p.target_units, p.actual_units])
        _sheet(book, plant.replace(" Plant", ""), rows, first=n == 0)
    _save_workbook(book, out / "production_targets.xlsx")


def answers_manufacturing(c: dict[str, pd.DataFrame]) -> list[dict]:
    wrk, wage, att, inc, prod = (c["workers"], c["wages"], c["attendance"], c["incidents"],
                                 c["production"])
    left = wrk[wrk.date_of_leaving.notna()]
    active = wrk[wrk.date_of_leaving.isna()]
    opening = len(wrk[wrk.date_of_joining < date(2025, 1, 1)])
    attrition = len(left) / ((opening + len(active)) / 2)
    by_plant = active.groupby(["plant", "employment_type"]).size().unstack(fill_value=0)
    by_month = wage.groupby("wage_month").net_payable.sum()
    ot_by_plant = att.groupby("plant").overtime_hours.sum().sort_values(ascending=False)
    ot_cost = wage.overtime_wages.sum()
    lti = inc[inc.incident_type == "Lost Time Injury"]
    inc_by_plant = inc.groupby("plant").agg(incidents=("incident_id", "size"),
                                            days_lost=("days_lost", "sum")).sort_values(
                                                "days_lost", ascending=False)
    attain = prod.groupby("plant").apply(
        lambda g: g.actual_units.sum() / g.target_units.sum(), include_groups=False).sort_values(ascending=False)
    contractor_attrition = (len(left[left.employment_type == "Contractor"]) /
                            len(wrk[wrk.employment_type == "Contractor"]))
    return [
        {"q": "How many people work at each plant, permanent versus contractor?",
         "a": f"{len(active):,} active workers of {len(wrk):,} on the register.\n" + "\n".join(
             f"- {plant}: {int(row['Permanent'])} permanent, {int(row['Contractor'])} contractor"
             for plant, row in by_plant.iterrows()),
         "files": "workforce_master.csv",
         "trap": "A title row above the header, plant names typed four ways ('Chakan Plant', "
                 "'chakan plant ', 'CHAKAN PLANT'), and leavers still on the register - filter on "
                 "an empty date_of_leaving."},
        {"q": "What was the attrition rate in 2025, and is it worse for contractors?",
         "a": f"{attrition:.1%} overall - {len(left)} leavers against an average headcount of "
              f"{(opening + len(active)) / 2:,.0f}. Contractors leave at {contractor_attrition:.1%} "
              f"of their own head count, permanents at "
              f"{len(left[left.employment_type == 'Permanent']) / len(wrk[wrk.employment_type == 'Permanent']):.1%}.",
         "files": "workforce_master.csv",
         "trap": "date_of_leaving is blank for everyone still employed; counting blanks as a leaving "
                 "date makes attrition 100%."},
        {"q": "What did wages cost, month by month?",
         "a": f"Rs. {inr(int(wage.net_payable.sum()))} net over six months "
              f"({len(wage):,} wage rows).\n" + "\n".join(
                  f"- {k:%b %Y}: Rs. {inr(int(v))}" for k, v in by_month.items()) +
              f"\nPF Rs. {inr(int(wage.pf_deduction.sum()))}, ESI Rs. {inr(int(wage.esi_deduction.sum()))}.",
         "files": "wage_register_h1.csv",
         "trap": "Semicolon-separated Windows-1252 with a Grand Total footer that repeats every total. "
                 "Counted in, every number here doubles."},
        {"q": "How much overtime is each plant running, and what did it cost?",
         "a": "\n".join(f"{n}. {k} {v:,.1f} hours" for n, (k, v) in enumerate(ot_by_plant.items(), 1)) +
              f"\nOvertime wages across all plants: Rs. {inr(int(ot_cost))} "
              f"({ot_cost / wage.net_payable.sum():.1%} of net wages).",
         "files": "shift_attendance.csv + wage_register_h1.csv",
         "trap": "Cross-file: the hours are in attendance, the money is in the wage register, and the "
                 "attendance file carries 50 duplicated rows plus one orphan ticket (099999) that "
                 "inflates the hours if kept. Dates are MM/DD/YYYY here, DD-MM-YYYY in the master."},
        {"q": "Which plant has the worst safety record?",
         "a": "\n".join(f"{n}. {k}: {int(row.incidents)} incidents, {int(row.days_lost)} days lost"
                        for n, (k, row) in enumerate(inc_by_plant.iterrows(), 1)) +
              f"\n{len(lti)} were lost-time injuries, {int(lti.days_lost.sum())} days lost between them.",
         "files": "safety_incidents.csv",
         "trap": "'Worst' by count and by days lost can rank differently - the answer should say which "
                 "it used. Dates read '3 Mar 2025'; the file has a UTF-8 BOM."},
        {"q": "Which plant is closest to its production target?",
         "a": "\n".join(f"{n}. {k} {v:.1%} of target" for n, (k, v) in enumerate(attain.items(), 1)) +
              f"\nAll plants: {prod.actual_units.sum():,} units against a target of "
              f"{prod.target_units.sum():,}.",
         "files": "production_targets.xlsx (four sheets)",
         "trap": "One sheet per plant with identical columns - all four must combine, and each sheet "
                 "has its own title row above the header."},
        {"q": "What is the overtime cost per unit produced, by plant?",
         "a": "\n".join(
             f"- {plant}: Rs. {inr(int(round(v)))} per unit"
             for plant, v in (wage.merge(wrk[['ticket_no', 'plant']], on='ticket_no')
                              .groupby('plant').overtime_wages.sum()
                              / prod.groupby('plant').actual_units.sum()).items()),
         "files": "wage_register_h1.csv + workforce_master.csv + production_targets.xlsx",
         "trap": "Three files and a fan-out: one worker row prices six wage rows, and production is "
                 "per plant per line per month. Join at the wrong grain and the cost is multiplied."},
        {"q": "How many workers are absent?",
         "a": "CLARIFY. 'Absent' could be absent_days in the attendance file, days_worked below the "
              "month's working days in the wage register, or people who have left. The app should ask.",
         "files": "-", "trap": "Ambiguous term that three files answer differently."},
        {"q": "How many units will Hosur produce next quarter?",
         "a": "REFUSE. A forecast. Also try 'Show me the scrap rate per line' - there is no such column.",
         "files": "-", "trap": "Forecast and missing column."},
    ]


# ---------------------------------------------------------------- packs


PACKS: dict[str, tuple[Callable, Callable, Callable]] = {
    "recruitment": (build_recruitment, write_recruitment, answers_recruitment),
    "leave_and_shifts": (build_leave, write_leave, answers_leave),
    "learning": (build_learning, write_learning, answers_learning),
    "benefits_and_claims": (build_benefits, write_benefits, answers_benefits),
    "retail_sales": (build_retail, write_retail, answers_retail),
    "performance_and_engagement": (build_performance, write_performance, answers_performance),
    "company_fintech_full": (build_fintech, write_fintech, answers_fintech),
    "company_manufacturing_full": (build_manufacturing, write_manufacturing, answers_manufacturing),
}


def _zip(folder: Path) -> Path:
    """One zip per pack, with fixed timestamps so reruns are byte-identical."""
    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
        for item in sorted(folder.iterdir()):
            info = zipfile.ZipInfo(f"{folder.name}/{item.name}", date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, item.read_bytes())
    return archive


def _write_expected(expected: dict[str, list[dict]]) -> None:
    lines = [
        "# Expected answers, pack by pack",
        "",
        "Written by `test_files/packs/generate_packs.py` from the clean frames, with pandas,",
        "before any mess was added. Nothing here is typed by hand, so these numbers are what",
        "the files really contain, not what the app says they contain. If DarwinLens disagrees",
        "with a number below, DarwinLens is wrong (or the question was read differently: the",
        "trap line under each answer says exactly what was counted).",
        "",
        "Two answers per pack are not numbers. **CLARIFY** means the app should ask a question",
        "back rather than guess. **REFUSE** means the app should decline: a forecast, or a",
        "column that does not exist.",
        "",
    ]
    for pack, items in expected.items():
        lines += [f"## {pack}", ""]
        for number, item in enumerate(items, start=1):
            lines += [f"### {number}. {item['q']}", "",
                      f"*Files:* {item['files']}", "", item["a"], "",
                      f"> **Trap:** {item['trap']}", ""]
    (HERE / "EXPECTED.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    expected: dict[str, list[dict]] = {}
    for n, (pack, (build, write, answers)) in enumerate(PACKS.items()):
        folder = HERE / pack
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.iterdir():
            stale.unlink()
        clean = build(random.Random(SEED + n))
        write(folder, clean, random.Random(SEED + 100 + n))  # a separate stream: mess never moves facts
        expected[pack] = answers(clean)
        archive = _zip(folder)
        print(f"{pack:28} {archive.stat().st_size / 1e6:6.2f} MB zipped")
        for item in sorted(folder.iterdir()):
            print(f"    {item.name:26} {item.stat().st_size / 1e6:6.2f} MB")
        assert all(i.stat().st_size < 9e6 for i in folder.iterdir()), f"{pack}: a file is over 9 MB"
    _write_expected(expected)
    total = sum(p.stat().st_size for p in HERE.glob("*.zip"))
    print(f"\nAll zips: {total / 1e6:.2f} MB. Wrote EXPECTED.md.")


# ---------------------------------------------------------------- the check


def check() -> None:
    """Ingest every pack through the real engine, the way backend/tests do, and print the
    receipt. No model is involved: this is ingestion, profiling, link and union detection."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.sessions import SessionStore  # noqa: PLC0415 - only the --check path needs the backend

    for pack in PACKS:
        folder = HERE / pack
        files = [(p, p.name) for p in sorted(folder.iterdir()) if p.suffix in {".csv", ".xlsx"}]
        session = SessionStore().create()
        catalog = session.add_files(files)
        print(f"\n=== {pack} ({len(files)} files)")
        for table in catalog.tables:
            health = table.health
            notes = []
            if health.skipped_title_rows:
                notes.append(f"{health.skipped_title_rows} title row(s) skipped")
            if health.dropped_total_rows:
                notes.append(f"{health.dropped_total_rows} total row(s) dropped")
            if health.duplicate_rows:
                notes.append(f"{health.duplicate_rows} duplicate row(s)"
                             f"{' removed' if health.duplicates_removed else ' kept'}")
            if health.date_format:
                notes.append(f"dates {health.date_format}"
                             f"{' (ambiguous)' if health.date_format_ambiguous else ''}")
            if health.preserved_id_columns:
                notes.append(f"kept as text: {', '.join(health.preserved_id_columns)}")
            if health.pii_columns:
                notes.append(f"personal: {', '.join(health.pii_columns)}")
            for warning in health.warnings:
                notes.append(f"warning: {warning}")
            kind = "view" if table.is_view else table.source_file
            print(f"  {table.name:28} {table.row_count:>7,} rows x {len(table.columns):>2} cols"
                  f"  [{kind}]")
            for note in notes:
                print(f"      - {note}")
        for union in catalog.unions:
            print(f"  combined view: {union.view_name} <- {', '.join(union.tables)} ({union.status})")
        for link in catalog.relationships:
            print(f"  link {link.status:9} {link.left_table}.{link.left_column} -> "
                  f"{link.right_table}.{link.right_column} ({link.cardinality}, "
                  f"{link.match_left:.0%}/{link.match_right:.0%})")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        main()
