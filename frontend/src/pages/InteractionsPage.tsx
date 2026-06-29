import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { analysisApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { useToast } from "@/components/Toast";
import { useAgentSteps } from "./AppLayout";
import { useJobStream } from "@/hooks/useJobStream";
import { isJobEnqueueResponse, type DrugInteraction, type InteractionCheckResult } from "@/api/types";

const SEVERITY_BADGE: Record<string, string> = { contraindicada: "critical", maior: "major", moderada: "moderate", menor: "minor" };
const RISK_BADGE: Record<string, string> = { baixo: "minor", moderado: "moderate", alto: "major", crítico: "critical" };

export function InteractionsPage() {
  const toast = useToast();
  const { setSteps } = useAgentSteps();
  const jobStream = useJobStream<InteractionCheckResult>();

  const [drugTags, setDrugTags] = useState<string[]>([]);
  const [drugInput, setDrugInput] = useState("");
  const [result, setResult] = useState<InteractionCheckResult | null>(null);

  const mutation = useMutation({
    mutationFn: analysisApi.checkInteractions,
    onSuccess: (data) => {
      if (isJobEnqueueResponse(data)) {
        toast(`Enfileirado — acompanhando ${data.pairs ?? ""} combinações...`, "success");
        jobStream.watch(data.job_id, (finalResult) => {
          setResult(finalResult);
          setSteps(finalResult.agent_steps ?? []);
        });
        return;
      }
      setResult(data);
      setSteps(data.agent_steps ?? []);
    },
    onError: (err) => toast(err instanceof ApiError ? err.message : "Erro na verificação", "error"),
  });

  function addTag() {
    const name = drugInput.trim();
    if (!name) return;
    setDrugTags((tags) => [...tags, name]);
    setDrugInput("");
  }

  function removeTag(i: number) {
    setDrugTags((tags) => tags.filter((_, idx) => idx !== i));
  }

  function handleCheck() {
    if (drugTags.length < 2) {
      toast("Adicione pelo menos 2 medicamentos", "error");
      return;
    }
    jobStream.reset();
    mutation.mutate({ drugs: drugTags });
  }

  function handleClear() {
    setDrugTags([]);
    setDrugInput("");
    setResult(null);
    jobStream.reset();
  }

  const busy = mutation.isPending || (jobStream.status !== "idle" && jobStream.status !== "completed" && jobStream.status !== "failed");

  return (
    <div>
      <div className="form-section">
        <div className="form-section-title">⚡ Verificação de Interações</div>
        <div className="form-field">
          <label>Adicionar medicamento</label>
          <div className="drug-input-row">
            <input
              type="text"
              value={drugInput}
              onChange={(e) => setDrugInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addTag();
                }
              }}
              placeholder="Nome do medicamento"
            />
            <button className="btn btn-ghost" onClick={addTag} style={{ whiteSpace: "nowrap" }}>
              + Adicionar
            </button>
          </div>
          <div className="drug-tags">
            {drugTags.map((d, i) => (
              <div className="drug-tag" key={i}>
                {d}
                <button onClick={() => removeTag(i)} title="Remover">
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
        <div className="action-row">
          <button className="btn btn-analyze" onClick={handleCheck} disabled={busy}>
            {busy ? jobStream.progressMsg || "Verificando..." : "Verificar Interações →"}
          </button>
          <button className="btn btn-ghost" onClick={handleClear}>
            Limpar
          </button>
        </div>
      </div>

      {result && <InteractionResultCard result={result} />}
    </div>
  );
}

function InteractionResultCard({ result: d }: { result: InteractionCheckResult }) {
  const riskColor = RISK_BADGE[d.overall_risk] ?? "info";

  return (
    <div className="result-card">
      <div className="result-header">
        <div style={{ fontSize: 18 }}>⚡</div>
        <div className="result-title">Resultado: {d.total_interactions} interação(ões) encontrada(s)</div>
        <span className={`badge badge-${riskColor}`}>Risco {d.overall_risk}</span>
      </div>
      <div className="result-body">
        {d.critical_alerts.map((a, i) => (
          <div className="alert-box critical" key={i}>
            <div>🚨</div>
            <div>{a}</div>
          </div>
        ))}

        {d.interactions.length === 0 ? (
          <div style={{ color: "var(--slate-600)", fontSize: 13, padding: "12px 0" }}>Nenhuma interação documentada encontrada</div>
        ) : (
          d.interactions.map((ix, i) => <InteractionCard interaction={ix} key={i} />)
        )}

        {d.recommendations.length > 0 && (
          <>
            <div className="divider" />
            <div className="result-label">Recomendações</div>
            <ul className="result-list" style={{ marginTop: 8 }}>
              {d.recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

function InteractionCard({ interaction: ix }: { interaction: DrugInteraction }) {
  return (
    <div className="interaction-card">
      <div className="interaction-header">
        <div className="interaction-drugs">
          {ix.drug_a} <span>×</span> {ix.drug_b}
        </div>
        <span className={`badge badge-${SEVERITY_BADGE[ix.severity] ?? "info"}`}>{ix.severity}</span>
      </div>
      <div className="result-label" style={{ marginBottom: 4 }}>
        Mecanismo
      </div>
      <div className="result-value" style={{ marginBottom: 10 }}>
        {ix.mechanism}
      </div>
      <div className="result-label" style={{ marginBottom: 4 }}>
        Manejo
      </div>
      <div className="result-value">{ix.management}</div>
    </div>
  );
}
