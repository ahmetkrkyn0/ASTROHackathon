const DEFAULT_API_BASE_URL = "/api";

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

function buildUrl(path, query = {}) {
  const baseUrl = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${baseUrl}${normalizedPath}`, window.location.origin);

  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    url.searchParams.set(key, String(value));
  });

  return url.toString();
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof payload === "string"
      ? payload
      : payload?.message ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

export function isMockApiEnabled() {
  return import.meta.env.VITE_USE_MOCK_API !== "false";
}

export async function apiGet(path, { query, headers } = {}) {
  const response = await fetch(buildUrl(path, query), {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...headers,
    },
  });

  return parseResponse(response);
}

export async function apiPost(path, body, { query, headers } = {}) {
  const response = await fetch(buildUrl(path, query), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body ?? {}),
  });

  return parseResponse(response);
}

export default {
  apiGet,
  apiPost,
  isMockApiEnabled,
};
