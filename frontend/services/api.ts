const DEFAULT_API_URL = "http://127.0.0.1:8000";
const DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws";

export function getApiBaseUrl() {
  return process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL;
}

export function getWebSocketBaseUrl() {
  return process.env.EXPO_PUBLIC_WS_URL ?? DEFAULT_WS_URL;
}

export function buildApiUrl(path: string) {
  const base = getApiBaseUrl().replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}
