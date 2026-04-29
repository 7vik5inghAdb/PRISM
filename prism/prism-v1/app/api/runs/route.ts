import { storage } from "@/lib/db/client";

export const runtime = "nodejs";

export async function DELETE() {
  await storage.delete("run:current");
  return Response.json({ ok: true });
}
