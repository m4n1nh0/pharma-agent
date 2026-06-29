// Tipos espelhando src/application/use_cases/dtos.py e src/domain/entities/*.py

export interface PatientInfo {
  age?: number;
  weight_kg?: number;
  renal_function?: "normal" | "leve" | "moderada" | "grave";
  hepatic_function?: "normal" | "comprometida";
  pregnancy?: boolean;
  allergies?: string[];
  comorbidities?: string[];
}

export interface PrescriptionItem {
  drug_name: string;
  dose: string;
  frequency: string;
  route?: string;
  duration?: string;
  indication?: string | null;
}

// ── Auth ──────────────────────────────────────────────────────────────────

export type UserRole = "farmaceutico" | "medico" | "admin";

export interface UserResponse {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  crm_crf: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}

export interface UserCreatePayload {
  name: string;
  email: string;
  password: string;
  role: UserRole;
  crm_crf?: string | null;
}

export interface UserLoginPayload {
  email: string;
  password: string;
}

// ── Análise de medicamento ───────────────────────────────────────────────

export interface DrugAnalysisRequest {
  drug_name: string;
  context?: string | null;
  patient_info?: PatientInfo | null;
}

export interface DrugAnalysisResult {
  drug_name: string;
  generic_name: string | null;
  drug_class: string | null;
  mechanism_of_action: string;
  indications: string[];
  contraindications: string[];
  adverse_effects: string[];
  dosage_info: string | null;
  known_interactions: string[];
  pregnancy_category: string | null;
  renal_adjustment: string | null;
  hepatic_adjustment: string | null;
  clinical_alerts: string[];
  summary: string;
  confidence_score: number;
  agent_steps: string[];
}

// ── Interações ────────────────────────────────────────────────────────────

export type InteractionSeverity = "contraindicada" | "maior" | "moderada" | "menor" | "desconhecida";

export interface DrugInteraction {
  drug_a: string;
  drug_b: string;
  severity: InteractionSeverity;
  mechanism: string;
  clinical_effect: string;
  management: string;
  evidence_level: string | null;
}

export interface InteractionCheckRequest {
  drugs: string[];
  patient_info?: PatientInfo | null;
}

export interface InteractionCheckResult {
  drugs_analyzed: string[];
  total_interactions: number;
  interactions: DrugInteraction[];
  critical_alerts: string[];
  recommendations: string[];
  overall_risk: "baixo" | "moderado" | "alto" | "crítico";
  agent_steps: string[];
}

// ── Prescrição ────────────────────────────────────────────────────────────

export interface PrescriptionReviewRequest {
  prescription: PrescriptionItem[];
  patient_info?: PatientInfo | null;
  clinical_context?: string | null;
}

export interface PrescriptionAlert {
  type: "interacao" | "dose" | "duplicidade" | "contraindicacao" | "monitoramento";
  severity: "informativo" | "atencao" | "alerta" | "critico";
  drug: string;
  description: string;
  recommendation: string;
}

export interface PrescriptionReviewResult {
  total_items: number;
  items_reviewed: string[];
  alerts: PrescriptionAlert[];
  interactions_found: DrugInteraction[];
  therapeutic_duplications: string[];
  dosage_issues: string[];
  overall_safety_score: number;
  pharmacist_notes: string;
  recommended_monitoring: string[];
  agent_steps: string[];
}

// ── Jobs assíncronos ──────────────────────────────────────────────────────

export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface JobEnqueueResponse {
  job_id: string;
  status: "pending";
  stream_url: string;
  result_url: string;
  [extra: string]: unknown;
}

export interface JobStatusDict {
  job_id: string;
  type: string;
  status: JobStatus;
  progress: number;
  progress_msg: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  has_result: boolean;
}

export interface JobResult<T> {
  job_id: string;
  type: string;
  duration_ms: number | null;
  completed_at: string | null;
  result: T;
}

// Resultado síncrono ou enfileirado — os 3 endpoints de análise retornam um ou outro.
export type SyncOrJob<T> = T | JobEnqueueResponse;

export function isJobEnqueueResponse(v: unknown): v is JobEnqueueResponse {
  return !!v && typeof v === "object" && "job_id" in v && "stream_url" in v;
}
