import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SourceDropzone from "@/components/courses/new/SourceDropzone";
import CourseMapWorkspace from "@/components/courses/new/CourseMapWorkspace";
import ReadinessPanel from "@/components/courses/new/ReadinessPanel";
import { SOURCE_INTENT_OPTIONS } from "@/lib/sourceIntentOptions";

describe("Create Course workspace UX", () => {
  it("renders upload area with human copy", () => {
    render(
      <SourceDropzone
        fileIntent="classify"
        filePriority="medium"
        includeGen
        onFileIntentChange={vi.fn()}
        onFilePriorityChange={vi.fn()}
        onIncludeGenChange={vi.fn()}
        onFileSelected={vi.fn()}
        onPasteInstead={vi.fn()}
      />,
    );
    expect(screen.getByText("Upload course sources")).toBeInTheDocument();
    expect(screen.getByText("Paste text instead")).toBeInTheDocument();
    expect(screen.queryByText(/raw_material/i)).not.toBeInTheDocument();
  });

  it("shows plain source intent options", () => {
    render(
      <SourceDropzone
        fileIntent="knowledge"
        filePriority="medium"
        includeGen
        onFileIntentChange={vi.fn()}
        onFilePriorityChange={vi.fn()}
        onIncludeGenChange={vi.fn()}
        onFileSelected={vi.fn()}
      />,
    );
    expect(screen.getByText("How should ROKN use this source?")).toBeInTheDocument();
    for (const opt of SOURCE_INTENT_OPTIONS) {
      expect(screen.getByText(opt.label)).toBeInTheDocument();
    }
  });

  it("renders course map editor and generate button", () => {
    render(
      <CourseMapWorkspace
        mapText=""
        mapStatus={null}
        mapUnsaved={false}
        mapSaved={false}
        canGenerate
        onMapChange={vi.fn()}
        onGenerateMap={vi.fn()}
        onSaveMap={vi.fn()}
        onClearMap={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /generate course map/i })).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/write or paste the course map/i),
    ).toBeInTheDocument();
  });

  it("renders readiness panel with next step", () => {
    render(
      <ReadinessPanel
        briefComplete={false}
        sourcesReady={0}
        sourcesPending={0}
        mapStatus="empty"
        mapUnsaved={false}
        canCreate={false}
        nextStep="Add a title, target learner, and course goal."
        disabledReason="Add a course title first"
      />,
    );
    expect(screen.getByText("Course readiness")).toBeInTheDocument();
    expect(screen.getByText(/Add a title, target learner/i)).toBeInTheDocument();
  });

  it("does not expose Rukn branding in primary labels", () => {
    render(
      <SourceDropzone
        fileIntent="classify"
        filePriority="medium"
        includeGen
        onFileIntentChange={vi.fn()}
        onFilePriorityChange={vi.fn()}
        onIncludeGenChange={vi.fn()}
        onFileSelected={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Rukn/i)).not.toBeInTheDocument();
  });
});
