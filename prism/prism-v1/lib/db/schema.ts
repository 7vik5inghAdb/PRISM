import { type PrismUIMessage } from "@/lib/ai/ui-message";

export type RunState = {
  id: string;
  createdAt: string;
  updatedAt: string;
  messages: PrismUIMessage[];
};
