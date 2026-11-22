function required(name) {
  const value = import.meta.env[name];
  if (!value) {
    throw new Error(`${name} is missing from services/web/.env`);
  }
  return value;
}

export const APP_API = required("VITE_APP_API");
export const CHAT_API = required("VITE_CHAT_API");

export function currentUser() {
  const raw = localStorage.getItem("reader");
  return raw ? JSON.parse(raw) : null;
}

export function saveUser(user) {
  localStorage.setItem("reader", JSON.stringify(user));
}

export function signOut() {
  localStorage.removeItem("reader");
}

export async function request(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = body && body.detail ? body.detail : response.statusText;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return body;
}
