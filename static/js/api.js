// Thin client for the Flask API. Every function resolves with parsed JSON
// (or null for 204) and rejects with an ApiError carrying the server's message.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) return null;

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(body.error || "Something went wrong. Please try again.", response.status);
  }
  return body;
}

export const listAppointments = () => request("/items");
export const listDoctors = () => request("/doctors");

export const bookAppointment = (payload) =>
  request("/items", { method: "POST", body: JSON.stringify(payload) });

export const setStatus = (id, status) =>
  request(`/items/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });

export const removeAppointment = (id) => request(`/items/${id}`, { method: "DELETE" });

export async function checkHealth() {
  const start = performance.now();
  try {
    const response = await fetch("/health", { cache: "no-store" });
    return { up: response.ok, ms: Math.round(performance.now() - start) };
  } catch (err) {
    return { up: false, ms: 0 };
  }
}
