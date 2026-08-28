"use client";

import { AlertCircle, FileUp, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  deleteNodeResource,
  getResourceDeletionPreview,
  listNodeResources,
  streamResourceUpload,
  type IndexedResource,
  type WorkspaceNode,
} from "../../lib/api";

type State = "idle" | "loading" | "uploading" | "deleting" | "error";

export function ResourceLibraryPanel({ nodes }: { nodes: WorkspaceNode[] }) {
  const [nodeId, setNodeId] = useState<number | null>(nodes[0]?.id ?? null);
  const [resources, setResources] = useState<IndexedResource[]>([]);
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<{ id: number; phrase: string; input: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => { setNodeId(nodes[0]?.id ?? null); }, [nodes]);
  const load = useCallback(async () => {
    if (!nodeId) { setResources([]); return; }
    setState("loading"); setMessage(null);
    try { setResources(await listNodeResources(nodeId)); setState("idle"); }
    catch (error) { setState("error"); setMessage(error instanceof ApiError ? error.message : "无法读取资料列表"); }
  }, [nodeId]);
  useEffect(() => { void load(); }, [load]);

  const upload = async () => {
    const file = fileInput.current?.files?.[0];
    if (!nodeId || !file) { setMessage("请选择一个知识点和资料文件"); return; }
    setState("uploading"); setMessage(null); setProgress([]);
    try {
      await streamResourceUpload(nodeId, file, (event) => setProgress((current) => [...current, event.message ?? event.kind]));
      if (fileInput.current) fileInput.current.value = "";
      await load();
    } catch (error) { setState("error"); setMessage(error instanceof ApiError ? error.message : "资料索引失败"); }
  };
  const beginDelete = async (resource: IndexedResource) => {
    if (!nodeId) return;
    try { const preview = await getResourceDeletionPreview(nodeId, resource.resource_id); setDeleting({ id: resource.resource_id, phrase: preview.confirmation_phrase, input: "" }); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : "无法准备删除资料"); }
  };
  const confirmDelete = async () => {
    if (!nodeId || !deleting) return;
    setState("deleting"); setMessage(null);
    try { await deleteNodeResource(nodeId, deleting.id, deleting.input); setDeleting(null); await load(); }
    catch (error) { setState("error"); setMessage(error instanceof ApiError ? error.message : "删除资料失败"); }
  };

  return <section className="resource-library-panel">
    <div className="section-heading"><div><p className="eyebrow">RESOURCE LIBRARY</p><h3>资料库</h3></div><button className="icon-button" type="button" title="刷新资料" onClick={() => void load()} disabled={state === "loading"}><RefreshCw size={17} /></button></div>
    <div className="resource-upload-form"><label>知识点<select value={nodeId ?? ""} onChange={(event) => setNodeId(Number(event.target.value))}>{nodes.map((node) => <option key={node.id} value={node.id}>{node.code} {node.title}</option>)}</select></label><label>本地文件<input ref={fileInput} type="file" accept=".txt,.md,.pdf,.docx,.html" /></label><button type="button" className="command-button" onClick={() => void upload()} disabled={state === "uploading" || !nodeId}><FileUp size={16} />上传并索引</button></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在读取资料</div>}
    {state === "uploading" && <div className="resource-progress">{progress.length ? progress.map((item, index) => <span key={`${item}-${index}`}>{item}</span>) : <span>正在建立索引任务</span>}</div>}
    {message && <div className="resource-error"><AlertCircle size={17} />{message}</div>}
    {resources.length === 0 && state !== "loading" && <div className="rag-empty">当前知识点还没有已上传资料。</div>}
    <div className="resource-list">{resources.map((resource) => <article className={`resource-row ${resource.status}`} key={resource.resource_id}><div><strong>{resource.title}</strong><span>{resource.status === "completed" ? "已索引" : resource.status === "failed" ? "索引失败" : "索引中"} · {resource.rtype}</span>{resource.message && <p>{resource.message}</p>}</div><button type="button" className="icon-button danger" title={`删除 ${resource.title}`} onClick={() => void beginDelete(resource)} disabled={state === "deleting"}><Trash2 size={16} /></button>{deleting?.id === resource.resource_id && <div className="resource-delete-confirm"><span>输入“{deleting.phrase}”确认删除该资料索引。</span><input value={deleting.input} onChange={(event) => setDeleting({ ...deleting, input: event.target.value })} /><button type="button" className="danger-button" onClick={() => void confirmDelete()} disabled={deleting.input !== deleting.phrase || state === "deleting"}>确认删除</button><button type="button" className="secondary-button" onClick={() => setDeleting(null)}>取消</button></div>}</article>)}</div>
  </section>;
}
