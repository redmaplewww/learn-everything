import { ApiError } from "./api";

export function formatError(error: unknown, fallback = "无法连接本地学习服务，请确认 FastAPI 已启动。") {
  if (error instanceof ApiError) {
    return error.requestId ? `${error.message}（请求编号：${error.requestId}）` : error.message;
  }
  return fallback;
}
