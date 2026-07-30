import { useCallback, useEffect, useState } from "react";
import type { User } from "../types";
import * as api from "../lib/api";

const TOKEN_KEY = "rag_auth_token";

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Auth state backed by a JWT in localStorage. On mount (and whenever the token
 * changes) the token is validated against /api/auth/me, so a stale/expired
 * token cleanly logs the user out. `ready` flips true once that check settles.
 */
export function useAuth() {
  const [token, setToken] = useState<string | null>(readToken);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    if (!token) {
      setUser(null);
      setReady(true);
      return;
    }
    api.fetchMe(token).then((u) => {
      if (!active) return;
      if (u) {
        setUser(u);
      } else {
        setUser(null);
        setToken(null);
        try {
          localStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
      }
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [token]);

  const persist = (t: string, u: User) => {
    try {
      localStorage.setItem(TOKEN_KEY, t);
    } catch {
      /* ignore */
    }
    setUser(u);
    setToken(t);
  };

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    persist(res.token, res.user);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await api.register(email, password);
    persist(res.token, res.user);
  }, []);

  const googleLogin = useCallback(async (credential: string) => {
    const res = await api.googleAuth(credential);
    persist(res.token, res.user);
  }, []);

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setUser(null);
    setToken(null);
  }, []);

  return { token, user, ready, login, register, googleLogin, logout };
}
