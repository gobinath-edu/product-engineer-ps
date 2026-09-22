async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  chat: (message) =>
    request("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, subject: "user-001" }),
    }),
  memories: () => request("/api/memories"),
  allMemories: () => request("/api/memories/all"),
  memory: (id) => request(`/api/memories/${id}`),
  history: (id) => request(`/api/memories/${id}/history`),
  deleteMemory: (id) =>
    request(`/api/memories/${id}`, { method: "DELETE" }),
};
