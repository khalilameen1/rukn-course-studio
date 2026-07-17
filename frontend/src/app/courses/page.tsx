"use client";



import Link from "next/link";

import { useEffect, useState } from "react";

import { api, formatApiErrorForDisplay } from "@/lib/api";

import type { Course } from "@/lib/types";

import {

  deriveCourseDisplayStatus,

  type CourseWithDisplayStatus,

} from "@/lib/courseDisplayStatus";

import CourseTable from "@/components/courses/CourseTable";

import PageHeader from "@/components/ui/PageHeader";



async function enrichCoursesWithDisplayStatus(

  courses: Course[],

): Promise<CourseWithDisplayStatus[]> {

  return Promise.all(

    courses.map(async (course) => {

      let hasVersions = false;

      let latestJobStatus: string | null = null;

      try {

        const versions = await api.listVersions(course.id);

        hasVersions = versions.length > 0;

      } catch {

        // ignore

      }

      try {

        const job = await api.getLatestJob(course.id);

        latestJobStatus = job.status;

      } catch {

        // no run yet

      }

      return {

        ...course,

        displayStatus: deriveCourseDisplayStatus(hasVersions, latestJobStatus),

      };

    }),

  );

}



export default function CoursesPage() {

  const [courses, setCourses] = useState<CourseWithDisplayStatus[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);



  useEffect(() => {

    api

      .listCourses()

      .then(enrichCoursesWithDisplayStatus)

      .then(setCourses)

      .catch((err) => setError(formatApiErrorForDisplay(err)))

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

