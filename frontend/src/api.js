const API_BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
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
    throw new Error(message);
  }

  if (body === undefined) {
    throw new Error("The API returned an empty response.");
  }
  if (body === null) {
    throw new Error("The API returned an invalid JSON response.");
  }
  return body;
}

export function getDashboard() {
  return request("/dashboard");
}

export function getEmployeeFilterOptions() {
  return request("/employees/filters");
}

export function getEmployees(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value !== undefined && value !== null) {
      query.set(key, String(value));
    }
  }
  return request(`/employees?${query.toString()}`);
}
