const DEFAULT_API_URL = import.meta.env.DEV ? "http://localhost:8000" : "/api";
const API_BASE_URL = (import.meta.env.VITE_API_URL || DEFAULT_API_URL).replace(/\/$/, "");

/** Send a request to the API and parse its response or throw a readable error. */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { Accept: "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Could not reach the API. Check that the backend is running.");
  }

  const text = await response.text();
  let body;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join("; ")
      : typeof detail === "string"
        ? detail
        : `Request failed with status ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.detail = detail;
    throw error;
  }

  if (response.status === 204) return null;

  if (body === undefined) {
    throw new Error("The API returned an empty response.");
  }
  if (body === null) {
    throw new Error("The API returned an invalid JSON response.");
  }
  return body;
}

/** Load salary summaries and overall headcount. */
export function getDashboard() {
  return request("/dashboard");
}

/** Load the values available for employee filters and form selections. */
export function getEmployeeFilterOptions() {
  return request("/employees/filters");
}

/** Preview the next employee ID for the create form. */
export function getNextEmployeeId() {
  return request("/employees/next-id");
}

/** Load a page of employees matching the supplied filters. */
export function getEmployees(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value !== undefined && value !== null) {
      query.set(key, String(value));
    }
  }
  return request(`/employees?${query.toString()}`);
}

/** Create an employee record from the supplied fields. */
export function createEmployee(employee) {
  return request("/employees", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(employee),
  });
}

/** Replace an employee's editable fields. */
export function updateEmployee(employeeId, employee) {
  return request(`/employees/${encodeURIComponent(employeeId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(employee),
  });
}

/** Delete the employee with the supplied ID. */
export function deleteEmployee(employeeId) {
  return request(`/employees/${encodeURIComponent(employeeId)}`, { method: "DELETE" });
}
