"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState = {
  /** undefined while loading, null when signed out. */
  user: User | null | undefined;
  setUser: (user: User | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((u) => !cancelled && setUser(u))
      .catch(() => !cancelled && setUser(null));
    const onSignedOut = () => setUser(null);
    window.addEventListener("hsn:signed-out", onSignedOut);
    return () => {
      cancelled = true;
      window.removeEventListener("hsn:signed-out", onSignedOut);
    };
  }, []);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, setUser, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Renders children only for a signed-in user; otherwise sends them to sign in and back. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (user === null) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [user, router, pathname]);

  if (!user) {
    return <p className="p-8 text-center text-slate-500">Loading…</p>;
  }
  return <>{children}</>;
}
