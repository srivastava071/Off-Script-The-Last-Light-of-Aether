import { createContext, useContext, type ButtonHTMLAttributes, type ReactNode } from "react";

/** Inside a container that already draws the card (e.g. the side tabs), panels drop their own frame. */
export const PlainPanels = createContext(false);

export function Panel({ title, icon, children, className = "", actions }: {
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  const plain = useContext(PlainPanels);
  return (
    <section className={`${plain ? "border-t-2 border-ink/10 pt-4 first:border-t-0 first:pt-0" : "panel p-4"} ${className}`}>
      {title && (
        <header className="mb-3 flex items-center justify-between gap-2">
          <h2 className="panel-title flex items-center gap-2 text-sm uppercase">
            {icon}
            {title}
          </h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

type Variant = "primary" | "ghost" | "danger" | "subtle";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-[#ffd43b] text-ink font-bold border-[2.5px] border-ink shadow-[0_3px_0_#1d2142] hover:bg-[#ffe066]",
  ghost: "bg-white text-ink font-semibold border-[2.5px] border-ink shadow-[0_3px_0_#1d2142] hover:bg-panel-2",
  danger: "bg-white text-danger font-semibold border-[2.5px] border-danger shadow-[0_3px_0_#e03131] hover:bg-danger/10",
  subtle: "bg-[#e7f5ff] text-ink font-semibold border-2 border-ink/70 hover:bg-[#d0ebff]",
};

export function Button({ variant = "ghost", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
}) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm transition
        active:translate-y-0.5 active:shadow-none disabled:cursor-not-allowed disabled:opacity-45
        disabled:active:translate-y-0 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Badge({ children, tone = "muted", title }: {
  children: ReactNode;
  tone?: "muted" | "amber" | "teal" | "danger" | "ok" | "sky";
  title?: string;
}) {
  const tones = {
    muted: "border-line bg-white text-muted",
    amber: "border-amber bg-[#fff4e6] text-amber",
    teal: "border-teal bg-[#e3fafc] text-teal",
    danger: "border-danger bg-[#fff5f5] text-danger",
    ok: "border-ok bg-[#ebfbee] text-ok",
    sky: "border-sky bg-[#e7f5ff] text-sky",
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full border-2 px-2 py-0.5 text-xs font-bold ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function ProgressBar({ value, tone = "amber", label }: { value: number; tone?: "amber" | "teal" | "danger"; label?: string }) {
  const colors = { amber: "bg-[#ffd43b]", teal: "bg-[#38d9a9]", danger: "bg-danger" };
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="h-3 w-full overflow-hidden rounded-full border-2 border-ink bg-white" role="progressbar" aria-valuenow={pct}
      aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className={`h-full ${colors[tone]} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}
