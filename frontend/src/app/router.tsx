import type { ComponentType } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ONBOARDING } from "@/features/auth/redirects";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { OnboardingGate } from "@/features/onboarding/OnboardingGate";
import { OnboardingLayout } from "@/features/onboarding/OnboardingLayout";
import { AppShell } from "./AppShell";
import { HomeRedirect } from "./HomeRedirect";
import { PublicOnly } from "./PublicOnly";
import { RequireAuth } from "./RequireAuth";
import { RouteError } from "./RouteError";

function page<M extends Record<string, unknown>>(load: () => Promise<M>, name: keyof M) {
  return async () => ({ Component: (await load())[name] as ComponentType });
}

const lms = () => import("@/features/lms/pages");
const pulse = () => import("@/features/pulse/pages");
const notifications = () => import("@/features/notifications/InboxPage");
const quiz = () => import("@/features/quiz/pages");
const demo = () => import("@/features/demo/DemoPage");
const onboarding = () => import("@/features/onboarding/OnboardingPage");
const teach = () => import("@/features/teach/pages");

export const router = createBrowserRouter([
  {
    element: <PublicOnly />,
    errorElement: <RouteError />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/signup", element: <SignupPage /> },
    ],
  },
  { path: "/forgot-password", element: <ForgotPasswordPage />, errorElement: <RouteError /> },
  { path: "/reset-password", element: <ResetPasswordPage />, errorElement: <RouteError /> },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      {
        path: ONBOARDING,
        element: <OnboardingGate />,
        children: [
          {
            element: <OnboardingLayout />,
            children: [{ index: true, lazy: page(onboarding, "OnboardingPage") }],
          },
        ],
      },
      {
        element: <AppShell />,
        errorElement: <RouteError />,
        children: [
          { index: true, element: <HomeRedirect /> },
          {
            path: "pulse",
            lazy: page(pulse, "PulseGate"),
            children: [
              { index: true, element: <Navigate to="today" replace /> },
              { path: "today", lazy: page(pulse, "TodayPage") },
              { path: "onboarding", element: <Navigate to={ONBOARDING} replace /> },
              { path: "week", lazy: page(pulse, "WeekPage") },
              { path: "overall", lazy: page(pulse, "OverallPage") },
              { path: "settings", element: <Navigate to="/settings" replace /> },
              { path: "inbox", lazy: page(notifications, "InboxPage") },
              { path: "checks", lazy: page(quiz, "QuizHubPage") },
              { path: "checks/:checkId", lazy: page(quiz, "CheckPage") },
              { path: "leaderboard", lazy: page(quiz, "LeaderboardPage") },
              { path: "quiz", lazy: page(quiz, "OldCheckLink") },
              { path: "quiz/:checkId", lazy: page(quiz, "OldCheckLink") },
            ],
          },
          { path: "settings", lazy: page(pulse, "SettingsPage") },
          { path: "teach", lazy: page(teach, "TeachPage") },
          { path: "teach/register", lazy: page(teach, "RegisterCoursePage") },
          { path: "lms", lazy: page(lms, "CourseListPage") },
          { path: "demo", lazy: page(demo, "DemoPage") },
          {
            path: "lms/courses/:courseId",
            lazy: page(lms, "CourseLayout"),
            children: [
              { index: true, lazy: page(lms, "ContentTab") },
              { path: "assignments", lazy: page(lms, "AssignmentsTab") },
              { path: "syllabus", lazy: page(lms, "SyllabusTab") },
            ],
          },
          { path: "lms/courses/:courseId/chapters/new", lazy: page(lms, "ChapterEditorPage") },
          { path: "lms/courses/:courseId/chapters/:chapterId", lazy: page(lms, "ChapterPage") },
          {
            path: "lms/courses/:courseId/chapters/:chapterId/edit",
            lazy: page(lms, "ChapterEditorPage"),
          },
          {
            path: "lms/courses/:courseId/assignments/new",
            lazy: page(lms, "AssessmentEditorPage"),
          },
          {
            path: "lms/courses/:courseId/assignments/:assessmentId",
            lazy: page(lms, "AssessmentPage"),
          },
          {
            path: "lms/courses/:courseId/assignments/:assessmentId/edit",
            lazy: page(lms, "AssessmentEditorPage"),
          },
          { path: "lms/courses/:courseId/attempts/:attemptId", lazy: page(lms, "AttemptPage") },
        ],
      },
    ],
  },
]);
