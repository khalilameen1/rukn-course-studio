"use client";

import Link from "next/link";
import type { Course } from "@/lib/types";

export default function CourseTable({ courses }: { courses: Course[] }) {
  if (courses.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No courses yet. Create the first one.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-black/10 text-zinc-500 dark:border-white/10">
            <th className="py-2 pr-4">Title</th>
            <th className="py-2 pr-4">Audience</th>
            <th className="py-2 pr-4">Structure</th>
            <th className="py-2 pr-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {courses.map((course) => (
            <tr key={course.id} className="border-b border-black/5 dark:border-white/5">
              <td className="py-2 pr-4">
                <Link href={`/courses/${course.id}`} className="font-medium hover:underline">
                  {course.title}
                </Link>
              </td>
              <td className="py-2 pr-4">{course.audience}</td>
              <td className="py-2 pr-4">{course.structure_mode}</td>
              <td className="py-2 pr-4">
                <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs dark:bg-white/10">
                  {course.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
