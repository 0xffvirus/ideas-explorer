import { z } from "zod";

export const MAX_RAW_INPUT_CHARS = 5000;
export const WARN_RAW_INPUT_CHARS = 4000;

const optionalText = (max: number, label: string) =>
  z
    .string()
    .trim()
    .max(max, `${label} must be at most ${max} characters.`)
    .optional()
    .transform((value) => (value ? value : undefined));

/** Validation for the one-box intake form. Only `raw_input` is required. */
export const ideaIntakeSchema = z.object({
  raw_input: z
    .string()
    .trim()
    .min(1, "Describe your idea first.")
    .max(
      MAX_RAW_INPUT_CHARS,
      `Keep it under ${MAX_RAW_INPUT_CHARS.toLocaleString("en")} characters.`,
    ),
  context: z
    .object({
      target_region: optionalText(120, "Region"),
      audience_hint: optionalText(300, "Audience"),
      budget_hint: optionalText(120, "Budget"),
    })
    .optional(),
});

export type IdeaIntakeInput = z.input<typeof ideaIntakeSchema>;
export type IdeaIntakeValues = z.infer<typeof ideaIntakeSchema>;

/** The submit button is disabled while the text is empty/whitespace or over the cap. */
export function isRawInputSubmittable(rawInput: string): boolean {
  return rawInput.trim().length > 0 && rawInput.length <= MAX_RAW_INPUT_CHARS;
}
