"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth";
import { Button, ErrorMessage, Field, inputClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

/** Only same-site paths, so a crafted ?next= cannot send the student to another site. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const { user, setUser } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [is13, setIs13] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, router, next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u =
        mode === "login"
          ? await api.login({ email, password })
          : await api.signup({ email, password, display_name: name, confirms_age_13_plus: is13 });
      setUser(u);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const signup = mode === "signup";
  return (
    <div className="mx-auto max-w-md py-8">
      <h1 className="text-3xl font-bold text-slate-900">{signup ? "Create your account" : "Welcome back"}</h1>
      <p className="mt-2 text-slate-600">
        {signup
          ? "Turn class notes, handouts and chapters into study guides you can actually learn from."
          : "Sign in to see your study guides."}
      </p>
      <form
        onSubmit={submit}
        className="mt-8 space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        {signup && (
          <Field label="Your first name">
            <input
              className={inputClass}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={80}
              autoComplete="given-name"
            />
          </Field>
        )}
        <Field label="Email">
          <input
            className={inputClass}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </Field>
        <Field label="Password" hint={signup ? "At least 8 characters." : undefined}>
          <input
            className={inputClass}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={signup ? 8 : undefined}
            autoComplete={signup ? "new-password" : "current-password"}
          />
        </Field>
        {signup && (
          <label className="flex items-start gap-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={is13}
              onChange={(e) => setIs13(e.target.checked)}
              required
              className="mt-0.5 h-4 w-4 accent-indigo-600"
            />
            I am 13 or older.
          </label>
        )}
        <ErrorMessage>{error}</ErrorMessage>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "One moment…" : signup ? "Create account" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        {signup ? "Already have an account? " : "New here? "}
        <Link
          href={`${signup ? "/login" : "/signup"}${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`}
          className="font-medium text-indigo-700 hover:underline"
        >
          {signup ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </div>
  );
}
