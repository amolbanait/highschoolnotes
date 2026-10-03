import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Flashcards } from "@/components/Flashcards";
import { Quiz } from "@/components/Quiz";

import { guide } from "./fixtures";

function mockFetch(body: unknown, status = 200) {
  const fn = vi.fn(async () => new Response(body === undefined ? "" : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("Quiz", () => {
  it("grades multiple choice through the API and sends the CSRF header", async () => {
    const fetch = mockFetch({
      is_correct: true,
      correct_answer: "Chlorophyll",
      explanation: "Chlorophyll absorbs light.",
      source_refs: [],
    });
    render(<Quiz guideId="g1" questions={guide.questions!} />);
    await userEvent.click(screen.getByLabelText("Chlorophyll"));
    await userEvent.click(screen.getAllByRole("button", { name: "Check answer" })[0]);
    expect(await screen.findByText("Correct!")).toBeInTheDocument();
    expect(screen.getByText("1 of 1 right so far · 1 left")).toBeInTheDocument();
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/guides/g1/quiz-attempts");
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBeTruthy();
    expect(JSON.parse(init.body as string)).toEqual({ question_id: "q1", answer: "Chlorophyll" });
  });

  it("lets the student self-check open answers", async () => {
    mockFetch({
      is_correct: null,
      correct_answer: "No light energy.",
      explanation: "Light powers it.",
      source_refs: [],
    });
    render(<Quiz guideId="g1" questions={[guide.questions![1]]} />);
    await userEvent.type(screen.getByLabelText("Your answer"), "no sun");
    await userEvent.click(screen.getByRole("button", { name: "Check answer" }));
    expect(await screen.findByText("Compare with a good answer:")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(screen.getByText(/1 of 1 right so far/)).toBeInTheDocument();
  });

  it("shows the API's error message", async () => {
    mockFetch({ error: { code: "not_found", message: "That question does not exist.", details: {} } }, 404);
    render(<Quiz guideId="g1" questions={[guide.questions![0]]} />);
    await userEvent.click(screen.getByLabelText("Chlorophyll"));
    await userEvent.click(screen.getByRole("button", { name: "Check answer" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That question does not exist.");
  });
});

describe("Flashcards", () => {
  it("flips, records ratings and puts 'again' cards back at the end", async () => {
    const fetch = mockFetch(undefined, 201);
    render(<Flashcards guideId="g1" cards={guide.flashcards!} />);
    await userEvent.click(screen.getByRole("button", { name: "Show the answer" }));
    expect(screen.getByText("Green pigment")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Again" }));
    expect(screen.getByText("Glucose")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show the answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.getByText("Chlorophyll")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show the answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Easy" }));
    expect(screen.getByText("Deck done!")).toBeInTheDocument();
    const ratings = fetch.mock.calls.map((c) =>
      JSON.parse((c as unknown as [string, RequestInit])[1].body as string),
    );
    expect(ratings).toEqual([
      { card_id: "k1", rating: "again" },
      { card_id: "k2", rating: "good" },
      { card_id: "k1", rating: "easy" },
    ]);
  });
});
