import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { APP_API, CHAT_API, request, signOut } from "../api.js";
import BookViewer from "../BookViewer.jsx";
import { useReader } from "../useReader.js";

export default function Chat() {
  const user = useReader();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const sessionId = params.get("session");
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState(null);
  const [bookId, setBookId] = useState(null);
  const [book, setBook] = useState(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!user) return undefined;
    let stopped = false;
    request(`${CHAT_API}/users/${user.user_id}/sessions`)
      .then((rows) => {
        if (!stopped) setSessions(rows);
      })
      .catch((err) => {
        if (!stopped) setError(err.message);
      });
    return () => {
      stopped = true;
    };
  }, [user, messages]);

  useEffect(() => {
    if (!user || !sessionId) {
      setMessages(null);
      setBookId(null);
      return undefined;
    }
    let stopped = false;
    request(`${CHAT_API}/users/${user.user_id}/sessions/${sessionId}`)
      .then((session) => {
        if (stopped) return;
        setBookId(session.book_id);
        setMessages(session.messages.filter((message) => message.turn !== "system"));
      })
      .catch((err) => {
        if (!stopped) setError(err.message);
      });
    return () => {
      stopped = true;
    };
  }, [user, sessionId]);

  useEffect(() => {
    if (!user || !bookId) {
      setBook(null);
      return undefined;
    }
    let stopped = false;
    request(`${APP_API}/users/${user.user_id}/books/${bookId}`)
      .then((status) => {
        if (!stopped) setBook(status);
      })
      .catch((err) => {
        if (!stopped) setError(err.message);
      });
    return () => {
      stopped = true;
    };
  }, [user, bookId]);

  if (!user) return null;

  async function onSend(event) {
    event.preventDefault();
    const input = event.currentTarget.elements.msg;
    const msg = input.value.trim();
    if (!msg || !sessionId) return;
    input.value = "";
    setError("");
    setSending(true);
    setMessages((current) => [...(current ?? []), { turn: "user", content: msg }]);
    try {
      const reply = await request(`${CHAT_API}/infer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, msg }),
      });
      setMessages((current) => [...(current ?? []), { turn: "ai", content: reply.message }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
      input.focus();
    }
  }

  const visible = messages ?? [];

  return (
    <div className="chat-shell">
      <aside className="sidebar">
        <header>
          <p className="eyebrow">Chats</p>
          <Link to="/books">Upload a book</Link>
        </header>
        <ul className="session-list">
          {sessions.length === 0 && <li className="hint">No chats yet.</li>}
          {sessions.map((session) => (
            <li key={session.session_id}>
              <button
                type="button"
                aria-current={session.session_id === sessionId ? "true" : undefined}
                onClick={() => setParams({ session: session.session_id })}
              >
                {session.preview}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="thread">
        <header className="topbar">
          <strong>{user.name || user.username}</strong>
          <button className="ghost" type="button" onClick={() => { signOut(); navigate("/"); }}>
            Sign out
          </button>
        </header>
        <div className="messages">
          {!sessionId && <p className="empty">Choose a chat on the left, or start one from a parsed book.</p>}
          {sessionId && visible.length === 0 && messages && (
            <p className="empty">The book is loaded. Ask the first question.</p>
          )}
          {visible.map((message, index) => (
            <article className={`bubble ${message.turn}`} key={`${message.turn}-${index}`}>
              {message.content}
            </article>
          ))}
        </div>
        {sessionId && (
          <form className="composer" onSubmit={onSend}>
            <input name="msg" type="text" placeholder="Ask about this book" required autoComplete="off" />
            <button className="primary" type="submit" disabled={sending}>Send</button>
          </form>
        )}
        <p className="error" role="alert">{error}</p>
      </section>
      <aside className="reader">
        <header>
          <p className="eyebrow">Book</p>
          <strong>{book ? book.name : "No book open"}</strong>
        </header>
        {!sessionId && <p className="empty">Choose a chat to open its book.</p>}
        {sessionId && !bookId && <p className="empty">This chat is not linked to a book.</p>}
        {book && !book.viewable && (
          <p className="empty">This book is not a PDF, so it stays out of the viewer.</p>
        )}
        {book && book.viewable && (
          <BookViewer url={`${APP_API}/users/${user.user_id}/books/${book.book_id}/file`} />
        )}
      </aside>
    </div>
  );
}
