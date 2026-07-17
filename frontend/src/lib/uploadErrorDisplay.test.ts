import { describe, expect, it } from "vitest";
import { ApiError, formatUploadErrorForDisplay } from "@/lib/api";

describe("formatUploadErrorForDisplay", () => {
  it("maps 415 to Arabic unsupported-type message", () => {
    const err = new ApiError("Unsupported file type '.exe'.", { status: 415 });
    expect(formatUploadErrorForDisplay(err)).toContain("نوع الملف غير مدعوم");
  });

  it("maps 413 to Arabic size message", () => {
    const err = new ApiError("File too large.", { status: 413 });
    expect(formatUploadErrorForDisplay(err)).toContain("أكبر من الحد");
  });

  it("maps 400 to Arabic bad-request message", () => {
    const err = new ApiError("Empty or unreadable file.", { status: 400 });
    expect(formatUploadErrorForDisplay(err)).toContain("طلب غير صحيح");
  });

  it("includes correlation id on unexpected 500", () => {
    const err = new ApiError("Internal server error", {
      status: 500,
      correlationId: "abc123",
    });
    expect(formatUploadErrorForDisplay(err)).toContain("abc123");
  });
});
