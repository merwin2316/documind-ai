/**
 * API client for DocuMind AI backend.
 * Automatically attaches Supabase Auth Bearer access tokens to all requests.
 */
import { supabase } from "@/lib/supabase";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Retrieve current Supabase access token.
 */
export async function getAuthToken(): Promise<string | null> {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      return session.access_token;
    }
  } catch (err) {
    console.warn("Failed to retrieve Supabase session token:", err);
  }
  return null;
}

/**
 * Fetch wrapper for authenticated API calls.
 * Automatically injects the Supabase Bearer token if present.
 */
export async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const url = endpoint.startsWith("http") ? endpoint : `${API_URL}${endpoint}`;
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `API error: ${response.status} ${response.statusText}`
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// ================================================================
// Documents
// ================================================================

export async function listDocuments(skip = 0, limit = 20): Promise<any[]> {
  const data = await fetchWithAuth(`/documents?skip=${skip}&limit=${limit}`);
  return data.documents || [];
}

export async function getDocument(documentId: string): Promise<any> {
  return fetchWithAuth(`/documents/${documentId}`);
}

export async function deleteDocument(documentId: string): Promise<void> {
  await fetchWithAuth(`/documents/${documentId}`, { method: "DELETE" });
}

export async function uploadFileWithAuth(endpointOrFile: string | File, maybeFile?: File): Promise<any> {
  const file = maybeFile || (endpointOrFile as File);
  const endpoint = typeof endpointOrFile === "string" ? endpointOrFile : "/documents/upload";
  const url = `${API_URL}${endpoint}`;
  const formData = new FormData();
  formData.append("file", file);

  const token = await getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
    // Note: Do not set Content-Type header — browser automatically sets boundary for multipart
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
  }

  return response.json();
}

export async function getDocumentUrl(documentId: string): Promise<string> {
  const data = await fetchWithAuth(`/documents/${documentId}/download-url`);
  return data.url;
}

export async function getDocumentDownloadUrl(documentId: string): Promise<string> {
  return getDocumentUrl(documentId);
}

// ================================================================
// Chat
// ================================================================

export async function sendChatMessage(payload: {
  conversation_id: string | null;
  message: string;
  document_ids: string[] | null;
}): Promise<any> {
  return fetchWithAuth("/chat/message", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function sendChatMessageStream(payload: {
  conversation_id: string | null;
  message: string;
  document_ids: string[] | null;
}): Promise<Response> {
  const url = `${API_URL}/chat/stream`;
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Stream error: ${response.statusText}`);
  }

  return response;
}

// ================================================================
// Conversations
// ================================================================

export async function listConversations(
  skip = 0,
  limit = 20
): Promise<any[]> {
  const data = await fetchWithAuth(
    `/chat/conversations?skip=${skip}&limit=${limit}`
  );
  return data.conversations || [];
}

export async function getConversation(conversationId: string): Promise<any> {
  return fetchWithAuth(`/chat/conversations/${conversationId}`);
}

export async function deleteConversation(
  conversationId: string
): Promise<void> {
  await fetchWithAuth(`/chat/conversations/${conversationId}`, { method: "DELETE" });
}

export async function updateConversation(
  conversationId: string,
  data: { title?: string; is_pinned?: boolean }
): Promise<any> {
  return fetchWithAuth(`/chat/conversations/${conversationId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ================================================================
// Folders (stubs — not implemented in backend yet)
// ================================================================

export async function listFolders(): Promise<any[]> {
  return [];
}

export async function createFolder(
  _nameOrPayload: string | { name: string; parent_id?: string },
  _parentId?: string
): Promise<any> {
  return {};
}

export async function deleteFolder(_folderId: string): Promise<void> {}

export async function getFolderTree(): Promise<any[]> {
  return [];
}
