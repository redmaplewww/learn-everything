"use client";

import { AlertCircle, LoaderCircle, MessageSquareText, RotateCcw, Send, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, listNodeResources, streamRagChat, type IndexedResource, type RagExcerpt, type WorkspaceNode } from "../../lib/api";

type Message = { role: "user" | "assistant"; content: string; excerpts?: RagExcerpt[] };

export function RagChatPanel({ nodes }: { nodes: WorkspaceNode[] }) {
  const [nodeId, setNodeId] = useState<number | null>(nodes[0]?.id ?? null);
  const [resources, setResources] = useState<IndexedResource[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const latestQuestion = useRef("");
  const controller = useRef<AbortController | null>(null);

  useEffect(() => { setNodeId(nodes[0]?.id ?? null); }, [nodes]);
  const loadScope = useCallback(async () => {
    if (!nodeId) { setResources([]); setSelectedIds([]); return; }
    setScopeLoading(true); setError(null);
    try {
      const indexed = (await listNodeResources(nodeId)).filter((item) => item.status === "completed" && item.collection_id && item.source_id);
      const collection = indexed[0]?.collection_id;
      const inCollection = indexed.filter((item) => item.collection_id === collection);
      setResources(inCollection);
      setSelectedIds(inCollection.map((item) => item.source_id!));
      setMessages([]);
    } catch (loadError) {
      setResources([]); setSelectedIds([]);
      setError(loadError instanceof ApiError ? loadError.message : "无法读取可问答资料");
    } finally { setScopeLoading(false); }
  }, [nodeId]);
  useEffect(() => { void loadScope(); }, [loadScope]);

  const collectionId = resources[0]?.collection_id ?? "";
  const toggleSource = (sourceId: string) => setSelectedIds((current) => current.includes(sourceId) ? current.filter((id) => id !== sourceId) : [...current, sourceId]);
  const ask = async (retry = false) => {
    const message = (retry ? latestQuestion.current : question).trim();
    if (!message || !collectionId || !selectedIds.length) { setError("请选择至少一份已完成索引的资料后再提问"); return; }
    latestQuestion.current = message;
    setError(null); setRunning(true);
    setMessages((current) => [...current, { role: "user", content: message }, { role: "assistant", content: "" }]);
    controller.current = new AbortController();
    try {
      await streamRagChat({ collection_id: collectionId, conversation_id: crypto.randomUUID(), message, history: messages.map(({ role, content }) => ({ role, content })), file_ids: selectedIds }, controller.current.signal, (event) => {
        if (event.kind === "evidence") setMessages((current) => current.map((item, index) => index === current.length - 1 ? { ...item, excerpts: event.excerpts } : item));
        if (event.kind === "answer_delta") setMessages((current) => current.map((item, index) => index === current.length - 1 ? { ...item, content: `${item.content}${event.text ?? ""}` } : item));
        if (event.kind === "error") setError(event.text ?? "知识问答失败");
      });
      if (!retry) setQuestion("");
    } catch (streamError) {
      if (!(streamError instanceof DOMException && streamError.name === "AbortError")) setError(streamError instanceof ApiError ? streamError.message : "知识问答连接中断");
    } finally { setRunning(false); controller.current = null; }
  };

  return <section className="rag-chat-panel">
    <div className="section-heading"><div><p className="eyebrow">KNOWLEDGE Q&A</p><h3>资料问答</h3></div><MessageSquareText size={22} aria-hidden="true" /></div>
    <div className="rag-scope"><label>知识点<select value={nodeId ?? ""} onChange={(event) => setNodeId(Number(event.target.value))} disabled={running}>{nodes.map((node) => <option value={node.id} key={node.id}>{node.code} {node.title}</option>)}</select></label><div className="rag-source-list"><span>问答资料</span>{scopeLoading && <small><LoaderCircle className="spin" size={14} />正在读取资料</small>}{!scopeLoading && resources.length === 0 && <small>请先在资料库上传并完成索引。</small>}{resources.map((resource) => <label key={resource.source_id}><input type="checkbox" checked={selectedIds.includes(resource.source_id!)} onChange={() => toggleSource(resource.source_id!)} disabled={running} />{resource.title}</label>)}</div></div>
    <div className="rag-transcript" aria-live="polite">{messages.length === 0 && <div className="rag-empty">选择已索引资料后即可提问。</div>}{messages.map((item, index) => <article className={`rag-message ${item.role}`} key={`${item.role}-${index}`}><strong>{item.role === "user" ? "你" : "学习助手"}</strong><p>{item.content || (running && index === messages.length - 1 ? "正在检索资料..." : "")}</p>{item.excerpts?.map((excerpt) => <details key={`${excerpt.source_id}-${excerpt.text}`}><summary>{String(excerpt.metadata.file_name ?? excerpt.source_id)}</summary><p>{excerpt.text}</p></details>)}</article>)}</div>
    {error && <div className="rag-error"><AlertCircle size={17} />{error}{latestQuestion.current && <button type="button" className="text-action" onClick={() => void ask(true)}>重试</button>}</div>}
    <div className="rag-composer"><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="针对已选资料提问" disabled={running} /><div>{running ? <button type="button" className="secondary-button" onClick={() => controller.current?.abort()}><Square size={15} />停止</button> : <button type="button" className="command-button" onClick={() => void ask()} disabled={!resources.length}><Send size={16} />提问</button>}{messages.length > 0 && !running && <button type="button" className="icon-button" title="重试上一问题" onClick={() => void ask(true)}><RotateCcw size={16} /></button>}</div></div>
  </section>;
}
