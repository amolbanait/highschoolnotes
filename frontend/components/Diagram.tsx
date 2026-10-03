"use client";

import { useEffect, useId, useState } from "react";

import type { Diagram as DiagramData } from "@/lib/types";

/**
 * Renders a Mermaid diagram in the browser. Mermaid runs with securityLevel "strict", which
 * sanitizes labels and disables click handlers. If the diagram does not parse, the student
 * sees the caption and a short note instead of a broken picture.
 */
export function Diagram({ diagram }: { diagram: DiagramData }) {
  const id = "d" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
          fontFamily: "inherit",
        });
        const { svg } = await mermaid.render(id, diagram.mermaid);
        if (!cancelled) setSvg(svg);
      } catch {
        if (!cancelled) setFailed(true);
        document.getElementById("d" + id)?.remove(); // mermaid leaves an error node behind
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, diagram.mermaid]);

  return (
    <figure className="my-4 rounded-xl border border-slate-200 bg-white p-4">
      {svg ? (
        <div
          className="flex justify-center overflow-x-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : failed ? (
        <p className="text-sm text-slate-500">This diagram could not be drawn.</p>
      ) : (
        <div className="h-32 animate-pulse rounded bg-slate-100" aria-label="Drawing diagram" />
      )}
      {diagram.caption && (
        <figcaption className="mt-3 text-center text-sm text-slate-600">{diagram.caption}</figcaption>
      )}
    </figure>
  );
}
