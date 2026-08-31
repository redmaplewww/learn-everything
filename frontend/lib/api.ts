export type Progress = {
  total: number;
  done: number;
  learning: number;
  pending: number;
  weak: number;
  skipped: number;
  pct: number;
};

export type ProjectSummary = {
  id: number;
  title: string;
  topic: string;
  status: string;
  progress: Progress;
  created_at: string;
};

export type Project = ProjectWorkspace["project"];
export type ProjectUpdate = Omit<Project, "id" | "status" | "created_at" | "updated_at">;
export type ProjectDeletion = { project_id: number; deleted: Record<string, number> };

export type RoadmapNode = {
  id: number | null;
  code: string;
  title: string;
  description: string;
  stage: string;
  est_hours: number;
  difficulty: number;
  prerequisites: string[];
  mastery: number;
  status: string;
};

export type ProjectRoadmap = {
  project_id: number;
  summary: string;
  stages: Record<string, unknown>[];
  nodes: RoadmapNode[];
};

export type WorkspaceNode = {
  id: number;
  code: string;
  title: string;
  description: string;
  stage: string;
  status: string;
  mastery: number;
  est_hours: number;
  difficulty: number;
  has_content: boolean;
  learnable: boolean;
  resources: Array<{ id: number | null; title: string }>;
};

export type NodeDetail = Omit<WorkspaceNode, "learnable" | "resources"> & {
  practice: { id: number | null; title: string; description: string; status: string } | null;
  note: { id: number | null; content: string; selection: string; updated_at: string } | null;
  resources: Array<{ id: number | null; title: string; url: string; rtype: string; description: string; preview: string; source: string }>;
};

export type NodeOperation = { node_id: number; project_id: number; status: string; detail: NodeDetail; resource_count?: number | null; error?: string | null };

export type ProjectWorkspace = {
  project: {
    id: number;
    title: string;
    topic: string;
    background: string;
    goal: string;
    weekly_hours: number;
    status: string;
    created_at: string;
    updated_at: string;
  };
  progress: Progress;
  environment: { description: string; status: string };
  nodes: WorkspaceNode[];
};

export type NodeStatusUpdate = {
  node: { id: number; status: string };
  workspace: ProjectWorkspace;
};

export type RoadmapPreview = {
  roadmap: Omit<ProjectRoadmap, "project_id">;
  audit: { score?: number; verdict?: string; problems?: string[]; changes?: string[] };
};

export type ProjectCreation = {
  project_id: number;
  title: string;
  node_count: number;
  environment_status: string;
  environment_error: string | null;
};

export type ContentPreparation = {
  job_id: number;
  project_id: number;
  generated_node_ids: number[];
  failed_node_ids: number[];
  pending_node_ids: number[];
  status: string;
  attempts: number;
  error: string | null;
  cancel_requested: boolean;
};

export type ReviewCard = {
  id: number;
  node_id: number | null;
  project_id: number | null;
  front: string;
  back: string;
  card_type: string;
  state: number;
  reps: number;
  next_review: string;
};

export type DueCards = { cards: ReviewCard[]; project_id: number | null };
export type ReviewSubmission = { card: ReviewCard; next_card: ReviewCard | null };

export type QuizQuestion = { id: number; node_id: number | null; qtype: string; stem: string; options: string[]; difficulty: number };
export type QuizGeneration = { quiz_id: number; project_id: number; title: string; quiz_type: string; questions: QuizQuestion[] };
export type QuizAnswer = { attempt_id: number; question_id: number; node_id: number | null; is_correct: boolean; feedback: string; mastery: number | null };
export type Dashboard = { project_id: number | null; projects: Array<{ label: string; id: number }>; metrics: { total_nodes: number; mastered_nodes: number; avg_mastery: number; week_minutes: number; due_cards: number; total_cards: number }; status_counts: Record<string, number>; heatmap: Array<{ date: string; minutes: number }>; latest_report: string };
export type RagExcerpt = { source_id: string; text: string; score: number | null; metadata: Record<string, unknown> };
export type RagStreamEvent = { kind: "evidence" | "answer_delta" | "citation" | "complete" | "error"; text: string | null; excerpts: RagExcerpt[]; metadata: Record<string, unknown> };
export type ModelEndpoint = { active_profile_id: string | null; active_profile_name: string | null; base_url: string; model: string; api_key_configured: boolean; ready: boolean };
export type ModelProfile = { id: string; name: string; base_url: string; model: string; api_key_configured: boolean };
export type ModelConfiguration = { llm: ModelEndpoint; rag: ModelEndpoint; llm_profiles: ModelProfile[]; rag_profiles: ModelProfile[] };
export type ModelEndpointInput = { name: string; base_url: string; api_key: string; model: string };
export type ModelConnectivity = { ok: boolean; message: string };
export type IndexedResource = { resource_id: number; node_id: number; title: string; rtype: string; source: string; status: string; message: string | null; collection_id: string | null; source_id: string | null };
export type ResourceDeletionPreview = { resource: IndexedResource; confirmation_phrase: string; index_delete_required: boolean };
export type ResourceUploadEvent = { kind: "started" | "progress" | "completed" | "failed"; resource_id: number; node_id: number; collection_id: string; message: string | null; source_id: string | null };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const apiBase = process.env.NEXT_PUBLIC_LEARNING_API_BASE ?? "/api/v1";

