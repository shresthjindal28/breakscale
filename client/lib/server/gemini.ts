import "server-only";
import { GoogleGenAI } from "@google/genai";
import { z } from "zod";

const geminiEnvironment = z.object({
  GEMINI_API_KEY: z.string().trim().min(1),
  GEMINI_MODEL: z.string().trim().min(1),
});

export function createGeminiClient() {
  const result = geminiEnvironment.safeParse({
    GEMINI_API_KEY: process.env.GEMINI_API_KEY,
    GEMINI_MODEL: process.env.GEMINI_MODEL,
  });
  if (!result.success)
    throw new Error(
      "Set GEMINI_API_KEY and GEMINI_MODEL in .env.local before using Gemini.",
    );
  return {
    client: new GoogleGenAI({ apiKey: result.data.GEMINI_API_KEY }),
    model: result.data.GEMINI_MODEL,
  };
}

export async function generateText(prompt: string) {
  const contents = z.string().trim().min(1).max(20_000).parse(prompt);
  const { client, model } = createGeminiClient();
  const response = await client.models.generateContent({ model, contents });
  return response.text ?? "";
}
