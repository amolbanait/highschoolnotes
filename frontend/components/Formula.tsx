import katex from "katex";

/** A display formula. KaTeX escapes its input; a formula it cannot parse is shown as plain text. */
export function Formula({ latex }: { latex: string }) {
  let html: string | null = null;
  try {
    html = katex.renderToString(latex, { displayMode: true, throwOnError: true, strict: "ignore" });
  } catch {
    html = null;
  }
  if (html === null) {
    return <code className="block overflow-x-auto rounded bg-slate-50 p-3 text-sm">{latex}</code>;
  }
  return <div className="overflow-x-auto py-1" dangerouslySetInnerHTML={{ __html: html }} />;
}
