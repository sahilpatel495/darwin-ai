"""The fixed vocabulary of semantic roles. The glossary refers to these names."""

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
