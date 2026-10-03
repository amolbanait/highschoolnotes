"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth";
import { formatBytes, UploadDropzone } from "@/components/UploadDropzone";
import { Button, ErrorMessage, Field, inputClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate, LEVELS } from "@/lib/labels";
import type { Level, Source } from "@/lib/types";

const MAX_SOURCES = 5;
const MAX_WORDS = 40_000;

export default function NewGuidePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"upload" | "paste">("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [level, setLevel] = useState<Level>((user?.default_level as Level) ?? "high_school");
  const [previous, setPrevious] = useState<Source[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSources()
      .then((s) => setPrevious(s.filter((x) => x.status !== "failed")))
      .catch(() => undefined);
  }, []);

  const pasteWords = pasteText.trim() ? pasteText.trim().split(/\s+/).length : 0;
  const newCount = tab === "upload" ? files.length : pasteText.trim() ? 1 : 0;
  const total = newCount + picked.length;
  const busy = status !== null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (total === 0) {
      setError("Add a file, paste some text, or pick material you added before.");
      return;
    }
    if (total > MAX_SOURCES) {
      setError(`One guide can use up to ${MAX_SOURCES} pieces of material.`);
      return;
    }
    if (tab === "paste" && pasteText.trim() && pasteWords > MAX_WORDS) {
      setError(
        `That's about ${pasteWords.toLocaleString()} words; the limit is ${MAX_WORDS.toLocaleString()} per guide.`,
      );
      return;
    }
    const ids = [...picked];
    try {
      if (tab === "upload") {
        for (const [i, f] of files.entries()) {
          setStatus(files.length > 1 ? `Uploading ${i + 1} of ${files.length}…` : "Uploading…");
          ids.push((await api.uploadSource(f)).id);
        }
      } else if (pasteText.trim()) {
        setStatus("Saving your text…");
        ids.push((await api.pasteSource(pasteTitle.trim() || "Pasted notes", pasteText)).id);
      }
      setStatus("Starting your guide…");
      const { guide_id } = await api.createGuide(ids, level);
      router.push(`/guides/${guide_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      // Anything already uploaded is kept: show it as picked so nothing is uploaded twice.
      const fresh = await api.listSources().catch(() => null);
      if (fresh) {
        setPrevious(fresh.filter((x) => x.status !== "failed"));
        setPicked(ids.filter((id) => fresh.some((s) => s.id === id)));
        setFiles([]);
        if (tab === "paste") setPasteText("");
      }
      setStatus(null);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">New study guide</h1>
        <p className="mt-1 text-slate-600">
          Add the material you need to learn. We&apos;ll explain it step by step, with examples, practice
          questions and flashcards.
        </p>
      </div>

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div role="tablist" className="inline-flex rounded-lg bg-slate-100 p-1">
          {(["upload", "paste"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`rounded-md px-4 py-1.5 text-sm ${tab === t ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}
            >
              {t === "upload" ? "Upload files" : "Paste text"}
            </button>
          ))}
        </div>
        {tab === "upload" ? (
          <UploadDropzone files={files} onChange={setFiles} />
        ) : (
          <div className="space-y-4">
            <Field label="Title">
              <input
                className={inputClass}
                value={pasteTitle}
                onChange={(e) => setPasteTitle(e.target.value)}
                placeholder="e.g. Chapter 8: Photosynthesis"
                maxLength={300}
              />
            </Field>
            <Field
              label="Your text"
              hint={`${pasteWords.toLocaleString()} words · up to ${MAX_WORDS.toLocaleString()}`}
            >
              <textarea
                className={`${inputClass} min-h-64 font-mono text-[13px]`}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder="Paste notes, a reading or a transcript. Headings in Markdown (# Heading) become sections."
              />
            </Field>
          </div>
        )}
        <p className="text-xs text-slate-500">
          Scanned pages (photos of text) can&apos;t be read yet. Use a PDF with selectable text.
        </p>
      </section>

      {previous.length > 0 && (
        <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-900">Or use material you added before</h2>
          <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto">
            {previous.map((s) => (
              <li key={s.id}>
                <label className="flex cursor-pointer items-center gap-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={picked.includes(s.id)}
                    onChange={(e) =>
                      setPicked((p) => (e.target.checked ? [...p, s.id] : p.filter((x) => x !== s.id)))
                    }
                    className="h-4 w-4 accent-indigo-600"
                  />
                  <span className="flex-1 truncate">{s.title}</span>
                  <span className="text-xs text-slate-400">
                    {s.word_count ? `${s.word_count.toLocaleString()} words` : formatBytes(s.byte_size)} ·{" "}
                    {formatDate(s.created_at)}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <Field label="Explain it for" hint="You can change your usual level in your account settings.">
          <select className={inputClass} value={level} onChange={(e) => setLevel(e.target.value as Level)}>
            {LEVELS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </Field>
      </section>

      <ErrorMessage>{error}</ErrorMessage>
      <div className="flex items-center gap-4">
        <Button type="submit" disabled={busy || total === 0} className="px-6 py-3 text-base">
          {status ?? "Make my study guide"}
        </Button>
        {total > 0 && !busy && (
          <span className="text-sm text-slate-500">
            {total} piece{total === 1 ? "" : "s"} of material
          </span>
        )}
      </div>
    </form>
  );
}
