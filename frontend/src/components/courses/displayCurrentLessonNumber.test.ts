import { describe, expect, it } from "vitest";
import { displayCurrentLessonNumber } from "./GeneratePanel";

describe("displayCurrentLessonNumber", () => {
  it("shows the in-progress lesson while generating", () => {
    expect(displayCurrentLessonNumber(4, 10, false)).toBe(5);
  });

  it("never exceeds total when all lessons are saved but job is still running", () => {
    expect(displayCurrentLessonNumber(113, 113, false)).toBe(113);
  });

  it("caps at total on terminal status", () => {
    expect(displayCurrentLessonNumber(113, 113, true)).toBe(113);
  });

  it("handles zero totals safely", () => {
    expect(displayCurrentLessonNumber(0, 0, false)).toBe(0);
  });
});
