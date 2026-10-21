import { describe, expect, it } from "vitest";
import { describeVersions, journeyFromForm, nodeCount } from "./journeys";

describe("journeyFromForm", () => {
  it("trims the name", () => {
    const form = new FormData();
    form.append("name", "  Welcome  ");
    expect(journeyFromForm(form)).toEqual({ name: "Welcome" });
  });
});

describe("describeVersions", () => {
  const v = (version: number, published_at: string | null) => ({
    id: `v${version}`,
    version,
    published_at,
  });

  it("names the highest published version and the draft", () => {
    expect(
      describeVersions([
        v(1, "2026-10-21T10:00:00+00:00"),
        v(2, "2026-10-21T11:00:00+00:00"),
        v(3, null),
      ]),
    ).toBe("v2 published, draft v3");
    expect(describeVersions([v(1, null)])).toBe("draft v1");
    expect(describeVersions([v(1, "2026-10-21T10:00:00+00:00")])).toBe("v1 published");
  });

  it("handles a journey without versions, embedded or not", () => {
    expect(describeVersions([])).toBe("no versions");
    expect(describeVersions(undefined)).toBe("no versions");
  });
});

describe("nodeCount", () => {
  it("counts nodes and tolerates a draft without a list", () => {
    const base = { id: "v1", version: 1, published_at: null, layout: {} };
    expect(nodeCount({ ...base, definition: { nodes: [{}, {}] } })).toBe(2);
    expect(nodeCount({ ...base, definition: {} })).toBe(0);
  });
});
