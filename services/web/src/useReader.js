import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { currentUser } from "./api.js";

export function useReader() {
  const navigate = useNavigate();
  const [user] = useState(currentUser);

  useEffect(() => {
    if (!user) navigate("/", { replace: true });
  }, [user, navigate]);

  return user;
}
