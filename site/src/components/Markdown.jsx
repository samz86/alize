import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Rendu Markdown des fiches et articles (contenus sourcés, édités dans Notion).
export default function Markdown({ source }) {
  const components = useMemo(
    () => ({
      a: ({ node, ...p }) => <a {...p} target="_blank" rel="noreferrer" />,
    }),
    []
  );
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
