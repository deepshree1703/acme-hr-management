import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createEmployee,
  deleteEmployee,
  getEmployeeFilterOptions,
  getEmployees,
  getNextEmployeeId,
  updateEmployee,
} from "../api.js";

const MAX_SALARY = 9999999999.99;
const SALARY_LIMIT_MESSAGE = "Salary can have at most 10 digits before the decimal and 2 after (maximum 9999999999.99).";

/** Parse a positive page number, defaulting invalid values to page one. */
function readPage(value) {
  const parsed = Number.parseInt(value || "1", 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

/** Format a salary as currency, falling back when the currency is unsupported. */
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

/** Return a readable error for invalid currency-scoped salary bounds. */
function salaryRangeError({ currency, min_salary: minSalary, max_salary: maxSalary }) {
  const hasMin = minSalary !== "";
  const hasMax = maxSalary !== "";
  const minimum = Number(minSalary);
  const maximum = Number(maxSalary);

  if (hasMin && (!Number.isFinite(minimum) || minimum < 0)) {
    return "Minimum salary must be a finite number of at least 0.";
  }
  if (hasMax && (!Number.isFinite(maximum) || maximum < 0)) {
    return "Maximum salary must be a finite number of at least 0.";
  }
  if ((hasMin || hasMax) && !currency) {
    return "Select a currency to filter by salary.";
  }
  if (hasMin && hasMax && minimum > maximum) {
    return "Minimum salary must be less than or equal to maximum salary.";
  }
  return "";
}

const EMPTY_EMPLOYEE = {
  name: "",
  department: "",
  designation: "",
  country: "",
  employment_status: "Active",
  annual_gross_base_salary: "",
  currency: "USD",
};

const EMPLOYEE_FIELDS = [
  ["name", "Name"],
  ["department", "Department"],
  ["designation", "Designation"],
  ["country", "Country"],
  ["employment_status", "Employment status"],
  ["annual_gross_base_salary", "Annual salary"],
  ["currency", "Currency"],
];

/** Render the employee create/edit form and handle its validation and submission. */
function EmployeeForm({ employee, filters, onClose, onSaved }) {
  const editing = Boolean(employee);
  const [values, setValues] = useState(() => employee
    ? { ...employee, annual_gross_base_salary: String(employee.annual_gross_base_salary) }
    : { ...EMPTY_EMPLOYEE });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewId, setPreviewId] = useState(employee?.employee_id || "");

  useEffect(() => {
    if (editing) return undefined;
    let active = true;
    getNextEmployeeId()
      .then((result) => {
        if (active) {
          setPreviewId(result.employee_id);
          setFieldErrors((current) => ({ ...current, employee_id: undefined }));
        }
      })
      .catch((error) => {
        if (active) setFieldErrors((current) => ({
          ...current,
          employee_id: error.message || "Unable to preview the employee ID.",
        }));
      });
    return () => { active = false; };
  }, [editing]);

  /** Update a field value and clear its validation error. */
  function setValue(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
    setFormError("");
  }

  /** Sanitize salary input and report values outside the supported limits. */
  function setSalaryValue(rawValue) {
    const negativeSign = rawValue.startsWith("-");
    let sanitized = rawValue.replace(/[^\d.]/g, "");
    const decimalPoint = sanitized.indexOf(".");
    if (decimalPoint !== -1) {
      sanitized = `${sanitized.slice(0, decimalPoint)}.${sanitized.slice(decimalPoint + 1).replace(/\./g, "")}`;
    }
    if (sanitized.startsWith(".")) sanitized = `0${sanitized}`;
    const [whole = "", fraction] = sanitized.split(".");
    const hadDecimal = sanitized.includes(".");
    const tooManyWholeDigits = whole.length > 10;
    const tooManyFractionDigits = (fraction || "").length > 2;
    const limited = `${whole.slice(0, 10)}${hadDecimal ? `.${(fraction || "").slice(0, 2)}` : ""}`;
    const value = `${negativeSign ? "-" : ""}${limited}`;
    const numericSalary = Number(value);
    let error;
    if (negativeSign && numericSalary < 0) error = "Salary cannot be negative.";
    else if (tooManyWholeDigits || tooManyFractionDigits) error = SALARY_LIMIT_MESSAGE;
    else if (value && value !== "-" && numericSalary > MAX_SALARY) error = SALARY_LIMIT_MESSAGE;
    setValues((current) => ({ ...current, annual_gross_base_salary: value }));
    setFieldErrors((current) => ({ ...current, annual_gross_base_salary: error }));
    setFormError("");
  }

  /** Return a validation message when the salary value is invalid. */
  function salaryError(value) {
    if (!value) return "Annual salary is required.";
    if (value.startsWith("-")) return "Salary cannot be negative.";
    if (!/^\d{1,10}(?:\.\d{1,2})?$/.test(value)) return SALARY_LIMIT_MESSAGE;
    if (Number(value) > MAX_SALARY) return SALARY_LIMIT_MESSAGE;
    return "";
  }

  /** Validate and submit the employee form. */
  async function submit(event) {
    event.preventDefault();
    const errors = {};
    for (const [name, label] of EMPLOYEE_FIELDS) {
      if (!String(values[name] ?? "").trim()) errors[name] = `${label} is required.`;
    }
    const rawSalary = values.annual_gross_base_salary;
    const salaryValidationError = salaryError(rawSalary);
    if (salaryValidationError) errors.annual_gross_base_salary = salaryValidationError;
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }

    const payload = {
      name: values.name.trim(),
      department: values.department.trim(),
      designation: values.designation.trim(),
      country: values.country.trim(),
      employment_status: values.employment_status,
      annual_gross_base_salary: Number(rawSalary),
      currency: values.currency,
    };
    setSaving(true);
    setFieldErrors({});
    setFormError("");
    try {
      const savedEmployee = editing
        ? await updateEmployee(employee.employee_id, payload)
        : await createEmployee(payload);
      onSaved(savedEmployee);
    } catch (error) {
      if (error.status === 422 && Array.isArray(error.detail)) {
        const mapped = {};
        const messages = [];
        for (const issue of error.detail) {
          const location = issue.loc || [];
          const field = location[location.length - 1];
          if (EMPLOYEE_FIELDS.some(([name]) => name === field)) {
            mapped[field] = issue.msg;
          } else {
            messages.push(issue.msg);
          }
        }
        setFieldErrors(mapped);
        if (messages.length) setFormError(messages.join("; "));
      } else if (error.status === 409) {
        setFieldErrors({ employee_id: error.message });
      } else {
        setFormError(error.message || "Unable to save this employee.");
      }
    } finally {
      setSaving(false);
    }
  }

  /** Render the control and validation feedback for one employee field. */
  function renderField(name, label) {
    const common = {
      id: `employee-${name}`,
      value: values[name] ?? "",
      onChange: (event) => name === "annual_gross_base_salary"
        ? setSalaryValue(event.target.value)
        : setValue(name, event.target.value),
      disabled: saving,
      "aria-invalid": Boolean(fieldErrors[name]),
      "aria-describedby": fieldErrors[name] ? `employee-${name}-error` : undefined,
    };
    let control;
    if (name === "employment_status" || name === "currency") {
      const options = name === "currency" ? filters?.currencies : filters?.employment_statuses;
      control = <select {...common} required>
        {(options || []).map((option) => <option value={option} key={option}>{option}</option>)}
      </select>;
    } else if (name === "department" || name === "country") {
      const listId = `employee-${name}-options`;
      const options = name === "department" ? filters?.departments : filters?.countries;
      control = <>
        <input {...common} list={listId} required />
        <datalist id={listId}>{(options || []).map((option) => <option value={option} key={option} />)}</datalist>
      </>;
    } else {
      control = <input
        {...common}
        required
        type="text"
        inputMode={name === "annual_gross_base_salary" ? "decimal" : undefined}
        autoComplete={name === "name" ? "name" : "off"}
        placeholder={name === "annual_gross_base_salary" ? "0.00" : undefined}
      />;
    }
    return <label className="employee-form-field" htmlFor={`employee-${name}`} key={name}>
      <span>{label}</span>
      {control}
      {name === "annual_gross_base_salary" && <small className="field-hint">Up to 10 digits before the decimal and 2 after.</small>}
      {fieldErrors[name] && <small className="field-error" id={`employee-${name}-error`}>{fieldErrors[name]}</small>}
    </label>;
  }

  /** Render the read-only employee ID field and its preview status. */
  function renderEmployeeId() {
    const errorId = "employee-employee_id-error";
    return <label className="employee-form-field" htmlFor="employee-employee_id" key="employee_id">
      <span>Employee ID</span>
      <input
        id="employee-employee_id"
        value={previewId}
        readOnly
        aria-invalid={Boolean(fieldErrors.employee_id)}
        aria-describedby={fieldErrors.employee_id ? errorId : undefined}
        placeholder={editing ? "" : "Loading ID…"}
      />
      {!editing && <small className="field-hint">Assigned automatically when the employee is saved.</small>}
      {fieldErrors.employee_id && <small className="field-error" id={errorId}>{fieldErrors.employee_id}</small>}
    </label>;
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget && !saving) onClose();
  }}>
    <section className="employee-modal" role="dialog" aria-modal="true" aria-labelledby="employee-form-title">
      <div className="modal-heading">
        <div>
          <p className="eyebrow">Employee record</p>
          <h2 id="employee-form-title">{editing ? "Edit employee" : "Add employee"}</h2>
        </div>
        <button className="modal-close" type="button" onClick={onClose} disabled={saving} aria-label="Close">×</button>
      </div>
      {formError && <p className="form-error" role="alert">{formError}</p>}
      <form onSubmit={submit} noValidate>
        <div className="employee-form-grid">
          {renderEmployeeId()}
          {EMPLOYEE_FIELDS.map(([name, label]) => renderField(name, label))}
        </div>
        <div className="form-actions">
          <button type="button" className="button-secondary" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="button-primary" disabled={saving}>{saving ? "Saving…" : editing ? "Save changes" : "Add employee"}</button>
        </div>
      </form>
    </section>
  </div>;
}

