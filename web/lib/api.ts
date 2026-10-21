import "server-only";
import { createClient } from "@/lib/supabase/server";

/**
 * Error from our API: `status` is the HTTP code, `message` the API's `detail` (joined when it is
 * a list), `details` the list itself (validation problems come as one string per problem).
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details: string[] = [],
  ) {
    super(message);
  }
}

type Options = { method?: "GET" | "POST" | "PUT"; body?: unknown };

function detailsOf(payload: unknown): string[] {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return [];
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") return [detail];
  if (!Array.isArray(detail)) return [];
  return detail.map((item) =>
    typeof item === "string"
      ? item
      : item && typeof item === "object" && "msg" in item
        ? String((item as { msg: unknown }).msg)
        : JSON.stringify(item),
  );
}

/** Calls our FastAPI as the signed-in user. Server side only: API_URL never reaches the browser. */
export async function apiFetch<T>(path: string, options: Options = {}): Promise<T> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new ApiError(401, "not signed in");
  }
  const response = await fetch(`${process.env.API_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      "Content-Type": "application/json",
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const details = detailsOf(payload);
    throw new ApiError(
      response.status,
      details.length > 0 ? details.join("; ") : `API responded ${response.status}`,
      details,
    );
  }
  return (await response.json()) as T;
}
