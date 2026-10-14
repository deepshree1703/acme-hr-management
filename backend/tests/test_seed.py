"""Tests for the deterministic employee seed utility."""

from pathlib import Path

import pytest

from app.database import connect
from scripts.seed import seed_employees


def test_seed_is_repeatable_with_a_small_employee_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "seed-test.db"))

    first_added, first_total = seed_employees(count=12, batch_size=5)
    second_added, second_total = seed_employees(count=12, batch_size=5)

    assert (first_added, first_total) == (12, 12)
    assert (second_added, second_total) == (0, 12)

    connection = connect()
    try:
        rows = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT employee_id) FROM employees"
        ).fetchone()
        assert tuple(rows) == (12, 12)
        id_bounds = connection.execute(
            "SELECT MIN(employee_id), MAX(employee_id) FROM employees"
        ).fetchone()
        assert tuple(id_bounds) == ("EMP-00001", "EMP-00012")
    finally:
        connection.close()
