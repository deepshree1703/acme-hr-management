import { useEffect, useState } from "react";
import {
  getDashboard,
  getDashboardByCountry,
  getDashboardByDepartment,
  getEmployeeFilterOptions,
} from "../api.js";

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

const EMPTY_FILTERS = {
  department: "",
  country: "",
  employment_status: "",
};

/** Load and display filtered salary summaries across currencies and dimensions. */
export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [breakdownBy, setBreakdownBy] = useState("department");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState(null);
  const [filterError, setFilterError] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getEmployeeFilterOptions()
      .then((options) => { if (active) setFilterOptions(options); })
      .catch((err) => {
        if (active) setFilterError(err.message || "Unable to load dashboard filters.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    const getBreakdown = breakdownBy === "department"
      ? getDashboardByDepartment
      : getDashboardByCountry;
    setLoading(true);
    setError("");
    Promise.all([getDashboard(filters), getBreakdown(filters)])
      .then(([summary, groups]) => {
        if (active) {
          setDashboard(summary);
          setBreakdown(groups);
        }
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load the dashboard.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [filters, breakdownBy]);

  /** Change one dashboard filter and reload every dashboard figure. */
  function updateFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  /** Clear all dashboard filters. */
  function clearFilters() {
    setFilters({ ...EMPTY_FILTERS });
  }

  const hasFilters = Object.values(filters).some(Boolean);
  const breakdownRows = (breakdown || []).flatMap((group) => group.currencies.map((currency) => ({
    key: `${group.name}-${currency.currency}`,
    name: group.name,
    ...currency,
  })));

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Salary dashboard</h1>
          <p className="page-subtitle">A snapshot of your global workforce.</p>
        </div>
      </div>

      <section className="panel employee-toolbar dashboard-filters" aria-label="Dashboard filters">
        <label className="filter-field">
          <span>Department</span>
          <select
            value={filters.department}
            onChange={(event) => updateFilter("department", event.target.value)}
            disabled={!filterOptions}
          >
            <option value="">All</option>
            {(filterOptions?.departments || []).map((department) => (
              <option value={department} key={department}>{department}</option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span>Country</span>
          <select
            value={filters.country}
            onChange={(event) => updateFilter("country", event.target.value)}
            disabled={!filterOptions}
          >
            <option value="">All</option>
            {(filterOptions?.countries || []).map((country) => (
              <option value={country} key={country}>{country}</option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span>Status</span>
          <select
            value={filters.employment_status}
            onChange={(event) => updateFilter("employment_status", event.target.value)}
            disabled={!filterOptions}
          >
            <option value="">All</option>
            {(filterOptions?.employment_statuses || []).map((status) => (
              <option value={status} key={status}>{status}</option>
            ))}
          </select>
        </label>
        <button
          className="button-secondary clear-filters"
          type="button"
          onClick={clearFilters}
          disabled={!hasFilters}
        >
          Clear filters
        </button>
      </section>
      {filterError && <p className="filter-error" role="alert">Filter options: {filterError}</p>}

      {error ? (
        <div className="message error" role="alert">{error}</div>
      ) : loading || dashboard === null || breakdown === null ? (
        <div className="message" role="status">Loading dashboard…</div>
      ) : (
        <>
          <section className="panel headcount-card" aria-label="Overall headcount">
            <div className="metric-icon" aria-hidden="true">👥</div>
            <div>
              <p className="metric-label">Overall headcount</p>
              <p className="metric-value">{dashboard.total_headcount.toLocaleString()}</p>
              <p className="metric-caption">Employees across all currencies</p>
            </div>
          </section>

          <section className="panel summary-panel">
            <div className="section-heading">
              <div>
                <h2>Salary by currency</h2>
                <p>Headcount and annual gross base salary by currency</p>
              </div>
              <span className="section-badge">{dashboard.currencies.length} currencies</span>
            </div>
            {dashboard.currencies.length === 0 ? (
              <p className="empty-state">No salary data matches these filters.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Currency</th>
                      <th className="numeric">Headcount</th>
                      <th className="numeric">Average annual salary</th>
                      <th className="numeric">Minimum annual salary</th>
                      <th className="numeric">Maximum annual salary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.currencies.map((row) => (
                      <tr key={row.currency}>
                        <td><span className="currency-code">{row.currency}</span></td>
                        <td className="numeric">{row.headcount.toLocaleString()}</td>
                        <td className="numeric salary">{formatSalary(row.average_annual_gross_base_salary, row.currency)}</td>
                        <td className="numeric salary">{formatSalary(row.minimum_annual_gross_base_salary, row.currency)}</td>
                        <td className="numeric salary">{formatSalary(row.maximum_annual_gross_base_salary, row.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="table-note">Salary figures are shown in their respective currencies and are not combined.</p>
          </section>

          <section className="panel summary-panel breakdown-panel">
            <div className="section-heading">
              <div>
                <h2>Breakdown</h2>
                <p>Salary statistics by group and currency</p>
              </div>
              <label className="breakdown-selector">
                <span>Group by</span>
                <select value={breakdownBy} onChange={(event) => setBreakdownBy(event.target.value)}>
                  <option value="department">Department</option>
                  <option value="country">Country</option>
                </select>
              </label>
            </div>
            {breakdownRows.length === 0 ? (
              <p className="empty-state">No breakdown data matches these filters.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{breakdownBy === "department" ? "Department" : "Country"}</th>
                      <th>Currency</th>
                      <th className="numeric">Headcount</th>
                      <th className="numeric">Average annual salary</th>
                      <th className="numeric">Minimum annual salary</th>
                      <th className="numeric">Maximum annual salary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {breakdownRows.map((row) => (
                      <tr key={row.key}>
                        <td>{row.name}</td>
                        <td><span className="currency-code">{row.currency}</span></td>
                        <td className="numeric">{row.headcount.toLocaleString()}</td>
                        <td className="numeric salary">{formatSalary(row.average_annual_gross_base_salary, row.currency)}</td>
                        <td className="numeric salary">{formatSalary(row.minimum_annual_gross_base_salary, row.currency)}</td>
                        <td className="numeric salary">{formatSalary(row.maximum_annual_gross_base_salary, row.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="table-note">Each row keeps one currency separate; salary values are never added or averaged across currencies.</p>
          </section>
        </>
      )}
    </>
  );
}
