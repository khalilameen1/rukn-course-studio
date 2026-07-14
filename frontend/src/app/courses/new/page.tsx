"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import CourseForm, { type CourseFormValues } from "@/components/courses/CourseForm";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";

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
      generation_preset: values.generation_preset,
    });
    router.push(`/courses/${course.id}`);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <PageHeader
        title="New Course"
        description="Fill in the course brief. Sources and generation come after creating it - the final export is a spoken lecturer script only, ready to record."
      />

      <Card>
        <CourseForm onSubmit={handleSubmit} submitLabel="Create Course" />
      </Card>
    </div>
  );
}
