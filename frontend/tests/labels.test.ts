import { describe, expect, it } from "vitest";

import { formatClock, refLabel } from "@/lib/labels";
import { limitFor } from "@/components/UploadDropzone";

describe("refLabel", () => {
  it("shows the page for PDF citations", () => expect(refLabel("p12-s3")).toBe("p. 12"));
  it("shows the part for Word, text and pasted citations", () => expect(refLabel("s7")).toBe("part 7"));
  it("names the source when a guide uses several", () => expect(refLabel("d2-p3-s1")).toBe("Source 2, p. 3"));
  it("leaves unknown shapes alone", () => expect(refLabel("x9")).toBe("x9"));
  it("shows the time for recordings", () => {
    expect(refLabel("t14m32s")).toBe("14:32");
    expect(refLabel("t0m05s-2")).toBe("0:05");
    expect(refLabel("v1h02m05s")).toBe("1:02:05 on screen");
    expect(refLabel("d2-t3m00s")).toBe("Source 2, 3:00");
  });
});

describe("formatClock", () => {
  it("formats minutes and hours", () => {
    expect(formatClock(872.9)).toBe("14:32");
    expect(formatClock(3725)).toBe("1:02:05");
    expect(formatClock(5)).toBe("0:05");
  });
});

describe("limitFor", () => {
  it("allows large recordings but keeps documents small", () => {
    expect(limitFor("Lecture.MP4")).toBe(1024 * 1024 * 1024);
    expect(limitFor("notes.pdf")).toBe(20 * 1024 * 1024);
    expect(limitFor("photo.jpeg")).toBe(20 * 1024 * 1024);
    expect(limitFor("slides.pptx")).toBeNull();
  });
});
