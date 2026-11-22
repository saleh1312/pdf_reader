import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_API, currentUser, request, saveUser } from "../api.js";

export default function Auth() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("signup");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (currentUser()) return <Navigate to="/books" replace />;

  async function remember(userId) {
    const profile = await request(`${APP_API}/users/${userId}`);
    saveUser(profile);
    navigate("/books");
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const path = mode === "signup" ? "/sign_up" : "/sign_in";
      const result = await request(`${APP_API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      await remember(result.user_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth">
      <section className="card">
        <p className="eyebrow">Reader</p>
        <h1>Your books, in conversation.</h1>
        <p className="lede">Create an account or sign in. The next page is where a book becomes a chat.</p>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "signup"} onClick={() => setMode("signup")}>
            Sign up
          </button>
          <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => setMode("login")}>
            Log in
          </button>
        </div>
        <form onSubmit={onSubmit}>
          {mode === "signup" && (
            <label>
              Name
              <input name="name" type="text" required autoComplete="name" />
            </label>
          )}
          <label>
            Username
            <input name="username" type="text" required autoComplete="username" />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              required
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
            />
          </label>
          <button className="primary" type="submit" disabled={pending}>
            {mode === "signup" ? "Create account" : "Log in"}
          </button>
        </form>
        <p className="error" role="alert">{error}</p>
      </section>
    </main>
  );
}
