import { describe, expect, it } from "vitest";
import type { ResolverOptions } from "react-hook-form";
import { z } from "zod";
import { zodFormResolver } from "./zodFormResolver";

const schema = z.object({
  name: z.string().trim().min(1, "Pflichtfeld"),
  a: z.object({ b: z.string().min(3, "Zu kurz").regex(/^x/, "Muss mit x beginnen") }),
});
type Values = z.infer<typeof schema>;

const OPTIONS = { fields: {}, shouldUseNativeValidation: false } as unknown as ResolverOptions<Values>;

describe("zodFormResolver", () => {
  it("liefert bei gültigen Werten die geparsten (getrimmten) Werte ohne Fehler", async () => {
    const result = await zodFormResolver(schema)({ name: "  Anna  ", a: { b: "xyz" } }, undefined, OPTIONS);
    expect(result.values).toEqual({ name: "Anna", a: { b: "xyz" } });
    expect(result.errors).toEqual({});
  });

  it("meldet verschachtelte Pfade als errors.a.b.message und nimmt je Pfad die erste Meldung", async () => {
    const result = await zodFormResolver(schema)({ name: "Anna", a: { b: "y" } }, undefined, OPTIONS);
    expect(result.values).toEqual({});
    expect(result.errors).toHaveProperty("a.b.message", "Zu kurz");
    expect(result.errors).not.toHaveProperty("name");
  });

  it("nimmt je Pfad nur die erste Meldung (flaches Feld mit zwei Verstößen)", async () => {
    const flat = z.object({ code: z.string().min(3, "Zu kurz").regex(/^x/, "Muss mit x beginnen") });
    const opts = { fields: {}, shouldUseNativeValidation: false } as unknown as ResolverOptions<z.infer<typeof flat>>;
    const result = await zodFormResolver(flat)({ code: "y" }, undefined, opts);
    expect(result.errors).toHaveProperty("code.message", "Zu kurz");
    expect(result.errors).toHaveProperty("code.type", "too_small");
  });

  it("meldet mehrere ungültige Felder gleichzeitig", async () => {
    const result = await zodFormResolver(schema)({ name: "", a: { b: "y" } }, undefined, OPTIONS);
    expect(result.errors).toHaveProperty("name.message", "Pflichtfeld");
    expect(result.errors).toHaveProperty("a.b.message", "Zu kurz");
  });
});
