export interface Storage {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  delete(key: string): Promise<void>;
}

const memory = new Map<string, unknown>();

export const storage: Storage = {
  async get<T>(key: string): Promise<T | null> {
    return (memory.get(key) as T | undefined) ?? null;
  },
  async set<T>(key: string, value: T): Promise<void> {
    memory.set(key, value);
  },
  async delete(key: string): Promise<void> {
    memory.delete(key);
  },
};
