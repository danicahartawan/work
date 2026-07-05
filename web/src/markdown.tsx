import type { ReactNode } from "react";

/** Minimal Markdown renderer for AI notes: headings, lists, bold/italic/code. */
export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: ReactNode[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={`ul-${blocks.length}`}>{list}</ul>);
      list = [];
    }
  };
  text.split("\n").forEach((line, i) => {
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const li = line.match(/^\s*[-*]\s+(.*)/);
    if (li) {
      list.push(<li key={i}>{inline(li[1])}</li>);
      return;
    }
    flush();
    if (h) {
      const Tag = `h${h[1].length + 1}` as "h2";
      blocks.push(<Tag key={i}>{inline(h[2])}</Tag>);
    } else if (line.trim()) {
      blocks.push(<p key={i}>{inline(line)}</p>);
    }
  });
  flush();
  return <div className="markdown">{blocks}</div>;
}

function inline(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g)
    .filter(Boolean)
    .map((part, i) => {
      if (part.startsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
      if (part.startsWith("*")) return <em key={i}>{part.slice(1, -1)}</em>;
      return part;
    });
}
