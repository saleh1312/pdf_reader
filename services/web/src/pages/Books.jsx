import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { APP_API, CHAT_API, request, signOut } from "../api.js";
import { useReader } from "../useReader.js";

export default function Books() {
  const user = useReader();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [book, setBook] = useState(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    if (!book || book.isParsed) return undefined;
    let stopped = false;

    async function poll() {
      try {
        const status = await request(`${APP_API}/users/${user.user_id}/books/${book.id}`);
        if (stopped) return;
        if (status.is_parsed) {
          setBook((current) => (current ? { ...current, isParsed: true } : current));
        }
      } catch (err) {
        if (!stopped) setError(err.message);
      }
    }

    poll();
    const timer = window.setInterval(poll, 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [book, user]);

  if (!user) return null;

  async function onUpload(event) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const chosen = form.elements.file.files[0];
    const entered = form.elements.bookName.value.trim();
    const data = new FormData();
    data.set("storage_provider", "local");
    data.set("file", chosen);
    if (entered) data.set("name", entered);
    try {
      const created = await request(`${APP_API}/users/${user.user_id}/books`, {
        method: "POST",
        body: data,
      });
      setBook({ id: created.book_id, name: entered || chosen.name, isParsed: false });
      form.reset();
    } catch (err) {
      setError(err.message);
    }
  }

  async function startSession() {
    setOpening(true);
    setError("");
    try {
      const created = await request(`${CHAT_API}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.user_id, book_id: book.id }),
      });
      navigate(`/chat?session=${created.session_id}`);
    } catch (err) {
      setError(err.message);
      setOpening(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <strong>{user.name || user.username}</strong>
        <nav>
          <Link to="/chat">Chats</Link>
          <button className="ghost" type="button" onClick={() => { signOut(); navigate("/"); }}>
            Sign out
          </button>
        </nav>
      </header>
      <main className="workspace">
        <p className="eyebrow">Library</p>
        <h1>Upload a book</h1>
        <p className="lede">PDF or Word. After it lands, this page checks once a second until parsing finishes.</p>
        <form className="card" onSubmit={onUpload}>
          <label>
            Book name
            <input name="bookName" type="text" placeholder="Optional" />
          </label>
          <label>
            File
            <input name="file" type="file" accept=".pdf,.doc,.docx" required />
          </label>
          <button className="primary" type="submit">Upload</button>
          <p className="error" role="alert">{error}</p>
        </form>
        {book && (
          <section className="book-card">
            <strong>{book.name}</strong>
            <p className="status">
              {book.isParsed ? "Parsed. You can start a chat." : "Parsing. Checking again in a second."}
            </p>
            {book.isParsed && (
              <button className="primary" type="button" disabled={opening} onClick={startSession}>
                New session
              </button>
            )}
          </section>
        )}
      </main>
    </>
  );
}
