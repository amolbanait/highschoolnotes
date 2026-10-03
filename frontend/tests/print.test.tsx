import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExportMenu } from "@/app/(app)/guides/[id]/GuideTabs";
import { PrintableGuide } from "@/app/(app)/guides/[id]/print/PrintableGuide";
import { GuideView } from "@/components/GuideView";
import { SourceProvider } from "@/components/SourcePanel";
import type { StudyGuideContent } from "@/lib/types";

import { guide } from "./fixtures";

vi.mock("next/navigation", () => ({ usePathname: () => "/guides/g1" }));

const flagged: StudyGuideContent = {
  ...guide,
  concepts: guide.concepts!.map((c) =>
    c.id === "c2"
      ? {
          ...c,
          quality: {
            score: 55,
            flags: ["needs_checking"],
            reviewed: true,
            rewritten: false,
            needs_checking: true,
            problems: ["It says light splits carbon dioxide; the source says water."],
          },
        }
      : c,
  ),
};

describe("quality flags", () => {
  it("tells the student to check a section the review could not confirm", () => {
    render(
      <SourceProvider guideId="g1">
        <GuideView content={flagged} />
      </SourceProvider>,
    );
    const article = screen.getByRole("heading", { name: "Light reactions" }).closest("article")!;
    const note = within(article).getByRole("note");
    expect(note).toHaveTextContent("Check this against your source");
    expect(note).toHaveTextContent("the source says water");
    const other = screen.getByRole("heading", { name: "Inputs and outputs" }).closest("article")!;
    expect(within(other).queryByRole("note")).toBeNull();
  });
});

describe("printable guide", () => {
  it("opens everything up: all three levels, quick-check answers, answer key and flashcards", () => {
    render(<PrintableGuide content={flagged} level="high_school" />);
    expect(screen.getByText("Light breaks water apart.")).toBeInTheDocument();
    expect(screen.getByText("Light energy splits water.")).toBeInTheDocument();
    expect(screen.getByText("Photosystem II.")).toBeInTheDocument();
    expect(screen.getByText("Carbon dioxide.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show answer" })).toBeNull();
    expect(screen.queryByRole("tab")).toBeNull();

    const key = screen.getByRole("heading", { name: "Answer key" }).nextElementSibling!;
    expect(key).toHaveTextContent("A. Chlorophyll");
    expect(key).toHaveTextContent("No light energy for photosynthesis.");
    expect(screen.getByRole("heading", { name: "Flashcards" })).toBeInTheDocument();
    expect(screen.getByText(/Check this against your source/)).toBeInTheDocument();
  });

  it("shows citations as text, since there is no source panel on paper", () => {
    render(<PrintableGuide content={guide} level="high_school" />);
    expect(screen.getAllByText("(Source: p. 1)").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "p. 1" })).toBeNull();
  });
});

describe("export menu", () => {
  it("links each download format and the printable view", () => {
    render(<ExportMenu guideId="g1" />);
    const links = screen.getAllByRole("link", { hidden: true });
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/api/v1/guides/g1/export?format=pdf",
      "/api/v1/guides/g1/export?format=docx",
      "/api/v1/guides/g1/export?format=md",
      "/api/v1/guides/g1/export?format=html",
      "/guides/g1/print",
    ]);
    expect(links[0]).toHaveAttribute("download");
  });
});
