"use client";

import { useRef, useState } from "react";

const DOCUMENTS = ["pdf", "docx", "txt", "md", "markdown", "png", "jpg", "jpeg", "webp"];
const RECORDINGS = [
  "mp3",
  "m4a",
  "wav",
  "ogg",
  "oga",
  "opus",
  "flac",
  "aac",
  "mp4",
  "m4v",
  "mov",
  "webm",
  "mkv",
];
export const ACCEPTED = [...DOCUMENTS, ...RECORDINGS].map((e) => `.${e}`).join(",");
export const MAX_BYTES = 20 * 1024 * 1024;
export const MAX_MEDIA_BYTES = 1024 * 1024 * 1024;
const MAX_FILES = 5;

/** The size limit for a file: recordings and videos may be much larger than documents. */
export function limitFor(name: string): number | null {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (RECORDINGS.includes(ext)) return MAX_MEDIA_BYTES;
  if (DOCUMENTS.includes(ext)) return MAX_BYTES;
  return null;
}

/** Drag-and-drop or click to choose up to five files. Checks type and size before upload. */
export function UploadDropzone({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function add(list: FileList | null) {
    if (!list) return;
    const next = [...files];
    for (const f of Array.from(list)) {
      const limit = limitFor(f.name);
      if (limit === null) {
        setProblem(
          `${f.name}: use a PDF, Word, text or Markdown file, a photo (PNG, JPEG, WebP), a recording (MP3, M4A, WAV) or a video (MP4, MOV, WebM).`,
        );
        continue;
      }
      if (f.size > limit) {
        setProblem(`${f.name} is larger than ${formatBytes(limit)}.`);
        continue;
      }
      if (next.length >= MAX_FILES) {
        setProblem(`One guide can use up to ${MAX_FILES} files.`);
        break;
      }
      if (!next.some((n) => n.name === f.name && n.size === f.size)) next.push(f);
    }
    onChange(next);
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          setProblem(null);
          add(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center ${
          dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-slate-50"
        }`}
      >
        <p className="font-medium text-slate-800">Drop your notes, handout, chapter or lecture here</p>
        <p className="mt-1 text-sm text-slate-500">
          PDF, Word, text, photos and scans · up to 20 MB each
          <br />
          Lecture recordings and class videos · up to 1 GB and 2 hours each
        </p>
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="mt-4 rounded-lg bg-white px-4 py-2 text-sm font-medium text-indigo-700 shadow-sm ring-1 ring-slate-200 hover:bg-indigo-50"
        >
          Choose files
        </button>
        <input
          ref={input}
          type="file"
          accept={ACCEPTED}
          multiple
          className="sr-only"
          aria-label="Choose files"
          onChange={(e) => {
            setProblem(null);
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {problem && <p className="mt-2 text-sm text-rose-700">{problem}</p>}
      {files.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {files.map((f) => (
            <li key={f.name + f.size} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="truncate">
                {f.name} <span className="text-slate-400">· {formatBytes(f.size)}</span>
              </span>
              <button
                type="button"
                onClick={() => onChange(files.filter((x) => x !== f))}
                className="ml-3 text-slate-500 hover:text-rose-700"
                aria-label={`Remove ${f.name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  if (n >= 1024 * 1024 * 1024 && n % (1024 * 1024 * 1024) === 0) return `${n / (1024 * 1024 * 1024)} GB`;
  return `${(n / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
}
