"""Seed the local database with deterministic fictional employees."""

import random
import sqlite3
from collections.abc import Iterator

from app.constants import EMPLOYMENT_STATUSES, SUPPORTED_CURRENCIES
from app.database import connect
from app.db_schema import init_db

EMPLOYEE_COUNT = 10_000
BATCH_SIZE = 500
RANDOM_SEED = 20240517

DEPARTMENTS = (
    "Finance",
    "Human Resources",
    "Engineering",
    "Marketing",
    "Operations",
    "Sales",
    "Customer Support",
    "Legal",
)

COUNTRY_CURRENCIES = (
    ("United States", "USD"),
    ("Germany", "EUR"),
    ("United Kingdom", "GBP"),
    ("India", "INR"),
    ("Canada", "CAD"),
    ("Australia", "AUD"),
    ("Singapore", "SGD"),
    ("Japan", "JPY"),
)

# Annual salary bounds in each local currency.
SALARY_RANGES = {
    "USD": (45_000, 180_000),
    "EUR": (35_000, 130_000),
    "GBP": (30_000, 120_000),
    "INR": (600_000, 4_000_000),  # about 6 to 40 lakhs
    "CAD": (50_000, 160_000),
    "AUD": (60_000, 180_000),
    "SGD": (50_000, 180_000),
    "JPY": (4_000_000, 18_000_000),  # several million yen
}

FIRST_NAMES = (
    "Aarav", "Aisha", "Alex", "Amelia", "Anika", "Arjun", "Ava", "Daniel",
    "Emma", "Ethan", "Fatima", "Hana", "Isabella", "James", "Kai", "Liam",
    "Maya", "Mei", "Noah", "Olivia", "Priya", "Ravi", "Sofia", "Zoe",
)
LAST_NAMES = (
    "Anderson", "Bennett", "Chen", "Das", "Garcia", "Gupta", "Harris",
    "Ito", "Khan", "Kim", "Lee", "Martin", "Miller", "Nguyen", "Patel",
    "Roberts", "Sharma", "Singh", "Taylor", "Wilson", "Wong", "Yamada",
)


def _employee_rows(count: int) -> Iterator[tuple[object, ...]]:
    rng = random.Random(RANDOM_SEED)
    currencies = set(SUPPORTED_CURRENCIES)
    if currencies != set(SALARY_RANGES):
        raise ValueError("Salary ranges must cover all supported currencies")

    for index in range(1, count + 1):
        country, currency = rng.choice(COUNTRY_CURRENCIES)
        salary_min, salary_max = SALARY_RANGES[currency]
        status = rng.choices(EMPLOYMENT_STATUSES, weights=(90, 10), k=1)[0]
        yield (
            f"EMP-{index:05d}",
            f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            rng.choice(DEPARTMENTS),
            country,
            status,
            rng.randint(salary_min, salary_max),
            currency,
        )


def seed_employees(count: int = EMPLOYEE_COUNT, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    """Insert up to ``count`` deterministic employees; return added and total counts."""
    if count < 0 or count > EMPLOYEE_COUNT:
        raise ValueError(f"count must be between 0 and {EMPLOYEE_COUNT}")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    init_db()
    connection = connect()
    added = 0
    try:
        with connection:
            rows = iter(_employee_rows(count))
            while batch := list(_take(rows, batch_size)):
                cursor = connection.executemany(
                    """
                    INSERT INTO employees (
                        employee_id,
                        name,
                        department,
                        country,
                        employment_status,
                        annual_gross_base_salary,
                        currency
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(employee_id) DO NOTHING
                    """,
                    batch,
                )
                added += cursor.rowcount
        total = connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        return added, total
    finally:
        connection.close()


def _take(rows: Iterator[tuple[object, ...]], count: int) -> Iterator[tuple[object, ...]]:
    for _ in range(count):
        try:
            yield next(rows)
        except StopIteration:
            return


def main() -> None:
    added, total = seed_employees()
    print(f"Added {added} employees. Total employees: {total}.")


if __name__ == "__main__":
    main()
