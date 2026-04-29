import { type PrismUIMessage } from "@/lib/ai/ui-message";
import { storage } from "./client";
import { type RunState } from "./schema";

const key = (id: string) => `run:${id}`;

export async function getRun(id: string): Promise<RunState | null> {
  return storage.get<RunState>(key(id));
}

export async function saveRun(state: RunState): Promise<void> {
  await storage.set(key(state.id), state);
}

export async function persistMessages(
  id: string,
  messages: PrismUIMessage[],
): Promise<void> {
  const existing = await getRun(id);
  const now = new Date().toISOString();
  await saveRun({
    id,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    messages,
  });
}
