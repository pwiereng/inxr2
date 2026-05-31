// TEMPORARY — proves CI fails on a failing frontend test. Remove before merge.
import { describe, it, expect } from "vitest";

describe("ci gate", () => {
  it("should fail to prove the frontend-tests CI gate works", () => {
    expect(1).toBe(2);
  });
});
