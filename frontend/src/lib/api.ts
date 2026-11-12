/**
 * API client for DocuMind AI backend.
 * Local mode — no Authorization headers needed.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Fetch wrapper for authenticated API calls.
 * In local mode, no Authorization header is sent.
 */
export async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const url = endpoint.startsWith("http") ? endpoint : `${API_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `API error: ${response.status} ${response.statusText}`
    );
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
  const url = `${API_URL}/documents/${documentId}`;
  const response = await fetch(url, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete document: ${response.statusText}`);
  }
}

export async function uploadFileWithAuth(endpointOrFile: string | File, maybeFile?: File): Promise<any> {
  const file = maybeFile || (endpointOrFile as File);
  const endpoint = typeof endpointOrFile === "string" ? endpointOrFile : "/documents/upload";
  const url = `${API_URL}${endpoint}`;
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(url, {
    method: "POST",
    body: formData,
    // No Content-Type header — browser sets it with boundary for multipart
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

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const url = `${API_URL}/chat/conversations/${conversationId}`;
  const response = await fetch(url, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete conversation: ${response.statusText}`);
  }
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
  nameOrPayload: string | { name: string; parent_id?: string },
  parentId?: string
): Promise<any> {
  return {};
}

export async function deleteFolder(_folderId: string): Promise<void> {}

export async function getFolderTree(): Promise<any[]> {
  return [];
}
