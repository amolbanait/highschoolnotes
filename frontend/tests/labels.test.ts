import { describe, expect, it } from "vitest";

import { refLabel } from "@/lib/labels";

describe("refLabel", () => {
  it("shows the page for PDF citations", () => expect(refLabel("p12-s3")).toBe("p. 12"));
  it("shows the part for Word, text and pasted citations", () => expect(refLabel("s7")).toBe("part 7"));
  it("names the source when a guide uses several", () => expect(refLabel("d2-p3-s1")).toBe("Source 2, p. 3"));
  it("leaves unknown shapes alone", () => expect(refLabel("x9")).toBe("x9"));
});
