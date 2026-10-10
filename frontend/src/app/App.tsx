import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { ToastRegion } from "@/components/ui";
import { queryClient } from "./queryClient";
import { router } from "./router";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ToastRegion />
    </QueryClientProvider>
  );
}
