"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

export type GuideProgress = {
  stage: string | null;
  /** While a recording or scan is being read: e.g. "Biology lecture: Transcribed 12:00 of 48:00". */
  detail: string | null;
  topics: { id: string; title: string }[];
  readySections: string[];
  reviewedSections: string[];
  failed: { code?: string; message?: string } | null;
  completed: boolean;
};

const EMPTY: GuideProgress = {
  stage: null,
  detail: null,
  topics: [],
  readySections: [],
  reviewedSections: [],
  failed: null,
  completed: false,
};

/**
 * Follows a guide's progress stream (SSE). Every event is replayed from the start, so a page
 * opened halfway through still shows the topics found so far. `onChange` fires when a section
 * lands or the run ends, so the caller can refetch the (partial) guide.
 */
export function useGuideEvents(guideId: string, enabled: boolean, onChange: () => void): GuideProgress {
  const [progress, setProgress] = useState<GuideProgress>(EMPTY);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!enabled) return;
    const source = new EventSource(api.eventsUrl(guideId), { withCredentials: true });
    const parse = (e: Event) => {
      try {
        return JSON.parse((e as MessageEvent).data);
      } catch {
        return {};
      }
    };
    source.addEventListener("stage", (e) => {
      const data = parse(e);
      if (data.stage && data.stage !== "regenerate_section")
        setProgress((p) => ({ ...p, stage: data.stage, detail: data.detail ?? null }));
    });
    source.addEventListener("topics_detected", (e) => {
      const data = parse(e);
      setProgress((p) => ({ ...p, topics: data.concepts ?? [] }));
      onChangeRef.current();
    });
    source.addEventListener("section_ready", (e) => {
      const data = parse(e);
      setProgress((p) =>
        p.readySections.includes(data.section_id)
          ? p
          : { ...p, readySections: [...p.readySections, data.section_id] },
      );
      onChangeRef.current();
    });
    source.addEventListener("section_reviewed", (e) => {
      const data = parse(e);
      setProgress((p) =>
        p.reviewedSections.includes(data.section_id)
          ? p
          : { ...p, reviewedSections: [...p.reviewedSections, data.section_id] },
      );
    });
    source.addEventListener("completed", () => {
      // A completed event from an earlier run can be replayed; the guide status decides what is shown.
      setProgress((p) => ({ ...p, completed: true, failed: null }));
      source.close();
      onChangeRef.current();
    });
    source.addEventListener("failed", (e) => {
      const data = parse(e);
      setProgress((p) => ({ ...p, failed: { code: data.code, message: data.message } }));
      source.close();
      onChangeRef.current();
    });
    return () => source.close();
  }, [guideId, enabled]);

  return progress;
}

/**
 * Follows one section rewrite (a regenerate job) on the guide's event stream. The stream may
 * close after replaying the guide's old "completed" event; EventSource then reconnects with
 * Last-Event-ID and only new events arrive.
 */
export function useJobEvents(
  guideId: string,
  jobId: string | null,
  handlers: { onDone: () => void; onFailed: (message: string) => void },
) {
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!jobId) return;
    const source = new EventSource(api.eventsUrl(guideId), { withCredentials: true });
    const data = (e: Event) => {
      try {
        return JSON.parse((e as MessageEvent).data);
      } catch {
        return {};
      }
    };
    source.addEventListener("section_ready", (e) => {
      if (data(e).job_id !== jobId) return;
      source.close();
      handlersRef.current.onDone();
    });
    source.addEventListener("failed", (e) => {
      const d = data(e);
      if (d.job_id !== jobId) return;
      source.close();
      handlersRef.current.onFailed(d.message ?? "The section could not be rewritten.");
    });
    return () => source.close();
  }, [guideId, jobId]);
}
