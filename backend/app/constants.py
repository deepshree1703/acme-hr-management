"""Shared employee-directory values."""

EMPLOYMENT_STATUSES = ("Active", "Inactive")
SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP", "INR", "CAD", "AUD", "SGD", "JPY")
PAGE_SIZE = 20
EMPLOYEE_ID_PATTERN = r"^EMP-\d{5,}$"
MAX_ANNUAL_GROSS_BASE_SALARY = 9999999999.99

DESIGNATIONS_BY_DEPARTMENT = {
    "Engineering": (
        "Software Engineer", "Senior Software Engineer", "QA Engineer",
        "DevOps Engineer", "Engineering Manager",
    ),
    "Finance": (
        "Financial Analyst", "Senior Financial Analyst", "Accountant",
        "Payroll Specialist", "Finance Manager",
    ),
    "Human Resources": (
        "HR Coordinator", "HR Business Partner", "Recruiter",
        "Compensation Analyst", "HR Manager",
    ),
    "Marketing": (
        "Marketing Associate", "Content Strategist",
        "Digital Marketing Specialist", "Brand Manager", "Marketing Manager",
    ),
    "Operations": (
        "Operations Analyst", "Operations Coordinator", "Logistics Specialist",
        "Process Improvement Lead", "Operations Manager",
    ),
    "Sales": (
        "Sales Representative", "Account Executive",
        "Business Development Manager", "Sales Analyst", "Sales Manager",
    ),
    "Customer Support": (
        "Support Agent", "Senior Support Agent", "Support Specialist",
        "Team Lead", "Support Manager",
    ),
    "Legal": (
        "Paralegal", "Legal Counsel", "Senior Legal Counsel",
        "Compliance Officer", "Legal Manager",
    ),
}
