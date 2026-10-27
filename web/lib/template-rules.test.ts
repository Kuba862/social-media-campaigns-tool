import { describe, expect, it } from "vitest";
import {
  bodyProblems,
  examplesByName,
  exampleRows,
  nameProblem,
  serviceSchema,
  templateDefaults,
  previewSegments,
  templateSchema,
  toTemplateSpec,
  variablesOf,
} from "./template-rules";

describe("variables and Meta's placement rules", () => {
  it("lists variables once, in order of first appearance", () => {
    expect(variablesOf("Hi {{first_name}}, {{offer}} for {{first_name}}")).toEqual([
      "first_name",
      "offer",
    ]);
    expect(variablesOf("no variables")).toEqual([]);
  });

  it("reports the same problems as the API", () => {
    expect(bodyProblems("Cześć {{first_name}}, oferta {{offer}}.")).toEqual([]);
    expect(bodyProblems("{{a}} hi")).toContain("the body must not start with a variable");
    expect(bodyProblems("hi {{a}}")).toContain("the body must not end with a variable");
    expect(bodyProblems("hi {{a}} {{b}} x")).toContain("two variables must be separated by text");
    expect(bodyProblems("hi {{1}} and {{b}} x")).toContain(
      "variables must be all named ({{first_name}}) or all positional ({{1}})",
    );
    expect(bodyProblems("hi {{2}} x")).toContain("placeholders must be numbered 1..n without gaps");
    expect(bodyProblems("hi {{1a}} x")).toContain("variable names must start with a letter: 1a");
  });

  it("keeps typed examples while the variables change", () => {
    expect(exampleRows("Hi {{a}} and {{b}}.", [{ value: "Ala" }])).toEqual([
      { value: "Ala" },
      { value: "" },
    ]);
  });
});

describe("schemas", () => {
  it("requires an https image for an image header and caps URL buttons", () => {
    const base = { ...templateDefaults, body: "Cześć {{a}} tam", example_values: [{ value: "x" }] };
    expect(templateSchema.safeParse(base).success).toBe(true);
    const image = templateSchema.safeParse({
      ...base,
      header_kind: "image",
      header_image_url: "ftp://x",
    });
    expect(image.success).toBe(false);
    const urls = {
      ...base,
      buttons: Array.from({ length: 3 }, () => ({
        type: "url" as const,
        text: "a",
        url: "https://x.y",
      })),
    };
    expect(templateSchema.safeParse(urls).error?.issues.map((i) => i.message)).toContain(
      "at most 2 URL buttons",
    );
  });

  it("builds the API body with nulls for the parts left empty", () => {
    const spec = toTemplateSpec("hello_1", {
      ...templateDefaults,
      header_kind: "text",
      header: " Nowość ",
      body: " Cześć {{first_name}}! ",
      buttons: [{ type: "quick_reply", text: "Tak", url: "" }],
      example_values: [{ value: "Ala" }],
    });
    expect(spec).toEqual({
      name: "hello_1",
      language: "pl",
      category: "UTILITY",
      header: "Nowość",
      header_image_url: null,
      body: "Cześć {{first_name}}!",
      footer: null,
      buttons: [{ type: "quick_reply", text: "Tak" }],
      example_values: ["Ala"],
    });
  });

  it("keeps variables and long captions out of service messages", () => {
    expect(
      serviceSchema.safeParse({ language: "pl", image_url: "", body: "Hej {{a}}" }).success,
    ).toBe(false);
    const long = { language: "pl", image_url: "https://x.y/a.png", body: "a".repeat(1025) };
    expect(serviceSchema.safeParse(long).success).toBe(false);
    expect(
      serviceSchema.safeParse({ language: "pl", image_url: "", body: "Dziękujemy 🙏" }).success,
    ).toBe(true);
  });

  it("checks the name against Meta's pattern and the taken names", () => {
    expect(nameProblem("Hello", new Set())).toMatch(/lowercase/);
    expect(nameProblem("hello_1", new Set(["hello_1"]))).toMatch(/taken/);
    expect(nameProblem("hello_1", new Set())).toBeNull();
  });
});

describe("preview", () => {
  it("replaces variables with their examples and keeps the placeholder otherwise", () => {
    const examples = examplesByName("Cześć {{first_name}}, {{offer}}!", [{ value: "Ala" }]);
    expect(examples).toEqual({ first_name: "Ala", offer: "" });
    expect(previewSegments("Cześć {{first_name}}, {{offer}}!", examples)).toEqual([
      { text: "Cześć " },
      { text: "Ala", variable: "first_name" },
      { text: ", " },
      { text: "{{offer}}", variable: "offer" },
      { text: "!" },
    ]);
    expect(previewSegments("plain", {})).toEqual([{ text: "plain" }]);
  });
});
