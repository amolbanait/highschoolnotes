import type {
  FlashcardRating,
  Guide,
  GuideList,
  GuideRef,
  Level,
  QuizResult,
  Source,
  User,
} from "@/lib/types";

/** An API failure, carrying the backend's {"error": {code, message, details}} body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

const BASE = "/api/v1";

async function request<T>(method: string, path: string, body?: BodyInit | object): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (method !== "GET") headers["X-Requested-With"] = "fetch"; // the API's CSRF guard
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection and try again.");
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // A proxy error page or similar; handled as a generic failure below.
  }
  if (!res.ok) {
    const err = data?.error;
    if (err?.code === "unauthorized" && typeof window !== "undefined")
      window.dispatchEvent(new Event("hsn:signed-out"));
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? `Something went wrong (${res.status}). Try again.`,
      err?.details ?? {},
    );
  }
  return data as T;
}

export const api = {
  signup: (body: { email: string; password: string; display_name: string; confirms_age_13_plus: boolean }) =>
    request<User>("POST", "/auth/signup", body),
  login: (body: { email: string; password: string }) => request<User>("POST", "/auth/login", body),
  logout: () => request<void>("POST", "/auth/logout"),
  me: () => request<User>("GET", "/me"),
  updateMe: (body: { display_name?: string; default_level?: Level }) => request<User>("PATCH", "/me", body),
  deleteMe: () => request<void>("DELETE", "/me"),

  listSources: () => request<Source[]>("GET", "/sources"),
  uploadSource: (file: File, title?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    return request<Source>("POST", "/sources", form);
  },
  pasteSource: (title: string, text: string) =>
    request<Source>("POST", "/sources", { kind: "paste", title, text }),
  deleteSource: (id: string) => request<void>("DELETE", `/sources/${id}`),
  sourceFileUrl: (id: string) => `${BASE}/sources/${id}/file`,

  createGuide: (sourceIds: string[], level?: Level) =>
    request<{ guide_id: string; job_id: string }>("POST", "/guides", { source_ids: sourceIds, level }),
  listGuides: (cursor?: string) =>
    request<GuideList>("GET", `/guides${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
  getGuide: (id: string) => request<Guide>("GET", `/guides/${id}`),
  deleteGuide: (id: string) => request<void>("DELETE", `/guides/${id}`),
  resolveRef: (guideId: string, ref: string) =>
    request<GuideRef>("GET", `/guides/${guideId}/refs/${encodeURIComponent(ref)}`),
  regenerateSection: (guideId: string, sectionId: string, instruction?: string) =>
    request<{ job_id: string }>("POST", `/guides/${guideId}/sections/${sectionId}/regenerate`, {
      instruction,
    }),
  eventsUrl: (guideId: string) => `${BASE}/guides/${guideId}/events`,

  answerQuestion: (guideId: string, questionId: string, answer: string) =>
    request<QuizResult>("POST", `/guides/${guideId}/quiz-attempts`, { question_id: questionId, answer }),
  reviewFlashcard: (guideId: string, cardId: string, rating: FlashcardRating) =>
    request<void>("POST", `/guides/${guideId}/flashcard-reviews`, { card_id: cardId, rating }),
};
