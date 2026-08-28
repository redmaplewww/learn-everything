"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ content }: { content: string }) {
  return (
    <article className="lesson-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children, ...props }) => (
            <a {...props} href={href} target="_blank" rel="noreferrer">{children}</a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  );
}
