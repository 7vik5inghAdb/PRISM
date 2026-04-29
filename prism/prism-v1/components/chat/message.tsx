import { PingCard } from "@/components/cards/ping-card";
import { type PrismUIMessage } from "@/lib/ai/ui-message";

export function Message({ message }: { message: PrismUIMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      className={`flex flex-col gap-2 ${
        isUser ? "items-end" : "items-start"
      }`}
    >
      {message.parts.map((part, i) => {
        if (part.type === "text") {
          return (
            <div
              key={i}
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                isUser
                  ? "bg-zinc-900 text-zinc-50"
                  : "bg-zinc-100 text-zinc-900"
              }`}
            >
              <span className="whitespace-pre-wrap">{part.text}</span>
            </div>
          );
        }
        if (part.type === "data-ping-card") {
          return (
            <div key={i} className="w-full max-w-[80%]">
              <PingCard {...part.data} />
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
