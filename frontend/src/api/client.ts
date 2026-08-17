// Cliente HTTP fino.
// VITE_API_URL vazia → mesma origem (dev com proxy do Vite, ou build servido
// pelo próprio FastAPI). Definida → API em domínio próprio, como no deploy em
// serviços separados. O valor é embutido no bundle em tempo de build.

const TOKEN_KEY = "pharma_token";

export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(apiUrl(path), {
    method: options.method ?? (options.body ? "POST" : "GET"),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401) {
    onUnauthorized?.();
    throw new ApiError("Sessão expirada. Faça login novamente.", 401);
  }

  // 202 com corpo vazio em alguns casos (get_result em PENDING/RUNNING usa HTTPException, então sempre tem JSON)
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new ApiError(extractErrorMessage((data as { detail?: unknown }).detail), res.status);
  }
  return data as T;
}

interface PydanticValidationError {
  loc: (string | number)[];
  msg: string;
}

function isPydanticValidationErrors(detail: unknown): detail is PydanticValidationError[] {
  return Array.isArray(detail) && detail.every((e) => e && typeof e === "object" && "msg" in e && "loc" in e);
}

// FastAPI retorna `detail` como string em erros de negócio (HTTPException), mas como
// lista de { loc, msg } em erros 422 de validação Pydantic — precisamos achatar os dois formatos.
function extractErrorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (isPydanticValidationErrors(detail)) {
    return detail
      .map((e) => {
        const field = e.loc.filter((p) => p !== "body").join(".");
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join("; ");
  }
  return "Erro na requisição";
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
