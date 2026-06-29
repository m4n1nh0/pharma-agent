import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { analysisApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { useToast } from "@/components/Toast";
import { useAgentSteps } from "./AppLayout";
import { useJobStream } from "@/hooks/useJobStream";
import { isJobEnqueueResponse, type PrescriptionItem, type PrescriptionReviewResult } from "@/api/types";

let nextId = 0;

interface PrescDraftItem {
  id: number;
  drug_name: string;
  dose: string;
  frequency: string;
  indication: string;
}

function emptyItem(): PrescDraftItem {
  return { id: nextId++, drug_name: "", dose: "", frequency: "", indication: "" };
}

export function PrescriptionPage() {
  const toast = useToast();
  const { setSteps } = useAgentSteps();
  const jobStream = useJobStream<PrescriptionReviewResult>();

  const [items, setItems] = useState<PrescDraftItem[]>([emptyItem()]);
  const [context, setContext] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [result, setResult] = useState<PrescriptionReviewResult | null>(null);

  const mutation = useMutation({
    mutationFn: analysisApi.reviewPrescription,
    onSuccess: (data) => {
      if (isJobEnqueueResponse(data)) {
        toast(`Enfileirado — revisando ${data.items ?? ""} medicamento(s)...`, "success");
        jobStream.watch(data.job_id, (finalResult) => {
          setResult(finalResult);
          setSteps(finalResult.agent_steps ?? []);
        });
        return;
      }
      setResult(data);
      setSteps(data.agent_steps ?? []);
    },
    onError: (err) => toast(err instanceof ApiError ? err.message : "Erro na revisão", "error"),
  });

  function updateItem(id: number, patch: Partial<PrescDraftItem>) {
    setItems((list) => list.map((i) => (i.id === id ? { ...i, ...patch } : i)));
  }

  function removeItem(id: number) {
    setItems((list) => list.filter((i) => i.id !== id));
  }

  function handleReview() {
    const prescription: PrescriptionItem[] = items
      .filter((i) => i.drug_name.trim())
      .map((i) => ({ drug_name: i.drug_name.trim(), dose: i.dose.trim(), frequency: i.frequency.trim(), indication: i.indication.trim() || null }));

    if (prescription.length === 0) {
      toast("Adicione ao menos um medicamento", "error");
      return;
    }

    const patientInfo = age || weight ? { age: age ? parseInt(age, 10) : undefined, weight_kg: weight ? parseFloat(weight) : undefined } : null;

    jobStream.reset();
    mutation.mutate({ prescription, patient_info: patientInfo, clinical_context: context || null });
  }

  function handleClear() {
    setItems([emptyItem()]);
    setContext("");
    setAge("");
    setWeight("");
    setResult(null);
    jobStream.reset();
  }

  const busy = mutation.isPending || (jobStream.status !== "idle" && jobStream.status !== "completed" && jobStream.status !== "failed");

  return (
    <div>
      <div className="form-section">
        <div className="form-section-title">📋 Revisão de Prescrição</div>

        <div className="presc-list">
          {items.map((item, idx) => (
            <div className="presc-item" key={item.id}>
              <div className="presc-item-header">
                <span>Medicamento {idx + 1}</span>
                <button className="remove-btn" onClick={() => removeItem(item.id)} title="Remover">
                  ×
                </button>
              </div>
              <div className="presc-item-row">
                <div className="form-field">
                  <label>Nome</label>
                  <input type="text" value={item.drug_name} onChange={(e) => updateItem(item.id, { drug_name: e.target.value })} placeholder="Ex: Metformina" />
                </div>
                <div className="form-field">
                  <label>Dose</label>
                  <input type="text" value={item.dose} onChange={(e) => updateItem(item.id, { dose: e.target.value })} placeholder="Ex: 850mg" />
                </div>
                <div className="form-field">
                  <label>Frequência</label>
                  <input type="text" value={item.frequency} onChange={(e) => updateItem(item.id, { frequency: e.target.value })} placeholder="Ex: 2x/dia" />
                </div>
                <div className="form-field">
                  <label>Indicação</label>
                  <input type="text" value={item.indication} onChange={(e) => updateItem(item.id, { indication: e.target.value })} placeholder="Ex: DM2" />
                </div>
              </div>
            </div>
          ))}
        </div>

        <button className="btn btn-ghost" onClick={() => setItems((list) => [...list, emptyItem()])} style={{ width: "100%", marginBottom: 16 }}>
          + Adicionar medicamento
        </button>

        <div className="form-field">
          <label>Contexto clínico</label>
          <textarea value={context} onChange={(e) => setContext(e.target.value)} placeholder="Diagnósticos, comorbidades, objetivo da revisão..." />
        </div>

        <div className="form-row" style={{ marginTop: 14 }}>
          <div className="form-field">
            <label>Idade do paciente</label>
            <input type="number" value={age} onChange={(e) => setAge(e.target.value)} placeholder="anos" />
          </div>
          <div className="form-field">
            <label>Peso (kg)</label>
            <input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="kg" />
          </div>
        </div>

        <div className="action-row">
          <button className="btn btn-analyze" onClick={handleReview} disabled={busy}>
            {busy ? jobStream.progressMsg || "Revisando..." : "Revisar Prescrição →"}
          </button>
          <button className="btn btn-ghost" onClick={handleClear}>
            Limpar
          </button>
        </div>
      </div>

      {result && <PrescriptionResultCard result={result} />}
    </div>
  );
}

function PrescriptionResultCard({ result: d }: { result: PrescriptionReviewResult }) {
  const scoreColor = d.overall_safety_score >= 8 ? "var(--green-400)" : d.overall_safety_score >= 5 ? "var(--amber-400)" : "var(--red-400)";

  return (
    <div className="result-card">
      <div className="result-header">
        <div style={{ fontSize: 18 }}>📋</div>
        <div className="result-title">Revisão — {d.total_items} medicamento(s)</div>
      </div>
      <div className="result-body">
        <div className="score-meter">
          <div>
            <div className="score-value" style={{ color: scoreColor }}>
              {d.overall_safety_score.toFixed(1)}
            </div>
            <div className="score-label">Score de segurança</div>
          </div>
          <div className="score-bar-track">
            <div className="score-bar-fill" style={{ width: `${d.overall_safety_score * 10}%`, background: scoreColor }} />
          </div>
          <div style={{ fontSize: 22 }}>{d.overall_safety_score >= 8 ? "✅" : d.overall_safety_score >= 5 ? "⚠️" : "🚨"}</div>
        </div>

        {d.alerts.map((a, i) => (
          <div className={`alert-box ${a.severity === "critico" ? "critical" : "warning"}`} key={i}>
            <div>{a.severity === "critico" ? "🚨" : "⚠️"}</div>
            <div>
              <strong>{a.drug}:</strong> {a.description}
              <br />
              <span style={{ fontSize: 12, opacity: 0.8 }}>{a.recommendation}</span>
            </div>
          </div>
        ))}

        <div className="result-label" style={{ margin: "16px 0 8px" }}>
          Medicamentos Revisados
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
          {d.items_reviewed.map((i, idx) => (
            <span className="drug-tag" key={idx}>
              {i}
            </span>
          ))}
        </div>

        {d.pharmacist_notes && (
          <>
            <div className="divider" />
            <div className="result-label">Notas Farmacêuticas</div>
            <div className="result-value" style={{ marginTop: 8, lineHeight: 1.7 }}>
              {d.pharmacist_notes}
            </div>
          </>
        )}

        {d.recommended_monitoring.length > 0 && (
          <>
            <div className="divider" />
            <div className="result-label">Monitoramento Recomendado</div>
            <ul className="result-list" style={{ marginTop: 8 }}>
              {d.recommended_monitoring.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
