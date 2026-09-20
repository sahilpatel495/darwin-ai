"""The fixed vocabulary of semantic roles, and how a column header earns one.

Why roles exist: "attrition" can only mean one vetted thing if the glossary knows which
column is the joining date and which is the exit date, whatever the export called them.

Why a plain dictionary: at a customer site the fix for "it did not recognise our header" must
be one line anybody can review. Add the header, normalised, to the right tuple below.
"""

from __future__ import annotations

import re

from app.contracts import ColumnType
from app.ingest.cleaning import snake_case

ROLES: tuple[str, ...] = (
    # people
    "employee_id", "manager_id", "person_name", "department", "location", "grade",
    "designation", "gender", "employment_type", "status",
    # lifecycle dates
    "join_date", "exit_date", "exit_reason", "birth_date",
    # pay
    "pay_month", "ctc", "gross", "net", "basic", "deductions", "bonus", "lop_days", "paid_days",
    # attendance and performance
    "days_present", "days_absent", "working_days", "rating", "review_cycle",
    # generic, for non-HR data
    "date", "amount", "quantity", "category", "product", "region", "customer",
)

# Same rule as ingest uses to keep a column as text: emp_id, emp_code, order_no, ...
IDENTIFIER_PATTERN = re.compile(r"(^|_)(id|code|no|num|number)$")

# role -> headers, already normalised (see normalise_header). A header belongs to one role.
ROLE_SYNONYMS: dict[str, tuple[str, ...]] = {
    # "empno"/"employeeno" are for the all-caps spelling EMPNO: no normaliser can find the word
    # break in it, unlike "EmpNo", which normalise_header splits.
    "employee_id": ("employee_id", "emp_id", "emp_code", "emp_no", "emp_num", "emp_number", "empid",
                    "empno", "employeeno",
                    "empcode", "employee_code", "employee_no", "employee_num", "employee_number",
                    "staff_id", "staff_code", "staff_no", "personnel_no", "personnel_number",
                    "worker_id", "associate_id", "ee_id"),
    # The "*_no" spellings are the ones stores.csv uses ("Manager EmpNo" -> manager_emp_no);
    # "*empno" is for the all-caps MANAGER EMPNO, which no normaliser can find a word break in.
    "manager_id": ("manager_id", "manager_code", "manager_no", "manager_number",
                   "manager_emp_id", "manager_emp_code", "manager_emp_no", "manager_empno",
                   "manager_employee_id", "manager_employee_code", "manager_employee_no",
                   "reporting_manager_id", "reporting_manager_code", "reporting_manager_no",
                   "reporting_manager_emp_no", "reporting_manager_empno",
                   "reports_to_id", "supervisor_id", "supervisor_code", "supervisor_no",
                   "supervisor_emp_no", "mgr_id", "mgr_code", "mgr_no", "mgr_emp_no",
                   "l1_manager_id", "l1_manager_code"),
    "person_name": ("person_name", "name", "employee_name", "emp_name", "full_name", "staff_name"),
    "department": ("department", "dept", "department_name", "dept_name", "business_unit", "function"),
    "location": ("location", "city", "office", "office_location", "work_location", "base_location",
                 "location_name", "branch", "site"),
    "grade": ("grade", "band", "level", "job_grade", "job_level", "job_band", "pay_grade"),
    "designation": ("designation", "title", "job_title", "position", "role", "designation_name"),
    "gender": ("gender", "sex"),
    "employment_type": ("employment_type", "emp_type", "employee_type", "worker_type", "contract_type",
                        "employment_category"),
    "status": ("status", "employment_status", "employee_status", "emp_status", "active_status"),
    "join_date": ("join_date", "doj", "date_of_joining", "joining_date", "hire_date", "date_of_hire",
                  "date_of_join", "start_date", "joined_on", "date_joined", "hired_on"),
    "exit_date": ("exit_date", "lwd", "last_working_day", "last_working_date", "date_of_exit",
                  "separation_date", "relieving_date", "date_of_relieving", "date_of_separation",
                  "date_of_leaving", "leaving_date", "termination_date", "dol", "end_date"),
    "exit_reason": ("exit_reason", "reason_for_exit", "reason_for_leaving", "leaving_reason",
                    "separation_reason", "attrition_reason", "termination_reason", "resignation_reason"),
    "birth_date": ("birth_date", "dob", "date_of_birth", "birthdate", "birthday"),
    "pay_month": ("pay_month", "payroll_month", "salary_month", "pay_period", "payroll_period",
                  "month_of_pay"),
    "ctc": ("ctc", "annual_ctc", "cost_to_company", "total_ctc", "ctc_annual", "ctc_per_annum",
            "annual_cost_to_company", "ctc_inr"),
    "gross": ("gross", "gross_pay", "gross_salary", "gross_earnings", "gross_amount", "monthly_gross",
              "total_gross", "gross_wages"),
    "net": ("net", "net_pay", "net_salary", "take_home", "take_home_pay", "net_amount", "net_payable",
            "in_hand", "in_hand_salary", "net_take_home"),
    "basic": ("basic", "basic_pay", "basic_salary", "basic_wage"),
    "deductions": ("deductions", "deduction", "total_deductions", "total_deduction"),
    "bonus": ("bonus", "bonus_amount", "annual_bonus", "performance_bonus", "incentive", "variable_pay"),
    "lop_days": ("lop_days", "lop", "loss_of_pay_days", "loss_of_pay", "lwp_days", "lwp",
                 "unpaid_leave_days"),
    "paid_days": ("paid_days", "days_paid", "payable_days", "pay_days"),
    "days_present": ("days_present", "present_days", "present", "days_worked", "worked_days"),
    "days_absent": ("days_absent", "absent_days", "absent", "absences", "absent_count"),
    "working_days": ("working_days", "work_days", "total_working_days", "total_days", "business_days"),
    "rating": ("rating", "performance_rating", "final_rating", "overall_rating", "perf_rating",
               "appraisal_rating", "review_rating"),
    "review_cycle": ("review_cycle", "cycle", "appraisal_cycle", "review_period", "performance_cycle",
                     "appraisal_period", "appraisal_year"),
    "date": ("date", "order_date", "transaction_date", "txn_date", "invoice_date", "sale_date",
             "posting_date", "created_date", "attendance_date", "attendance_month", "month", "period",
             "day"),
    "amount": ("amount", "revenue", "sales", "sales_amount", "total_amount", "total", "value",
               "net_sales", "turnover", "total_revenue", "total_sales", "order_value", "total_price",
               "line_total"),
    "quantity": ("quantity", "qty", "units", "units_sold", "unit_count", "volume"),
    "category": ("category", "product_category", "segment", "type", "sub_category", "subcategory"),
    "product": ("product", "product_name", "item", "item_name", "sku"),
    "region": ("region", "zone", "territory", "state", "country", "area", "market"),
    "customer": ("customer", "customer_name", "client", "client_name", "account_name", "buyer"),
}

