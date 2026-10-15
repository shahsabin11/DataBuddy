export type HealthResponse = {
  status: string;
  version: string;
  service: string;
};

export type MeResponse = {
  user_id: string;
  email: string;
  institution_id: string | null;
  role: string;
  status: string;
};

export type InstitutionRow = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  domains: string[];
  allowed_entra_tenant_ids: string[];
  user_token_budget_usd: string | null;
  institution_token_budget_usd: string | null;
  enforce_institution_budget: boolean;
};

export type AccessRequestRow = {
  id: string;
  user_id: string;
  email: string;
  email_domain: string;
  institution_id: string | null;
  status: string;
  message: string | null;
  created_at: string;
};

export type InstitutionUsage = {
  institution_id: string;
  active_members: number;
  totals: {
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
    estimated_cost_usd: string;
    events: number;
  };
  by_user: Array<{
    user_id: string;
    estimated_cost_usd: string;
    input_tokens: number;
    output_tokens: number;
    events: number;
  }>;
};

/** Same-origin call; Next.js rewrites /api/* to FastAPI. */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Health check failed (${response.status})`);
  }
  return response.json() as Promise<HealthResponse>;
}

export async function fetchMe(): Promise<MeResponse | null> {
  const response = await fetch("/api/auth/me", {
    cache: "no-store",
    credentials: "include",
  });
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(`Session check failed (${response.status})`);
  }
  return response.json() as Promise<MeResponse>;
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

export async function submitAccessRequest(message: string): Promise<void> {
  const response = await fetch("/api/auth/access-request", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error(`Access request failed (${response.status})`);
  }
}

export async function fetchInstitutions(): Promise<InstitutionRow[]> {
  const response = await fetch("/api/platform/institutions", {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Institutions failed (${response.status})`);
  }
  return response.json() as Promise<InstitutionRow[]>;
}

export async function createInstitution(body: {
  name: string;
  slug: string;
  domains: string[];
  user_token_budget_usd: string;
  institution_token_budget_usd: string;
  enforce_institution_budget: boolean;
  allowed_entra_tenant_ids: string[];
}): Promise<{ id: string; slug: string }> {
  const response = await fetch("/api/platform/institutions", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Create failed (${response.status})`);
  }
  return response.json() as Promise<{ id: string; slug: string }>;
}

export async function fetchAccessRequests(
  status = "pending",
): Promise<AccessRequestRow[]> {
  const response = await fetch(
    `/api/platform/access-requests?status_filter=${encodeURIComponent(status)}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(`Access requests failed (${response.status})`);
  }
  return response.json() as Promise<AccessRequestRow[]>;
}

export async function approveAccessRequest(
  requestId: string,
  institutionId: string,
  role = "student",
): Promise<void> {
  const response = await fetch(
    `/api/platform/access-requests/${requestId}/approve`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ institution_id: institutionId, role }),
    },
  );
  if (!response.ok) {
    throw new Error(`Approve failed (${response.status})`);
  }
}

