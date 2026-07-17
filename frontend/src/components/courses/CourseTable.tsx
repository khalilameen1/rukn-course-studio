"use client";



import Link from "next/link";

import type { CourseWithDisplayStatus } from "@/lib/courseDisplayStatus";

import {

  COURSE_DISPLAY_STATUS_LABEL,

  COURSE_DISPLAY_STATUS_TONE,

} from "@/lib/courseDisplayStatus";

import Card from "@/components/ui/Card";

import EmptyState from "@/components/ui/EmptyState";

import StatusBadge from "@/components/ui/StatusBadge";



const STRUCTURE_MODE_LABELS: Record<string, string> = {

  connected_no_modules: "Connected, no modules",

  connected_modules_with_bridge_projects: "Connected + bridge projects",

};



export default function CourseTable({ courses }: { courses: CourseWithDisplayStatus[] }) {

  if (courses.length === 0) {

    return (

      <EmptyState

        title="No courses yet"

        description="Create your first course brief to get started."

        action={

          <Link

            href="/courses/new"

            className="btn-primary"

          >

            New Course

          </Link>

        }

      />

    );

  }



  return (

    <Card padding="none" className="overflow-x-auto">

      <table className="w-full text-left text-sm">

        <thead>

          <tr className="border-b border-border bg-surface-muted/70 text-muted">

            <th className="px-4 py-3 font-medium">Title</th>

            <th className="px-4 py-3 font-medium">Audience</th>

            <th className="px-4 py-3 font-medium">Structure</th>

            <th className="px-4 py-3 font-medium">Status</th>

          </tr>

        </thead>

        <tbody>

          {courses.map((course) => (

            <tr key={course.id} className="border-b border-border last:border-0">

              <td className="px-4 py-3">

                <Link href={`/courses/${course.id}`} className="font-medium hover:underline">

                  {course.title}

                </Link>

              </td>

              <td className="px-4 py-3 text-muted">{course.audience}</td>

              <td className="px-4 py-3 text-muted">

                {STRUCTURE_MODE_LABELS[course.structure_mode] ?? course.structure_mode}

              </td>

              <td className="px-4 py-3">

                <StatusBadge

                  label={COURSE_DISPLAY_STATUS_LABEL[course.displayStatus]}

                  tone={COURSE_DISPLAY_STATUS_TONE[course.displayStatus]}

                />

              </td>

            </tr>

          ))}

        </tbody>

      </table>

    </Card>

  );

}

