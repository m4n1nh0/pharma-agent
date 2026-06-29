import { useCallback, useRef, useState } from "react";
import { getToken } from "@/api/client";
import { jobsApi } from "@/api/endpoints";
import type { JobResult, JobStatusDict } from "@/api/types";

interface JobStreamState {
  status: JobStatusDict["status"] | "idle";
  progress: number;
  progressMsg: string;
  error: string | null;
}

/**
 * Acompanha um job assíncrono via SSE (`/jobs/{id}/events`) e busca o resultado
 * final em `/jobs/{id}/result` quando o job completa.
 *
 * EventSource não suporta header Authorization, então o token vai como query
 * param — o backend aceita Bearer no header; aqui usamos fetch+ReadableStream
 * para poder enviar o header normalmente.
 */
export function useJobStream<T>() {
  const [state, setState] = useState<JobStreamState>({ status: "idle", progress: 0, progressMsg: "", error: null });
  const abortRef = useRef<AbortController | null>(null);

  const watch = useCallback((jobId: string, onComplete: (result: T) => void) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ status: "pending", progress: 0, progressMsg: "Na fila...", error: null });

    (async () => {
      try {
        const res = await fetch(`/jobs/${jobId}/events`, {
          headers: { Authorization: `Bearer ${getToken() ?? ""}` },
          signal: controller.signal,
        });
        if (!res.body) throw new Error("Stream indisponível");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const line = part.replace(/^data:\s*/, "").trim();
            if (!line || line === "[DONE]") continue;
            const payload = JSON.parse(line) as JobStatusDict;
            setState({
              status: payload.status,
              progress: payload.progress,
              progressMsg: payload.progress_msg,
              error: payload.error,
            });

            if (payload.status === "completed") {
              const full = await jobsApi.getResult<T>(jobId);
              onComplete((full as JobResult<T>).result);
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setState((s) => ({ ...s, status: "failed", error: err instanceof Error ? err.message : "Erro no stream" }));
      }
    })();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ status: "idle", progress: 0, progressMsg: "", error: null });
  }, []);

  return { ...state, watch, reset };
}
