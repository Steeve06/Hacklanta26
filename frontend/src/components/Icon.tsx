const paths = {
  today: "M5 5h14v14H5zM5 9h14M9 3v4M15 3v4M9 13h3v3H9z",
  week: "M4 6h16v13H4zM4 10h16M8 4v4M16 4v4M8 14h2M12 14h2M16 14h2",
  overall: "M4 18h16M6 15V9M10 15V6M14 15v-4M18 15V8",
  quiz: "M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z",
  courses: "M4 5h7a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM20 5h-7a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h7z",
  settings:
    "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v9H5z",
  check: "M5 12.5l4.5 4.5L19 7.5",
  flame:
    "M12 3c1 4 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-3.5 2-5 1 1.5 1.5 2 2.5 2C11.5 7.5 12 5.5 12 3z",
  chevron: "M9 6l6 6-6 6",
  back: "M15 6l-6 6 6 6",
  roster:
    "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2.5 19a5.5 5.5 0 0 1 11 0M16 11a3 3 0 1 0 0-6M17.5 19h4a5.5 5.5 0 0 0-4.5-5.4",
  upload: "M12 16V4M7 9l5-5 5 5M4 16v4h16v-4",
  signout: "M10 5H5v14h5M14 8l4 4-4 4M18 12H9",
  eye: "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  eyeOff:
    "M4 4l16 16M10.6 6.1A9.6 9.6 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.6 3.3M6.3 7.6C3.9 9.2 2.5 12 2.5 12S6 18 12 18c1.5 0 2.8-.4 4-1M9.9 10a2.5 2.5 0 0 0 3.6 3.5",
  external: "M14 4h6v6M20 4l-9 9M18 14v5H5V6h5",
  trophy:
    "M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v3M9 20h6M10 16h4v4h-4z",
  chat: "M4 5h16v11H10l-4 3.5V16H4z",
  close: "M6 6l12 12M18 6L6 18",
} as const;

export type IconName = keyof typeof paths;

export function Icon({
  name,
  className = "h-5 w-5",
  label,
}: {
  name: IconName;
  className?: string;
  label?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={paths[name]} />
    </svg>
  );
}