/** Display the employee directory, filters, pagination, and edit actions. */
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
      currency: params.get("currency") || "",
      min_salary: params.get("min_salary") || "",
      max_salary: params.get("max_salary") || "",
      page: readPage(params.get("page")),
    };
  }, [queryString]);

  const [searchInput, setSearchInput] = useState(urlState.search);
  const [filters, setFilters] = useState(null);
  const [filterError, setFilterError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formEmployee, setFormEmployee] = useState(undefined);
  const [mutationError, setMutationError] = useState("");
  const [mutationNotice, setMutationNotice] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const requestSequence = useRef(0);
  const rangeError = salaryRangeError(urlState);

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
    if (salaryRangeError(urlState)) {
      setLoading(false);
      setError("");
      return () => { active = false; };
    }
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
  }, [urlState, refreshKey]);

  /** Close the form, show a save notice, and refresh the employee list. */
  function finishSave(savedEmployee) {
    setFormEmployee(undefined);
    setMutationError("");
    setMutationNotice(savedEmployee?.employee_id ? `Saved employee ${savedEmployee.employee_id}.` : "Employee saved.");
    setRefreshKey((value) => value + 1);
  }

  /** Confirm and delete an employee, then keep pagination in a valid state. */
  async function removeEmployee(employee) {
    const confirmed = window.confirm(`Delete ${employee.name} (${employee.employee_id})? This cannot be undone.`);
    if (!confirmed) return;
    setMutationError("");
    setMutationNotice("");
    setDeletingId(employee.employee_id);
    try {
      await deleteEmployee(employee.employee_id);
      const newTotalPages = Math.ceil(Math.max(0, (result?.total || 0) - 1) / (result?.page_size || 20));
      if (urlState.page > newTotalPages && urlState.page > 1) {
        const next = new URLSearchParams(queryString);
        const lastPage = Math.max(1, newTotalPages);
        if (lastPage === 1) next.delete("page");
        else next.set("page", String(lastPage));
        setSearchParams(next);
      } else {
        setRefreshKey((value) => value + 1);
      }
    } catch (err) {
      setMutationError(err.message || "Unable to delete this employee.");
    } finally {
      setDeletingId("");
    }
  }

  /** Update one URL-backed filter and reset pagination. */
  function updateFilter(name, value) {
    const next = new URLSearchParams(queryString);
    if (value) next.set(name, value);
    else next.delete(name);
    if (name === "currency" && !value) {
      next.delete("min_salary");
      next.delete("max_salary");
    }
    next.delete("page");
    setSearchParams(next);
  }

  /** Clear search, filters, and pagination together. */
  function clearFilters() {
    requestSequence.current += 1;
    setSearchInput("");
    setSearchParams(new URLSearchParams());
  }

  /** Navigate to a page while preserving the current URL filters. */
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
        <button className="button-primary add-employee-button" type="button" onClick={() => setFormEmployee(null)} disabled={!filters}>
          + Add employee
        </button>
      </div>

      <section className="panel employee-panel">
        {mutationError && <p className="mutation-error" role="alert">{mutationError}</p>}
        {mutationNotice && <p className="mutation-notice" role="status">{mutationNotice}</p>}
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
          <label className="filter-field" htmlFor="employee-currency-filter">
            <span>Currency</span>
            <select
              id="employee-currency-filter"
              value={urlState.currency}
              onChange={(event) => updateFilter("currency", event.target.value)}
              disabled={!filters}
            >
              <option value="">All</option>
              {(filters?.currencies || []).map((currency) => (
                <option value={currency} key={currency}>{currency}</option>
              ))}
            </select>
          </label>
          <label className="filter-field" htmlFor="employee-min-salary-filter">
            <span>Min salary</span>
            <input
              id="employee-min-salary-filter"
              type="number"
              min="0"
              step="any"
              value={urlState.min_salary}
              onChange={(event) => updateFilter("min_salary", event.target.value)}
              disabled={!urlState.currency}
            />
          </label>
          <label className="filter-field" htmlFor="employee-max-salary-filter">
            <span>Max salary</span>
            <input
              id="employee-max-salary-filter"
              type="number"
              min="0"
              step="any"
              value={urlState.max_salary}
              onChange={(event) => updateFilter("max_salary", event.target.value)}
              disabled={!urlState.currency}
            />
          </label>
          <button
            className="button-secondary clear-filters"
            type="button"
            onClick={clearFilters}
            disabled={!searchInput.trim() && !urlState.search && !urlState.country && !urlState.department &&
              !urlState.employment_status && !urlState.currency && !urlState.min_salary &&
              !urlState.max_salary && urlState.page === 1}
          >
            Clear filters
          </button>
        </div>

        {urlState.currency === "" && <p className="salary-filter-hint">Select a currency to filter by salary.</p>}
        {rangeError && <p className="filter-error" role="alert">{rangeError}</p>}
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
                  <th>Employee ID</th><th>Name</th><th>Department</th><th>Designation</th><th>Country</th><th>Status</th><th className="numeric">Annual salary</th><th className="actions-heading">Actions</th>
                </tr>
              </thead>
              <tbody>
                {result?.items.map((employee) => (
                  <tr key={employee.employee_id}>
                    <td className="employee-id">{employee.employee_id}</td>
                    <td className="employee-name">{employee.name}</td>
                    <td>{employee.department}</td>
                    <td>{employee.designation}</td>
                    <td>{employee.country}</td>
                    <td><span className={`status-pill ${employee.employment_status.toLowerCase()}`}>{employee.employment_status}</span></td>
                    <td className="numeric salary">{formatSalary(employee.annual_gross_base_salary, employee.currency)} <span className="salary-currency">{employee.currency}</span></td>
                    <td className="row-actions">
                      <button type="button" onClick={() => setFormEmployee(employee)}>Edit</button>
                      <button type="button" className="delete-action" onClick={() => removeEmployee(employee)} disabled={deletingId === employee.employee_id}>
                        {deletingId === employee.employee_id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
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
      {formEmployee !== undefined && filters && (
        <EmployeeForm
          employee={formEmployee}
          filters={filters}
          onClose={() => setFormEmployee(undefined)}
          onSaved={finishSave}
        />
      )}
    </>
  );
}
