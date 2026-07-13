"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Course } from "@/lib/types";
import CourseTable from "@/components/courses/CourseTable";

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listCourses()
      .then(setCourses)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load courses"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Courses</h1>
        <Link
          href="/courses/new"
          className="rounded-full bg-foreground px-4 py-2 text-sm text-background"
        >
          New Course
        </Link>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-zinc-500">Loading...</p>
      ) : (
        <CourseTable courses={courses} />
      )}
    </div>
  );
}
