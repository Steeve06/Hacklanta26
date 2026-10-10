import { createBrowserRouter, Navigate } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { AppShell } from "./AppShell";
import { RequireAuth } from "./RequireAuth";
import { RouteError } from "./RouteError";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage />, errorElement: <RouteError /> },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      {
        element: <AppShell />,
        children: [{ index: true, element: <Navigate to="/pulse" replace /> }],
      },
    ],
  },
]);
