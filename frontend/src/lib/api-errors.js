// FastAPI validation errors use an array; HTTPException details may be any JSON.
// Return display text without mutating the error or exposing validation input.
export function getApiErrorMessage(error, fallback = "Não foi possível concluir a operação.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail.trim() || fallback;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => {
      if (!item || typeof item.msg !== "string" || !item.msg.trim()) return [];
      const location = Array.isArray(item.loc)
        ? item.loc.filter(part =>
            (typeof part === "string" || typeof part === "number") &&
            !["body", "query", "path", "header", "cookie"].includes(part)
          ).join(".")
        : "";
      return [location ? `${location}: ${item.msg.trim()}` : item.msg.trim()];
    });
    return [...new Set(messages)].join("; ") || fallback;
  }
  if (detail && typeof detail.message === "string") {
    return detail.message.trim() || fallback;
  }
  return fallback;
}
