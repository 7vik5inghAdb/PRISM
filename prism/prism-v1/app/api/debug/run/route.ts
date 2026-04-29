import { getRun } from "@/lib/db/runs";

export const runtime = "nodejs";

export async function GET() {
  const run = await getRun("current");
  return Response.json(run ?? null);
}
