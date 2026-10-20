import type { ReactNode, SVGProps } from "react";

type Props = SVGProps<SVGSVGElement> & { size?: number };
function icon(content: ReactNode) {
  return function Icon({ size = 18, strokeWidth = 2, ...props }: Props) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        {...props}
      >
        {content}
      </svg>
    );
  };
}
export const Layers3 = icon(
  <>
    <path d="m12 2 9 5-9 5-9-5 9-5Z" />
    <path d="m3 12 9 5 9-5M3 17l9 5 9-5" />
  </>,
);
export const ChevronDown = icon(<path d="m6 9 6 6 6-6" />);
export const CircleHelp = icon(
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M9.5 9a2.5 2.5 0 1 1 4.3 1.7c-1.1 1-1.8 1.3-1.8 3" />
    <path d="M12 17h.01" />
  </>,
);
export const BookOpen = icon(
  <>
    <path d="M12 7c-2-2-5-2-9-1v14c4-1 7-1 9 1 2-2 5-2 9-1V6c-4-1-7-1-9 1Z" />
    <path d="M12 7v14" />
  </>,
);
export const Menu = icon(
  <>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </>,
);
export const Plus = icon(<path d="M12 4v16M4 12h16" />);
export const GitBranch = icon(
  <>
    <circle cx="6" cy="4" r="2" />
    <circle cx="18" cy="6" r="2" />
    <circle cx="6" cy="20" r="2" />
    <path d="M6 6v12M18 8c0 6-12 2-12 8" />
  </>,
);
export const ArrowLeftRight = icon(
  <>
    <path d="M3 8h18m-4-4 4 4-4 4M21 16H3m4-4-4 4 4 4" />
  </>,
);
export const Play = icon(<path d="m8 5 11 7-11 7V5Z" />);
export const LockKeyhole = icon(
  <>
    <rect x="4" y="10" width="16" height="12" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3M12 15v3" />
  </>,
);
export const Split = icon(
  <>
    <path d="M12 3v18M4 7h5M4 12h5M15 7h5M15 12h5" />
  </>,
);
export const RotateCcw = icon(
  <>
    <path d="M3 11a9 9 0 1 0 3-6.7L3 7" />
    <path d="M3 3v4h4" />
  </>,
);
export const Download = icon(
  <>
    <path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4" />
  </>,
);
export const Activity = icon(<path d="M2 12h4l3-8 5 16 3-8h5" />);
export const Search = icon(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="m16 16 5 5" />
  </>,
);
export const X = icon(<path d="M5 5 19 19M19 5 5 19" />);
export const TriangleAlert = icon(
  <>
    <path d="M10.5 3a2 2 0 0 1 3 0L22 19a2 2 0 0 1-2 3H4a2 2 0 0 1-2-3L10.5 3Z" />
    <path d="M12 9v5m0 4h.01" />
  </>,
);
export const Command = icon(
  <>
    <path d="M9 7V5a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v14a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V7Z" />
  </>,
);
export const Save = icon(
  <>
    <path d="M4 3h14l3 3v15H3V3h1Z" />
    <path d="M7 3v6h10V3M7 21v-8h10v8" />
  </>,
);
export const CircleDot = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="3" />
  </>,
);
export const Eye = icon(
  <>
    <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </>,
);
export const Lightbulb = icon(
  <>
    <path d="M9 18h6m-5 3h4M8 14a7 7 0 1 1 8 0l-1 4H9l-1-4Z" />
  </>,
);
export const Pencil = icon(
  <>
    <path d="m4 20 4-.5L20 7l-3-3L4.5 16 4 20Z" />
    <path d="m14 7 3 3" />
  </>,
);
export const StickyNote = icon(
  <>
    <path d="M4 3h16v12l-6 6H4V3Z" />
    <path d="M14 21v-6h6" />
  </>,
);
export const UserRound = icon(
  <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </>,
);
