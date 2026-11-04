/** Cartoon portrait of a character, matching how they are drawn on the island map. */
const INK = "#1d2142";
const SKIN = "#ffd8b1";

export function ToonAvatar({ id, color, size = 56 }: { id: string; color: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="-26 -30 52 52" role="img" aria-label={`${id} portrait`}
      className="shrink-0 rounded-full border-[3px] border-ink bg-[#bfe7ff]">
      {/* shoulders / shirt */}
      <path d="M-18 22 Q-18 8 0 8 Q18 8 18 22 Z" fill={color} stroke={INK} strokeWidth="2.5" />
      {id === "meera" && <circle cx="0" cy="-4" r="17" fill="#2f9e44" stroke={INK} strokeWidth="2.5" />}
      {id === "aria" && <circle cx="14" cy="-14" r="6.5" fill="#7f4f24" stroke={INK} strokeWidth="2.2" />}
      <circle cx="0" cy="-4" r="13" fill={SKIN} stroke={INK} strokeWidth="2.5" />
      {id === "aria" && (
        <>
          <path d="M-13 -6 A13 13 0 0 1 13 -6 Z" fill="#7f4f24" />
          <rect x="-13" y="-10" width="26" height="4" fill="#ff922b" stroke={INK} strokeWidth="1.8" />
        </>
      )}
      {id === "kabir" && (
        <>
          <path d="M-14 -8 A14 14 0 0 1 14 -8 Z" fill="#ffd43b" stroke={INK} strokeWidth="2.5" />
          <rect x="-17" y="-10" width="34" height="5" rx="2.5" fill="#ffd43b" stroke={INK} strokeWidth="2" />
        </>
      )}
      {id === "meera" && <path d="M-13 -6 A13 13 0 0 1 13 -6 Z" fill="#2f9e44" />}
      {/* face */}
      <ellipse cx="-4.5" cy="-2" rx="2.6" ry="3.4" fill={INK} />
      <ellipse cx="4.5" cy="-2" rx="2.6" ry="3.4" fill={INK} />
      <circle cx="-3.6" cy="-3.2" r="1" fill="#fff" />
      <circle cx="5.4" cy="-3.2" r="1" fill="#fff" />
      <circle cx="-8" cy="3" r="2.4" fill="#ff8fab" opacity="0.6" />
      <circle cx="8" cy="3" r="2.4" fill="#ff8fab" opacity="0.6" />
      <path d="M-3.4 3.5 Q0 7 3.4 3.5" fill="none" stroke={INK} strokeWidth="2" strokeLinecap="round" />
      {id === "kabir" && (
        <g fill="none" stroke={INK} strokeWidth="1.6">
          <circle cx="-4.5" cy="-2" r="4.4" />
          <circle cx="4.5" cy="-2" r="4.4" />
        </g>
      )}
    </svg>
  );
}
