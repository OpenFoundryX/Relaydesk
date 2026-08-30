export interface HealthResponse {
  status: "ok";
}

export interface ApiInfo {
  name: string;
  version: string;
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function getApiInfo(): Promise<ApiInfo> {
  return request<ApiInfo>("/");
}
