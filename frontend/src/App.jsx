import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";

function EmployeesPlaceholder() {
  return (
    <section className="panel placeholder">
      <h1>Employees</h1>
      <p>The employee directory will be available here soon.</p>
    </section>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="ACME home">
          <span className="brand-mark">A</span>
          <span>ACME <span className="brand-light">People</span></span>
        </a>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/employees">Employees</NavLink>
        </nav>
      </header>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/employees" element={<EmployeesPlaceholder />} />
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  );
}