export async function rejectAccessRequest(requestId: string): Promise<void> {
  const response = await fetch(
    `/api/platform/access-requests/${requestId}/reject`,
    { method: "POST", credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(`Reject failed (${response.status})`);
  }
}

export async function fetchInstitutionUsage(): Promise<InstitutionUsage> {
  const response = await fetch("/api/institution/usage", {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Usage failed (${response.status})`);
  }
  return response.json() as Promise<InstitutionUsage>;
}

export type DatasetRow = {
  id: string;
  project_id: string;
  name: string;
  original_filename: string;
  status: string;
  current_version_id: string | null;
  version_number: number | null;
  storage_key: string | null;
  byte_size: number | null;
  row_count: number | null;
  column_count: number | null;
};

export type ApiErrorBody = {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string };
};

export function formatApiError(status: number, body: unknown): string {
  if (body && typeof body === "object") {
    const err = body as ApiErrorBody;
    if (typeof err.detail === "object" && err.detail?.message) {
      return err.detail.message;
    }
    if (typeof err.detail === "string") return err.detail;
    if (err.message) return err.message;
  }
  if (status === 413) return "File exceeds the 500 MB upload limit.";
  if (status === 401) return "Please sign in again, then retry the upload.";
  if (status === 403) return "You don't have access to upload to this project.";
  if (status === 500 || status === 502) {
    return "Upload failed on the server. Try again in a moment.";
  }
  return `Upload failed (${status})`;
}

export async function fetchDatasets(): Promise<DatasetRow[]> {
  const response = await fetch("/api/datasets", {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Datasets failed (${response.status})`);
  }
  return response.json() as Promise<DatasetRow[]>;
}

/** XHR upload so we can report progress (fetch has no upload progress). */
export function uploadDataset(
  file: File,
  options?: {
    projectId?: string;
    name?: string;
    onProgress?: (pct: number) => void;
  },
): Promise<DatasetRow> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/datasets");
    xhr.withCredentials = true;
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !options?.onProgress) return;
      options.onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText) as unknown;
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DatasetRow);
        return;
      }
      reject(new Error(formatApiError(xhr.status, body)));
    };
    xhr.onerror = () => reject(new Error("Network error during upload."));
    const form = new FormData();
    form.append("file", file);
    if (options?.projectId) form.append("project_id", options.projectId);
    if (options?.name) form.append("name", options.name);
    xhr.send(form);
  });
}

export async function deleteDataset(datasetId: string): Promise<void> {
  const response = await fetch(`/api/datasets/${datasetId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Delete failed (${response.status})`);
  }
}

export type TeacherProject = {
  id: string;
  title: string;
  description: string | null;
  owner_user_id?: string;
  member_count: number;
  pending_invites: number;
  created_at: string;
};

export type TeacherProjectDetail = {
  id: string;
  title: string;
  description: string | null;
  members: Array<{
    user_id: string;
    email: string;
    display_name: string | null;
    source: string;
  }>;
  invites: Array<{
    id: string;
    email: string;
    status: string;
    invite_url: string;
    created_at: string;
    accepted_at: string | null;
  }>;
};

export type InviteResult = {
  email: string;
  status: string;
  invite_url?: string;
  email_delivery?: string | null;
  error?: string;
};

export type PublicInvite = {
  token: string;
  email: string;
  status: string;
  project_title: string;
  teacher_name: string;
};

export async function fetchTeacherProjects(): Promise<TeacherProject[]> {
  const response = await fetch("/api/teacher/projects", {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Projects failed (${response.status})`);
  }
  return response.json() as Promise<TeacherProject[]>;
}

export async function createTeacherProject(body: {
  title: string;
  description?: string;
}): Promise<{ id: string; title: string }> {
  const response = await fetch("/api/teacher/projects", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Create project failed (${response.status})`);
  }
  return response.json() as Promise<{ id: string; title: string }>;
}

export async function fetchTeacherProject(
  projectId: string,
): Promise<TeacherProjectDetail> {
  const response = await fetch(`/api/teacher/projects/${projectId}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Project failed (${response.status})`);
  }
  return response.json() as Promise<TeacherProjectDetail>;
}

export async function inviteStudentsToProject(
  projectId: string,
  emails: string[],
): Promise<{
  smtp_configured: boolean;
  invites: InviteResult[];
}> {
  const response = await fetch(`/api/teacher/projects/${projectId}/invites`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ emails }),
  });
  if (!response.ok) {
    throw new Error(`Invite failed (${response.status})`);
  }
  return response.json() as Promise<{
    smtp_configured: boolean;
    invites: InviteResult[];
  }>;
}

export async function fetchPublicInvite(token: string): Promise<PublicInvite> {
  const response = await fetch(`/api/invites/${token}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Invite not found (${response.status})`);
  }
  return response.json() as Promise<PublicInvite>;
}
