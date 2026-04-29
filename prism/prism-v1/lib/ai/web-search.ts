import { search } from "duck-duck-scrape";

export type WebSearchResult = {
  title: string;
  url: string;
  snippet: string;
};

export async function webSearch(
  query: string,
  maxResults = 6,
): Promise<WebSearchResult[]> {
  const out = await search(query);
  if (out.noResults) return [];
  return out.results.slice(0, maxResults).map((r) => ({
    title: r.title,
    url: r.url,
    snippet: r.description,
  }));
}
