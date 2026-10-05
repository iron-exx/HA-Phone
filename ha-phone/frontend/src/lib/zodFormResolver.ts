import { toNestErrors, validateFieldsNatively } from "@hookform/resolvers";
import type { FieldValues, Resolver } from "react-hook-form";
import type { ZodType } from "zod";

/**
 * Ersatz für `zodResolver` aus `@hookform/resolvers/zod` (Paket @3.10.0, installiert
 * für Kompatibilität mit anderen Dialogen im Projekt). Dessen Adapter erkennt einen
 * Zod-Fehler an `Array.isArray(err.errors)` – das war die Property in Zod v3. Zod v4
 * (hier installiert) benennt sie in `.issues` um, `.errors` existiert nicht mehr.
 * Dadurch wirft der alte Adapter den Fehler ungefangen weiter, statt ihn als
 * Formularfehler anzuzeigen (unhandled rejection, Button bleibt stumm). Dieser
 * Resolver liest `.issues` und bleibt sonst ein Drop-in-Ersatz.
 */
export function zodFormResolver<T extends FieldValues>(schema: ZodType<T>): Resolver<T> {
  return async (values, _context, options) => {
    const result = schema.safeParse(values);
    if (result.success) {
      options.shouldUseNativeValidation && validateFieldsNatively({}, options);
      return { values: result.data, errors: {} };
    }
    const fieldErrors: Record<string, { type: string; message: string }> = {};
    for (const issue of result.error.issues) {
      const path = issue.path.join(".");
      if (!fieldErrors[path]) fieldErrors[path] = { type: issue.code, message: issue.message };
    }
    return { values: {}, errors: toNestErrors(fieldErrors, options) };
  };
}
