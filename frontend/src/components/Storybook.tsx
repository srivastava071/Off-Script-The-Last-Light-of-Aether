import { BookOpen, Wand2 } from "lucide-react";
import { useEffect, useRef } from "react";

import type { Chapter } from "../types/api";
import { Panel } from "./ui";

/** Who wrote a page, stated plainly so template prose is never passed off as AI writing. */
export const pageAuthor = (c: Chapter) => (c.generated_by === "template" ? "template" : `AI narrator · ${c.generated_by}`);

function Page({ c }: { c: Chapter }) {
  const twist = c.kind === "twist";
  return (
    <article className={`rounded-xl border-2 p-3 ${twist ? "border-[#b197fc] bg-[#f3f0ff]" : "border-ink/20 bg-[#fffbeb]"}`}>
      <header className="flex items-baseline gap-2">
        <span className="font-display text-xs text-muted">Page {c.id}</span>
        <h3 className={`flex items-center gap-1 font-display text-sm ${twist ? "text-[#7048e8]" : "text-ink"}`}>
          {twist && <Wand2 size={13} aria-hidden />} {c.title}
        </h3>
      </header>
      <p className="mt-1 text-sm leading-relaxed text-ink">{c.text}</p>
      <p className="mt-1 text-right text-[10px] uppercase tracking-wide text-muted">{pageAuthor(c)}</p>
    </article>
  );
}

/** The live storybook: one page per story beat and per twist, newest at the bottom. */
export function Storybook({ chapters, className = "" }: { chapters: Chapter[]; className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const count = chapters.length;
  useEffect(() => {
    // Scroll only inside the panel, never the page.
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [count]);
  return (
    <Panel title="Storybook" icon={<BookOpen size={16} />} className={`flex flex-col ${className}`}>
      <div ref={box} className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {count === 0 && <p className="text-sm text-muted">The story is about to begin…</p>}
        {chapters.map((c) => <Page key={c.id} c={c} />)}
      </div>
    </Panel>
  );
}

/** The whole storybook, for the ending screen. */
export function StorybookPages({ chapters }: { chapters: Chapter[] }) {
  return <div className="space-y-2">{chapters.map((c) => <Page key={c.id} c={c} />)}</div>;
}
