import { useEffect, useState } from "react";
import { getDashboard } from "../api.js";

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

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getDashboard()
      .then((data) => {
        if (active) setDashboard(data);
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load the dashboard.");
      });
    return () => { active = false; };
  }, []);

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Salary dashboard</h1>
          <p className="page-subtitle">A snapshot of your global workforce.</p>
        </div>
      </div>

      {error ? (
        <div className="message error" role="alert">{error}</div>
      ) : dashboard === null ? (
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
                <p>Headcount and average annual gross base salary</p>
              </div>
              <span className="section-badge">{dashboard.currencies.length} currencies</span>
            </div>
            {dashboard.currencies.length === 0 ? (
              <p className="empty-state">No salary data is available yet.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Currency</th><th className="numeric">Headcount</th><th className="numeric">Average annual salary</th></tr>
                  </thead>
                  <tbody>
                    {dashboard.currencies.map((row) => (
                      <tr key={row.currency}>
                        <td><span className="currency-code">{row.currency}</span></td>
                        <td className="numeric">{row.headcount.toLocaleString()}</td>
                        <td className="numeric salary">{formatSalary(row.average_annual_gross_base_salary, row.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="table-note">Average salaries are shown in their respective currencies and are not combined.</p>
          </section>
        </>
      )}
    </>
  );
}
