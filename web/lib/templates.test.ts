import { describe, expect, it } from "vitest";
import { specFromForm } from "./templates";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.append(key, value);
  return data;
}

describe("specFromForm", () => {
  it("trims text fields and splits lists on commas and newlines", () => {
    const spec = specFromForm(
      form({
        name: " welcome_offer ",
        language: "pl",
        category: "UTILITY",
        body: "Cześć {{1}}, oferta {{2}}",
        example_values: "Ala, 20%\n",
        quick_replies: "Tak\nNie,",
      }),
    );
    expect(spec).toEqual({
      name: "welcome_offer",
      language: "pl",
      category: "UTILITY",
      body: "Cześć {{1}}, oferta {{2}}",
      example_values: ["Ala", "20%"],
      quick_replies: ["Tak", "Nie"],
    });
  });

  it("defaults the category and tolerates missing lists", () => {
    const spec = specFromForm(form({ name: "x", language: "pl", body: "Hi" }));
    expect(spec.category).toBe("MARKETING");
    expect(spec.example_values).toEqual([]);
    expect(spec.quick_replies).toEqual([]);
  });
});
