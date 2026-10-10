import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

export function RouteError() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 px-4">
      <h1 className="text-2xl font-bold">
        {notFound ? "That page doesn't exist" : "This page failed to load"}
      </h1>
      <p className="text-ink-soft">
        {notFound
          ? "Check the address, or head back to your day."
          : "Reload the page. If it keeps happening, the server may be restarting."}
      </p>
      <div className="flex gap-3">
        <Link
          to="/pulse"
          className="inline-flex min-h-11 items-center rounded-md bg-pine px-4 font-bold text-on-pine"
        >
          Go to the start page
        </Link>
        {!notFound && (
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="min-h-11 rounded-md border border-line px-4 font-bold"
          >
            Reload
          </button>
        )}
      </div>
    </main>
  );
}
