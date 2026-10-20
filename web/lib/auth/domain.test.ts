import { describe, expect, it } from "vitest";
import { isAllowedEmail } from "./domain";

describe("isAllowedEmail", () => {
  it("accepts an address in the allowed domain, ignoring case", () => {
    expect(isAllowedEmail("ala@example.org", "example.org")).toBe(true);
    expect(isAllowedEmail("Ala@Example.ORG", "example.org")).toBe(true);
    expect(isAllowedEmail("ala@example.org", "EXAMPLE.org")).toBe(true);
  });

  it("rejects other domains, subdomains and look-alikes", () => {
    expect(isAllowedEmail("ola@evil.com", "example.org")).toBe(false);
    expect(isAllowedEmail("ala@sub.example.org", "example.org")).toBe(false);
    expect(isAllowedEmail("ala@example.org.evil.com", "example.org")).toBe(false);
    expect(isAllowedEmail("ala@example.org@evil.com", "example.org")).toBe(false);
  });

  it("rejects a missing e-mail or a missing domain", () => {
    expect(isAllowedEmail(undefined, "example.org")).toBe(false);
    expect(isAllowedEmail(null, "example.org")).toBe(false);
    expect(isAllowedEmail("", "example.org")).toBe(false);
    expect(isAllowedEmail("ala@example.org", "")).toBe(false);
  });
});