_NUMERIC: tuple[ColumnType, ...] = ("integer", "decimal", "currency")
_DATE_ROLES = {"join_date", "exit_date", "birth_date", "pay_month", "date"}
_NUMERIC_ROLES = {"ctc", "gross", "net", "basic", "deductions", "bonus", "amount", "quantity",
                  "lop_days", "paid_days", "days_present", "days_absent", "working_days"}
_ROLE_BY_HEADER = {header: role for role, headers in ROLE_SYNONYMS.items() for header in headers}


def normalise_header(text: str) -> str:
    """'Gross (₹)' -> 'gross', 'Date of Joining' -> 'date_of_joining', 'EmpNo' -> 'emp_no'.

    Exactly the rule ingest uses to name a column, so a synonym matches whether the role is read
    from the renamed column or from the original label. Two normalisers would drift apart: this
    one used to keep "EmpNo" as one word, so the commonest HRMS spelling of the employee id
    matched nothing while its spaced twin "Emp No" matched.
    """
    return snake_case(text)


def _allowed_types(role: str) -> tuple[ColumnType, ...]:
    """A header alone is not enough: 'DOJ' full of free text cannot drive date arithmetic,
    and a role on the wrong type would make the glossary write SQL that fails."""
    if role in _DATE_ROLES:
        return ("date",)
    if role in _NUMERIC_ROLES:
        return _NUMERIC
    if role in ("employee_id", "manager_id", "review_cycle"):
        return ("text", "integer")
    if role == "rating":  # "4" and "Exceeds expectations" are both ratings
        return ("text", *_NUMERIC)
    return ("text",)


def detect_role(name: str, label: str, type: ColumnType) -> str | None:
    """The role of a column, from its normalised name or, failing that, its original label
    (ingest renames duplicate or unusable headers, but the label still says what it is).

    ponytail: exact header synonyms only. Add fuzzy matching if customer exports show more
    variety than a dictionary can hold; until then a miss is a one-line fix above.
    """
    for header in (normalise_header(name), normalise_header(label)):
        role = _ROLE_BY_HEADER.get(header)
        if role and type in _allowed_types(role):
            return role
    return None