export function apiUrl(path: string): string {
  return `${apiBase}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.detail ?? `请求失败 (${response.status})`,
      response.headers.get("x-request-id"),
    );
  }
  return body as T;
}

export const listProjects = () => request<ProjectSummary[]>("/projects");
export const getProject = (projectId: number) => request<Project>(`/projects/${projectId}`);
export const updateProject = (projectId: number, payload: ProjectUpdate) => request<Project>(`/projects/${projectId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteProject = (projectId: number, confirmation_phrase: string) => request<ProjectDeletion>(`/projects/${projectId}`, { method: "DELETE", body: JSON.stringify({ confirmation_phrase }) });
export const getProjectRoadmap = (projectId: number) => request<ProjectRoadmap>(`/projects/${projectId}/roadmap`);
export const getProjectWorkspace = (projectId: number) => request<ProjectWorkspace>(`/projects/${projectId}/workspace`);
export const updateNodeStatus = (nodeId: number, status: string) => request<NodeStatusUpdate>(`/nodes/${nodeId}/status`, {
  method: "PATCH",
  body: JSON.stringify({ status }),
});
export const previewRoadmap = (payload: { topic: string; background: string; goal: string; weekly_hours: number }) => request<RoadmapPreview>("/roadmaps/preview", {
  method: "POST",
  body: JSON.stringify(payload),
});
export const refineRoadmap = (roadmap: RoadmapPreview["roadmap"], instruction: string) => request<{ roadmap: RoadmapPreview["roadmap"] }>("/roadmaps/refine", {
  method: "POST",
  body: JSON.stringify({ roadmap, instruction }),
});
export const createProject = (payload: {
  topic: string;
  background: string;
  goal: string;
  weekly_hours: number;
  roadmap: RoadmapPreview["roadmap"];
}) => request<ProjectCreation>("/projects", { method: "POST", body: JSON.stringify(payload) });
export const prepareProjectContent = (projectId: number) => request<ContentPreparation>(`/projects/${projectId}/content-preparation`, {
  method: "POST",
  body: JSON.stringify({ initial_count: 3 }),
});
export const getContentPreparation = (projectId: number, jobId: number) => request<ContentPreparation>(`/projects/${projectId}/content-preparation/${jobId}`);
export const cancelContentPreparation = (projectId: number, jobId: number) => request<ContentPreparation>(`/projects/${projectId}/content-preparation/${jobId}/cancel`, { method: "POST" });
export const retryContentPreparation = (projectId: number, jobId: number) => request<ContentPreparation>(`/projects/${projectId}/content-preparation/${jobId}/retry`, { method: "POST" });
export const getNodeDetail = (nodeId: number) => request<NodeDetail>(`/nodes/${nodeId}`);
export const generateNodeContent = (nodeId: number, force = false) => request<NodeOperation>(`/nodes/${nodeId}/content`, { method: "POST", body: JSON.stringify({ force }) });
export const generatePracticeLesson = (nodeId: number) => request<NodeOperation>(`/nodes/${nodeId}/practice`, { method: "POST", body: JSON.stringify({ force: true }) });
export const generateNodeResources = (nodeId: number) => request<NodeOperation>(`/nodes/${nodeId}/resources`, { method: "POST" });
export const saveNodeNote = (nodeId: number, content: string) => request<{ node_id: number; project_id: number; note: NodeDetail["note"]; detail: NodeDetail }>(`/nodes/${nodeId}/note`, { method: "PUT", body: JSON.stringify({ content }) });
export const getDueCards = (projectId: number) => request<DueCards>(`/reviews/due?project_id=${projectId}&limit=1`);
export const submitReview = (cardId: number, rating: number, projectId: number) => request<ReviewSubmission>(`/reviews/${cardId}`, { method: "POST", body: JSON.stringify({ rating, project_id: projectId }) });
export const generateQuiz = (projectId: number, payload: { node_ids: number[]; count: number; qtype: string }) => request<QuizGeneration>(`/projects/${projectId}/quizzes`, { method: "POST", body: JSON.stringify(payload) });
export const submitQuizAnswer = (projectId: number, questionId: number, answer: string) => request<QuizAnswer>(`/projects/${projectId}/quizzes/questions/${questionId}/answer`, { method: "POST", body: JSON.stringify({ answer }) });
export const getDashboard = (projectId: number) => request<Dashboard>(`/projects/${projectId}/dashboard`);
export const getModelConfiguration = () => request<ModelConfiguration>("/model-configuration");
export const createModelProfile = (kind: "llm" | "rag", name: string) => request<ModelConfiguration>(`/model-configuration/${kind}/profiles`, { method: "POST", body: JSON.stringify({ name }) });
export const saveModelProfile = (kind: "llm" | "rag", profileId: string, payload: ModelEndpointInput) => request<ModelConfiguration>(`/model-configuration/${kind}/profiles/${profileId}`, { method: "PUT", body: JSON.stringify(payload) });
export const activateModelProfile = (kind: "llm" | "rag", profileId: string) => request<ModelConfiguration>(`/model-configuration/${kind}/profiles/${profileId}/activate`, { method: "POST" });
export const deleteModelProfile = (kind: "llm" | "rag", profileId: string) => request<ModelConfiguration>(`/model-configuration/${kind}/profiles/${profileId}`, { method: "DELETE" });
export const testModelProfile = (kind: "llm" | "rag", payload: ModelEndpointInput, profileId?: string) => request<ModelConnectivity>(`/model-configuration/${kind}/test${profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ""}`, { method: "POST", body: JSON.stringify(payload) });
export const listNodeResources = (nodeId: number) => request<IndexedResource[]>(`/nodes/${nodeId}/resources`);
export const getResourceDeletionPreview = (nodeId: number, resourceId: number) => request<ResourceDeletionPreview>(`/nodes/${nodeId}/resources/${resourceId}/deletion-preview`);
export const deleteNodeResource = (nodeId: number, resourceId: number, confirmation_phrase: string) => request<{ resource_id: number; index_deleted: boolean }>(`/nodes/${nodeId}/resources/${resourceId}`, { method: "DELETE", body: JSON.stringify({ confirmation_phrase }) });

export async function streamRagChat(
  payload: { collection_id: string; conversation_id: string; message: string; history: Array<{ role: "user" | "assistant"; content: string }>; file_ids: string[] },
  signal: AbortSignal,
  onEvent: (event: RagStreamEvent) => void,
) {
  const response = await fetch(apiUrl("/rag/stream"), {
    method: "POST",
    signal,
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail ?? "无法建立知识问答连接");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    let separator = buffer.indexOf("\n\n");
    while (separator >= 0) {
      const frame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const kind = frame.match(/^event:\s*(.+)$/m)?.[1];
      const data = frame.match(/^data:\s*(.+)$/m)?.[1];
      if (kind && data) onEvent({ kind: kind as RagStreamEvent["kind"], ...JSON.parse(data) });
      separator = buffer.indexOf("\n\n");
    }
    if (done) return;
  }
}

export async function streamResourceUpload(nodeId: number, file: File, onEvent: (event: ResourceUploadEvent) => void) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(apiUrl(`/nodes/${nodeId}/resources/upload/stream`), { method: "POST", headers: { accept: "text/event-stream" }, body: form });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail ?? "无法上传资料");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    let separator = buffer.indexOf("\n\n");
    while (separator >= 0) {
      const frame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const kind = frame.match(/^event:\s*(.+)$/m)?.[1];
      const data = frame.match(/^data:\s*(.+)$/m)?.[1];
      if (kind && data) onEvent({ kind: kind as ResourceUploadEvent["kind"], ...JSON.parse(data) });
      separator = buffer.indexOf("\n\n");
    }
    if (done) return;
  }
}
