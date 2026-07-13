import type { NextConfig } from "next";

// NEXT_PUBLIC_* values are inlined into the client bundle at build time and
// silently fall back to "http://localhost:8000" if unset (see
// src/lib/config.ts) - which only fails once deployed, as every request
// from real users' browsers to localhost:8000. Fail the production build
// loudly instead, so a missing/misnamed env var on Render is caught here,
// not by a user seeing a broken login page.
if (
  process.env.NODE_ENV === "production" &&
  !process.env.NEXT_PUBLIC_API_BASE_URL &&
  !process.env.NEXT_PUBLIC_API_URL
) {
  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL is not set. Set it (in the Render Dashboard " +
      "for the frontend service, or frontend/.env.local for a local " +
      "production build) to the backend's full URL, e.g. " +
      "https://rukn-course-studio-backend.onrender.com - then rebuild.",
  );
}

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
