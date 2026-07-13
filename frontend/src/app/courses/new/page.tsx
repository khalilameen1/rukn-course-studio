"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import CourseForm, { type CourseFormValues } from "@/components/courses/CourseForm";

export default function NewCoursePage() {
  const router = useRouter();

  async function handleSubmit(values: CourseFormValues) {
    const course = await api.createCourse({
      title: values.title,
      audience: values.audience,
      outcome: values.outcome,
      special_notes: values.special_notes || null,
      structure_mode: values.structure_mode,
      manual_map_text: values.manual_map_text || null,
      explanation_level: values.explanation_level,
    });
    router.push(`/courses/${course.id}`);
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold">New Course</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Fill in the course brief. You can add sources and generate the DOCX
          after creating it.
        </p>
      </div>

      <CourseForm onSubmit={handleSubmit} submitLabel="Create Course" />
    </div>
  );
}
