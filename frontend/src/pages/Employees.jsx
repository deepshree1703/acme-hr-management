import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getEmployeeFilterOptions, getEmployees } from "../api.js";

function readPage(value) {
  const parsed = Number.parseInt(value || "1", 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function formatSalary(amount, currency) {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString()} ${currency}`;
  }
}

const FILTERS = [
  ["country", "Country", "countries"],
  ["department", "Department", "departments"],
  ["employment_status", "Employment status", "employment_statuses"],
];

export default function Employees() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryString = searchParams.toString();
  const urlState = useMemo(() => {
    const params = new URLSearchParams(queryString);
    return {
      search: params.get("search") || "",
      country: params.get("country") || "",
      department: params.get("department") || "",
      employment_status: params.get("employment_status") || "",
      page: readPage(params.get("page")),
    };
  }, [queryString]);

  const [searchInput, setSearchInput] = useState(urlState.search);
  const [filters, setFilters] = useState(null);
  const [filterError, setFilterError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestSequence = useRef(0);

  // Keep the input responsive while committing the search to the URL after typing pauses.
  useEffect(() => {
    setSearchInput(urlState.search);
  }, [urlState.search]);

  useEffect(() => {
    if (searchInput === urlState.search) return undefined;
    const timeout = window.setTimeout(() => {
      const next = new URLSearchParams(queryString);
      if (searchInput.trim()) next.set("search", searchInput.trim());
      else next.delete("search");
      next.delete("page");
      setSearchParams(next);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput, urlState.search, queryString, setSearchParams]);

  useEffect(() => {
    let active = true;
    getEmployeeFilterOptions()
      .then((data) => { if (active) setFilters(data); })
      .catch((err) => { if (active) setFilterError(err.message || "Unable to load filters."); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const sequence = ++requestSequence.current;
    let active = true;
    setLoading(true);
    setError("");
    getEmployees(urlState)
      .then((data) => {
        if (active && sequence === requestSequence.current) setResult(data);
      })
      .catch((err) => {
        if (active && sequence === requestSequence.current) setError(err.message || "Unable to load employees.");
      })
      .finally(() => {
        if (active && sequence === requestSequence.current) setLoading(false);
      });
    return () => { active = false; };
  }, [urlState]);

  function updateFilter(name, value) {
    const next = new URLSearchParams(queryString);
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete("page");
    setSearchParams(next);
  }

  function changePage(page) {
    const next = new URLSearchParams(queryString);
    if (page <= 1) next.delete("page");
    else next.set("page", String(page));
    setSearchParams(next);
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Directory</p>
          <h1>Employees</h1>
          <p className="page-subtitle">Search and filter your employee records.</p>
        </div>
      </div>

      <section className="panel employee-panel">
        <div className="employee-toolbar">
          <label className="search-field">
            <span>Search employees</span>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => {
                requestSequence.current += 1;
                setLoading(event.target.value.trim() !== urlState.search);
                setSearchInput(event.target.value);
              }}
              placeholder="Name or employee ID"
            />
          </label>
          {FILTERS.map(([name, label, optionsKey]) => (
            <label className="filter-field" key={name}>
              <span>{label}</span>
              <select
                value={urlState[name]}
                onChange={(event) => updateFilter(name, event.target.value)}
                disabled={!filters}
              >
                <option value="">All</option>
                {(filters?.[optionsKey] || []).map((option) => (
                  <option value={option} key={option}>{option}</option>
                ))}
              </select>
            </label>
          ))}
        </div>

        {filterError && <p className="filter-error" role="alert">Filter options: {filterError}</p>}

        {error ? (
          <div className="message error" role="alert">{error}</div>
        ) : loading ? (
          <div className="message" role="status">Loading employees…</div>
        ) : result?.items.length === 0 ? (
          <div className="empty-state employee-empty">No employees match</div>
        ) : (
          <div className="table-wrap">
            <table className="employee-table">
              <thead>
                <tr>
                  <th>Employee ID</th><th>Name</th><th>Department</th><th>Country</th><th>Status</th><th className="numeric">Annual salary</th>
                </tr>
              </thead>
              <tbody>
                {result?.items.map((employee) => (
                  <tr key={employee.employee_id}>
                    <td className="employee-id">{employee.employee_id}</td>
                    <td className="employee-name">{employee.name}</td>
                    <td>{employee.department}</td>
                    <td>{employee.country}</td>
                    <td><span className={`status-pill ${employee.employment_status.toLowerCase()}`}>{employee.employment_status}</span></td>
                    <td className="numeric salary">{formatSalary(employee.annual_gross_base_salary, employee.currency)} <span className="salary-currency">{employee.currency}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!error && result && !loading && (
          <div className="pagination">
            <span className="match-count">{result.total.toLocaleString()} {result.total === 1 ? "match" : "matches"}</span>
            <div className="page-controls">
              <span className="page-count">Page {result.page} of {result.total_pages}</span>
              <button type="button" onClick={() => changePage(urlState.page - 1)} disabled={urlState.page <= 1 || result.total_pages === 0}>Previous</button>
              <button type="button" onClick={() => changePage(urlState.page + 1)} disabled={urlState.page >= result.total_pages || result.total_pages === 0}>Next</button>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
