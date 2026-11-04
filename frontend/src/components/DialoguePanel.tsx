import { MessageCircle, Send } from "lucide-react";
import { useState } from "react";

import type { CharacterView, WorldEvent } from "../types/api";
import { authorship } from "./eventStyle";
import { Button, Panel } from "./ui";

export function DialoguePanel({ me, others, events, pending, busy, onSend }: {
  me: CharacterView;
  others: CharacterView[]; // characters at the same location
  events: WorldEvent[];
  pending: boolean;
  busy: boolean;
  onSend: (targetId: string, message: string) => void;
}) {
  const [target, setTarget] = useState<string>("");
  const [text, setText] = useState("");
  const chosen = others.find((o) => o.id === target) ?? others[0];

  const conversation = events
    .filter((e) => (e.kind === "talked" || e.kind === "asked") && chosen &&
      ((e.actor === me.id && e.data.target === chosen.id) || (e.actor === chosen.id && e.data.target === me.id)))
    .slice(-6);

  return (
    <Panel title="Talk" icon={<MessageCircle size={16} />}>
      {others.length === 0 ? (
        <p className="text-sm text-muted">Nobody is here with you. Travel to a teammate to talk in person.</p>
      ) : (
        <form
          className="space-y-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (chosen && text.trim()) {
              onSend(chosen.id, text.trim());
              setText("");
            }
          }}
        >
          <div className="flex gap-1.5">
            {others.map((o) => (
              <button key={o.id} type="button" onClick={() => setTarget(o.id)}
                className={`rounded-full border px-2.5 py-0.5 text-xs ${chosen?.id === o.id ? "border-amber text-amber" : "border-line text-muted"}`}>
                {o.name}
              </button>
            ))}
          </div>
          <ul className="scroll-thin max-h-40 space-y-1 overflow-y-auto text-sm">
            {conversation.map((e) => (
              <li key={e.seq} className={e.actor === me.id ? "text-muted" : ""}>
                {e.kind === "asked" ? e.description : <><b>{e.actor === me.id ? "You" : chosen?.name}:</b> {String(e.data.message ?? "")}</>}
                {authorship(e) && <span className="ml-1 text-xs text-muted">({authorship(e)})</span>}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="say">Message</label>
            <input id="say" value={text} maxLength={280} onChange={(e) => setText(e.target.value)}
              placeholder={chosen ? `Say something to ${chosen.name}…` : ""}
              className="min-w-0 flex-1 rounded-xl border-[2.5px] border-ink bg-white px-3 py-2 text-sm placeholder:text-muted/80" />
            <Button type="submit" variant="primary" disabled={pending || busy || !text.trim()} aria-label="Send">
              <Send size={14} />
            </Button>
          </div>
          {busy && <p className="text-xs text-muted">You can talk once your current action is done.</p>}
        </form>
      )}
    </Panel>
  );
}
