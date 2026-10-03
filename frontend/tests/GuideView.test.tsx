import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { GuideView } from "@/components/GuideView";
import { SourceProvider } from "@/components/SourcePanel";

import { guide } from "./fixtures";

function renderGuide(content = guide) {
  return render(
    <SourceProvider guideId="g1">
      <GuideView content={content} />
    </SourceProvider>,
  );
}

describe("GuideView", () => {
  it("renders the guide in teaching order", () => {
    renderGuide();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual([
      "What is this topic about?",
      "Key vocabulary",
      "Inputs and outputs",
      "Light reactions",
      "Key facts to remember",
      "How the ideas connect",
      "Summary",
      "Review checklist",
    ]);
  });

  it("labels AI-written examples and analogies apart from the student's material", () => {
    renderGuide();
    expect(screen.getByText("✦ AI-written example")).toBeInTheDocument();
    expect(screen.getByText("From your material")).toBeInTheDocument();
    expect(screen.getByText(/AI-written to help explain/)).toBeInTheDocument();
  });

  it("flags quotes that could not be matched to the source", () => {
    renderGuide();
    expect(screen.getByText(/couldn't be matched word for word/)).toBeInTheDocument();
  });

  it("shows prerequisites and relationships by concept title", () => {
    renderGuide();
    expect(screen.getByText("Builds on: Inputs and outputs")).toBeInTheDocument();
    expect(screen.getByText(/→ enables →/).parentElement).toHaveTextContent(
      "Inputs and outputs → enables → Light reactions",
    );
  });

  it("switches between the three explanation levels", async () => {
    renderGuide();
    expect(screen.getByText("Light energy splits water.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Explain like I'm new/ }));
    expect(screen.getByText("Light breaks water apart.")).toBeInTheDocument();
  });

  it("hides quick-check answers until asked", async () => {
    renderGuide();
    expect(screen.queryByText("Carbon dioxide.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
    expect(screen.getByText("Carbon dioxide.")).toBeInTheDocument();
  });

  it("renders partial content while the guide is still being made", () => {
    renderGuide({ title: "Study guide", level: "high_school", concepts: [guide.concepts![0]] });
    expect(screen.getByRole("heading", { name: "Inputs and outputs" })).toBeInTheDocument();
    expect(screen.queryByText("Summary")).not.toBeInTheDocument();
  });

  it("never renders raw HTML from model text", () => {
    const { container } = renderGuide({
      title: "x",
      level: "high_school",
      overview: 'Hi <img src=x onerror="alert(1)"> there',
    });
    expect(container.querySelector("img")).toBeNull();
  });
});
