import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { errorMessage } from "@/api/client";
import { DelayedSkeleton } from "./Skeleton";
import { EmptyState, ErrorState } from "./States";

type Props<T> = {
  query: UseQueryResult<T>;
  skeleton: ReactNode;
  isEmpty?: (data: T) => boolean;
  empty?: { title: string; body?: string; action?: ReactNode };
  children: (data: T) => ReactNode;
};

export function QueryView<T>({ query, skeleton, isEmpty, empty, children }: Props<T>) {
  if (query.isPending) return <DelayedSkeleton>{skeleton}</DelayedSkeleton>;
  if (query.isError)
    return (
      <ErrorState
        message={errorMessage(query.error)}
        onRetry={() => void query.refetch()}
        retrying={query.isFetching}
      />
    );
  if (isEmpty?.(query.data) && empty) return <EmptyState {...empty} />;
  return <>{children(query.data)}</>;
}
