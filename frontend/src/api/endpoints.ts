import { api } from "./client";
import type {
  DrugAnalysisRequest,
  DrugAnalysisResult,
  InteractionCheckRequest,
  InteractionCheckResult,
  JobResult,
  JobStatusDict,
  PrescriptionReviewRequest,
  PrescriptionReviewResult,
  SyncOrJob,
  TokenResponse,
  UserCreatePayload,
  UserLoginPayload,
  UserResponse,
} from "./types";

export const authApi = {
  login: (payload: UserLoginPayload) => api.post<TokenResponse>("/auth/login", payload),
  register: (payload: UserCreatePayload) => api.post<TokenResponse>("/auth/register", payload),
  me: () => api.get<UserResponse>("/auth/me"),
  logout: () => api.post<{ message: string; status: string }>("/auth/logout"),
};

// /analyze é sempre síncrono (1 fármaco).
export const analysisApi = {
  analyzeDrug: (payload: DrugAnalysisRequest) => api.post<DrugAnalysisResult>("/analyze", payload),

  // ≤3 fármacos → resultado direto. >3 → 202 com job_id (ver useJobStream).
  checkInteractions: (payload: InteractionCheckRequest) =>
    api.post<SyncOrJob<InteractionCheckResult>>("/interactions", payload),

  // ≤3 itens → resultado direto. >3 → 202 com job_id.
  reviewPrescription: (payload: PrescriptionReviewRequest) =>
    api.post<SyncOrJob<PrescriptionReviewResult>>("/prescription-review", payload),
};

export const jobsApi = {
  get: (jobId: string) => api.get<JobStatusDict>(`/jobs/${jobId}`),
  getResult: <T>(jobId: string) => api.get<JobResult<T>>(`/jobs/${jobId}/result`),
  cancel: (jobId: string) => api.delete<{ job_id: string; status: string }>(`/jobs/${jobId}`),
};
