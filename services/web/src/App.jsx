import { Route, Routes } from "react-router-dom";

import Auth from "./pages/Auth.jsx";
import Books from "./pages/Books.jsx";
import Chat from "./pages/Chat.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Auth />} />
      <Route path="/books" element={<Books />} />
      <Route path="/chat" element={<Chat />} />
    </Routes>
  );
}
