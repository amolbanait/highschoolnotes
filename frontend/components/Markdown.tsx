import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

/**
 * Model-written prose: Markdown with $…$ maths. Raw HTML is never rendered, so text from the
 * source material or the model cannot inject markup.
 */
export function Markdown({ children, inline = false }: { children: string; inline?: boolean }) {
  return (
    <div className={inline ? "prose-inline" : "prose-guide"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: "ignore" }]]}
        components={inline ? { p: ({ children }) => <>{children}</> } : undefined}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
