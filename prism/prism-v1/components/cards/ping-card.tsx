export function PingCard({
  id,
  ts,
  label,
}: {
  id: string;
  ts: string;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-zinc-500">
        Ping card
      </div>
      <div className="mt-1 text-sm font-medium text-zinc-900">{label}</div>
      <dl className="mt-2 grid gap-1 text-xs text-zinc-500">
        <div className="flex gap-2">
          <dt>id:</dt>
          <dd className="font-mono">{id}</dd>
        </div>
        <div className="flex gap-2">
          <dt>ts:</dt>
          <dd className="font-mono">{ts}</dd>
        </div>
      </dl>
    </div>
  );
}
