# PRISM v1

Synthetic UX research as a single conversation. The PM talks to an orchestrator (Claude Opus 4.7); sub-agents render results as inline cards (persona, instrument, panel, aggregator, charts, secondary research, report).

## Quick start

```bash
pnpm install
cp .env.local.example .env.local   # then add your ANTHROPIC_API_KEY
pnpm dev
```

Open `http://localhost:3000`.

## Environment

- `ANTHROPIC_API_KEY` — required. Used by the orchestrator and every sub-agent that calls Claude.
- `KV_REST_API_URL` / `KV_REST_API_TOKEN` — currently unused. The persistence layer at [lib/db/client.ts](lib/db/client.ts) is an in-memory `Map` (state is lost on dev-server restart and on every Vercel cold start). Swap that file for a `@vercel/kv` or Upstash client when deploying for real.

## Stack

- Next.js 16 (App Router) + Turbopack + TypeScript + Tailwind v4 + shadcn/ui
- AI SDK 6 with `@ai-sdk/anthropic`; Sonnet 4.6 for high-volume panel respondents
- DuckDuckGo via `duck-duck-scrape` for secondary research (no key needed; rate-limited in cloud environments)
- `react-to-print` for PDF export of the report card

## Architecture

- `app/api/chat/route.ts` — POST handler. Streams `streamText` (orchestrator path) or a custom `createUIMessageStream` (ping path). On stream finish, persists messages to `run:current`.
- `app/api/runs/route.ts` — DELETE clears the current run.
- `app/api/debug/run/route.ts` — GET returns the persisted run (for verification).
- `lib/ai/orchestrator.ts` — wraps `streamText` with the orchestrator system prompt + tool registry.
- `lib/ai/tools/*` — sub-agent tools, each with input/output schemas and an `execute` that calls `generateObject` (or fans out parallel sub-calls for the panel).
- `lib/schemas/*` — zod schemas for tool I/O.
- `components/cards/*` — one card component per sub-agent output, each with Edit + Regenerate.
- `components/chat/*` — thread, message, composer.

## Deploy

Standard Next.js deploy on Vercel works. Before deploying:

1. Provision Vercel KV (or Upstash Redis) and set `KV_REST_API_URL` + `KV_REST_API_TOKEN`.
2. Replace [lib/db/client.ts](lib/db/client.ts) with a thin `@vercel/kv` wrapper (same `Storage` interface).
3. Set `ANTHROPIC_API_KEY` as a project env var.

The DuckDuckGo search wrapper at [lib/ai/web-search.ts](lib/ai/web-search.ts) is unreliable on cloud IPs — swap to a keyed provider (Tavily, Brave, Exa) for production secondary research.
