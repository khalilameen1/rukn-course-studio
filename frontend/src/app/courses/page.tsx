"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Course } from "@/lib/types";
import CourseTable from "@/components/courses/CourseTable";
import PageHeader from "@/components/ui/PageHeader";

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
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Courses"
        description="Create a course brief, upload sources, and generate the final teleprompter-ready DOCX."
        action={
          <Link
            href="/courses/new"
            className="btn-primary"
          >
            New Course
          </Link>
        }
      />

      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {loading ? <p className="text-sm text-muted">Loading...</p> : <CourseTable courses={courses} />}
    </div>
  );
}
