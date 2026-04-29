import { z } from "zod";

export const RespondentAnswerSchema = z.object({
  itemIndex: z.number(),
  answer: z
    .string()
    .describe(
      "Answer in the respondent's voice. preference: a one-phrase choice. ranking: comma-separated, most to least. likert_5: a single digit 1-5. open_text: 1-3 sentences.",
    ),
  reasoning: z
    .string()
    .optional()
    .describe("Brief one-sentence justification, if useful."),
});

export const RespondentSchema = z.object({
  id: z.string().describe("Unique id like R01, R02, etc."),
  name: z
    .string()
    .describe(
      "Brief identifying label — first name plus a one-phrase descriptor (e.g., 'Maya — design-led').",
    ),
  answers: z.array(RespondentAnswerSchema),
});

export const PanelResultSchema = z.object({
  panelSize: z.number(),
  respondents: z.array(RespondentSchema),
});

export type RespondentAnswer = z.infer<typeof RespondentAnswerSchema>;
export type Respondent = z.infer<typeof RespondentSchema>;
export type PanelResult = z.infer<typeof PanelResultSchema>;
