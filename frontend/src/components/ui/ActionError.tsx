"use client";

import { ApiError } from "@/lib/api";

export type ActionErrorDetails = {
  title: string;
  message: string;
  detail?: string;
  nextStep?: string;
};

export function actionErrorFromUnknown(
  err: unknown,
  fallbackTitle = "Action failed",
): ActionErrorDetails {
  if (err instanceof ApiError) {
    if (err.status === 401) {
      return {
        title: "Session expired",
        message: "Your session expired. Please log in again.",
        nextStep: "Return to the login page and sign in.",
      };
    }
    if (err.isNetworkError) {
      return {
        title: fallbackTitle,
        message: "Could not reach the server.",
        detail: err.path ? `${err.method} ${err.path}` : undefined,
        nextStep: "Check your connection and API URL, then try again.",
      };
    }
    const detail = err.path && err.status ? `${err.method} ${err.path} returned ${err.status}.` : undefined;
    let nextStep = "Try refreshing. If it continues, check backend logs.";
    if (err.status === 422) nextStep = "Check your input and try again.";
    if (err.status === 409) nextStep = "Wait for the current action to finish, then retry.";
    return {
      title: fallbackTitle,
      message: err.message || "Something went wrong.",
      detail,
      nextStep,
    };
  }
  if (err instanceof Error) {
    return {
      title: fallbackTitle,
      message: err.message,
      nextStep: "Try again in a moment.",
    };
  }
  return {
    title: fallbackTitle,
    message: "Something went wrong.",
    nextStep: "Try refreshing the page.",
  };
}

export default function ActionError({
  title,
  message,
  detail,
  nextStep,
}: ActionErrorDetails) {
  return (
    <div className="nc-error-panel" role="alert">
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm text-foreground">{message}</p>
      {detail ? (
        <p className="mt-2 text-xs text-muted">
          <span className="font-medium text-foreground">Details: </span>
          {detail}
        </p>
      ) : null}
      {nextStep ? (
        <p className="mt-2 text-xs text-muted">
          <span className="font-medium text-foreground">Next step: </span>
          {nextStep}
        </p>
      ) : null}
    </div>
  );
}
