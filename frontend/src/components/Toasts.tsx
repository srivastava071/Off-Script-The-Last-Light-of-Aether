import { useEffect, useRef, useState } from "react";

import type { WorldEvent } from "../types/api";
import { eventStyle, isAdaptation, isHeadline } from "./eventStyle";

interface Toast {
  id: number;
  event: WorldEvent;
}

const TONE_BADGE: Record<string, string> = {
  muted: "bg-[#f1f3f5] text-muted", amber: "bg-[#fff4e6] text-amber", teal: "bg-[#e3fafc] text-teal",
  danger: "bg-[#fff5f5] text-danger", ok: "bg-[#ebfbee] text-ok", sky: "bg-[#e7f5ff] text-sky",
};

/** Brief notifications for headline events, taken straight from the backend event log. */
export function Toasts({ events }: { events: WorldEvent[] }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seen = useRef(0);

  useEffect(() => {
    const fresh = events.filter((e) => e.seq > seen.current);
    if (fresh.length === 0) return;
    const replaying = seen.current === 0;
    seen.current = fresh[fresh.length - 1].seq;
    if (replaying) return;
    const add = fresh.filter(isHeadline).slice(-3).map((event) => ({ id: event.seq, event }));
    if (add.length === 0) return;
    setToasts((t) => [...t, ...add].slice(-3));
    const ids = add.map((a) => a.id);
    setTimeout(() => setToasts((t) => t.filter((x) => !ids.includes(x.id))), 6000);
  }, [events]);

  return (
    <div className="pointer-events-none fixed inset-x-3 bottom-3 z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:bottom-5 sm:right-5 sm:w-80" aria-live="polite">
      {toasts.map(({ id, event }) => {
        const st = eventStyle(event);
        const Icon = st.icon;
        return (
          <div key={id} className="panel animate-rise flex w-full items-start gap-2.5 p-2.5 text-sm">
            <span className={`grid size-7 shrink-0 place-items-center rounded-full border-2 border-ink ${TONE_BADGE[st.tone]}`}>
              <Icon size={14} aria-hidden />
            </span>
            <span>
              {isAdaptation(event) && <b className="mr-1 text-amber">Adaptation:</b>}
              {event.description}
            </span>
          </div>
        );
      })}
    </div>
  );
}
