"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth";
import { Button, ErrorMessage, Field, inputClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { LEVELS } from "@/lib/labels";
import type { Level } from "@/lib/types";

export default function AccountPage() {
  const { user, setUser, signOut } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(user?.display_name ?? "");
  const [level, setLevel] = useState<Level>((user?.default_level as Level) ?? "high_school");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  if (!user) return null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      setUser(await api.updateMe({ display_name: name, default_level: level }));
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    }
  }

  async function deleteAccount() {
    setDeleting(true);
    setError(null);
    try {
      await api.deleteMe();
      setUser(null);
      router.replace("/signup");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete your account.");
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-8">
      <h1 className="text-3xl font-bold text-slate-900">Your account</h1>

      <form onSubmit={save} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">Signed in as {user.email}</p>
        <Field label="Name">
          <input
            className={inputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={80}
          />
        </Field>
        <Field label="Usual level" hint="New guides are explained at this level unless you pick another.">
          <select className={inputClass} value={level} onChange={(e) => setLevel(e.target.value as Level)}>
            {LEVELS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </Field>
        <ErrorMessage>{error}</ErrorMessage>
        <div className="flex items-center gap-3">
          <Button type="submit">Save</Button>
          {saved && <span className="text-sm text-emerald-700">Saved</span>}
        </div>
      </form>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <Button
          variant="secondary"
          onClick={async () => {
            await signOut();
            router.push("/login");
          }}
        >
          Sign out
        </Button>
      </div>

      <section className="space-y-3 rounded-2xl border border-rose-200 bg-white p-6">
        <h2 className="font-semibold text-rose-900">Delete your account</h2>
        <p className="text-sm text-slate-600">
          This permanently deletes your account, every file you uploaded, your study guides and your quiz
          history. It can&apos;t be undone.
        </p>
        <Field label="Type DELETE to confirm">
          <input
            className={inputClass}
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
          />
        </Field>
        <Button variant="danger" disabled={confirmText !== "DELETE" || deleting} onClick={deleteAccount}>
          {deleting ? "Deleting…" : "Delete everything"}
        </Button>
      </section>
    </div>
  );
}
