import { Link } from "react-router-dom";

type Crumb = { label: string; to?: string };

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-sm">
      <ol className="flex flex-wrap items-center gap-1 text-ink-soft">
        {items.map((item, i) => (
          <li key={`${item.label}-${i}`} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">›</span>}
            {item.to ? (
              <Link
                to={item.to}
                className="inline-flex min-h-11 items-center rounded-sm underline-offset-2 hover:underline md:min-h-0"
              >
                {item.label}
              </Link>
            ) : (
              <span aria-current="page" className="font-bold text-ink">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
