import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { analysisApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { useToast } from "@/components/Toast";
import { useAgentSteps } from "./AppLayout";
import type { DrugAnalysisResult, PatientInfo } from "@/api/types";

const PREGNANCY_BADGE: Record<string, string> = { A: "minor", B: "info", C: "moderate", D: "major", X: "critical" };

export function DrugAnalysisPage() {
  const toast = useToast();
  const { setSteps } = useAgentSteps();

  const [drugName, setDrugName] = useState("");
  const [context, setContext] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [renal, setRenal] = useState("");
  const [pregnancy, setPregnancy] = useState("");
  const [result, setResult] = useState<DrugAnalysisResult | null>(null);

  const mutation = useMutation({
    mutationFn: analysisApi.analyzeDrug,
    onSuccess: (data) => {
      setResult(data);
      setSteps(data.agent_steps ?? []);
    },
    onError: (err) => toast(err instanceof ApiError ? err.message : "Erro na análise", "error"),
  });

  function buildPatientInfo(): PatientInfo | null {
    if (!age && !weight && !renal && !pregnancy) return null;
    return {
      ...(age ? { age: parseInt(age, 10) } : {}),
      ...(weight ? { weight_kg: parseFloat(weight) } : {}),
      ...(renal ? { renal_function: renal as PatientInfo["renal_function"] } : {}),
      ...(pregnancy !== "" ? { pregnancy: pregnancy === "true" } : {}),
    };
  }

  function handleAnalyze() {
    const name = drugName.trim();
    if (!name) {
      toast("Informe o nome do medicamento", "error");
      return;
    }
    mutation.mutate({ drug_name: name, context: context || null, patient_info: buildPatientInfo() });
  }

  function handleClear() {
    setDrugName("");
    setContext("");
    setAge("");
    setWeight("");
    setRenal("");
    setPregnancy("");
    setResult(null);
  }

  return (
    <div>
      <div className="form-section">
        <div className="form-section-title">💊 Análise de Medicamento</div>
        <div className="form-row">
          <div className="form-field full">
            <label>Nome do medicamento</label>
            <input
              type="text"
              value={drugName}
              onChange={(e) => setDrugName(e.target.value)}
              placeholder="Ex: Amoxicilina, Warfarina, Metformina..."
            />
          </div>
          <div className="form-field full">
            <label>Contexto clínico (opcional)</label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Ex: Paciente com ITU recorrente, função renal preservada..."
            />
          </div>
        </div>

        <div className="form-section-title" style={{ marginTop: 18 }}>
          👤 Dados do Paciente (opcional)
        </div>
        <div className="form-row">
          <div className="form-field">
            <label>Idade</label>
            <input type="number" value={age} onChange={(e) => setAge(e.target.value)} placeholder="anos" min={0} max={120} />
          </div>
          <div className="form-field">
            <label>Peso (kg)</label>
            <input type="number" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="kg" min={1} max={300} />
          </div>
          <div className="form-field">
            <label>Função renal</label>
            <select value={renal} onChange={(e) => setRenal(e.target.value)}>
              <option value="">Não informada</option>
              <option value="normal">Normal</option>
              <option value="leve">Leve redução</option>
              <option value="moderada">Moderada (TFG 30-60)</option>
              <option value="grave">Grave (TFG &lt;30)</option>
            </select>
          </div>
          <div className="form-field">
            <label>Gestante?</label>
            <select value={pregnancy} onChange={(e) => setPregnancy(e.target.value)}>
              <option value="">Não informado</option>
              <option value="false">Não</option>
              <option value="true">Sim</option>
            </select>
          </div>
        </div>

        <div className="action-row">
          <button className="btn btn-analyze" onClick={handleAnalyze} disabled={mutation.isPending}>
            {mutation.isPending ? "Analisando..." : "Analisar →"}
          </button>
          <button className="btn btn-ghost" onClick={handleClear}>
            Limpar
          </button>
        </div>
      </div>

      {result && <DrugResultCard result={result} />}
    </div>
  );
}

function DrugResultCard({ result: d }: { result: DrugAnalysisResult }) {
  const pregCat = d.pregnancy_category ?? "—";
  const pregColor = PREGNANCY_BADGE[pregCat] ?? "info";

  return (
    <div className="result-card">
      <div className="result-header">
        <div style={{ fontSize: 18 }}>💊</div>
        <div className="result-title">{d.drug_name}</div>
        <div className="confidence-row">
          <div className="confidence-dot" />
          {Math.round(d.confidence_score * 100)}% confiança
        </div>
      </div>
      <div className="result-body">
        <div className="result-grid" style={{ marginBottom: 16 }}>
          <div className="result-field">
            <div className="result-label">Classe</div>
            <div className="result-value">{d.drug_class ?? "—"}</div>
          </div>
          <div className="result-field">
            <div className="result-label">Categoria Gestação</div>
            <div className="result-value">
              <span className={`badge badge-${pregColor}`}>{pregCat}</span>
            </div>
          </div>
        </div>

        <div className="result-field" style={{ marginBottom: 16 }}>
          <div className="result-label">Mecanismo de Ação</div>
          <div className="result-value">{d.mechanism_of_action}</div>
        </div>

        <div className="divider" />
        <div className="result-grid">
          <div className="result-field">
            <div className="result-label">✅ Indicações</div>
            <ul className="result-list">
              {d.indications.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
          <div className="result-field">
            <div className="result-label">🚫 Contraindicações</div>
            <ul className="result-list">
              {d.contraindications.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="divider" />
        <div className="result-field" style={{ marginBottom: 16 }}>
          <div className="result-label">⚠️ Efeitos Adversos</div>
          <ul className="result-list">
            {d.adverse_effects.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </div>

        {d.renal_adjustment && (
          <div className="alert-box warning">
            <div>🫘</div>
            <div>
              <strong>Ajuste Renal:</strong> {d.renal_adjustment}
            </div>
          </div>
        )}

        {d.clinical_alerts.length > 0 && (
          <div className="alert-box critical">
            <div>🚨</div>
            <div>
              <strong>Alertas Clínicos:</strong> {d.clinical_alerts.join(" • ")}
            </div>
          </div>
        )}

        {d.summary && (
          <>
            <div className="divider" />
            <div className="result-label">Análise do Agente</div>
            <div className="result-value" style={{ marginTop: 8, lineHeight: 1.7 }}>
              {d.summary}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
