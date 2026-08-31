"use client";

import { AlertCircle, Bot, CheckCircle2, Database, KeyRound, LoaderCircle, Plus, Save, Trash2, Wifi } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  activateModelProfile,
  ApiError,
  createModelProfile,
  deleteModelProfile,
  getModelConfiguration,
  saveModelProfile,
  testModelProfile,
  type ModelConfiguration,
  type ModelEndpointInput,
  type ModelProfile,
} from "../../lib/api";

type Kind = "llm" | "rag";
type State = "loading" | "ready" | "saving" | "testing" | "error";
type TestMessage = { kind: "success" | "error"; text: string } | null;

const emptyForm = (kind: Kind): ModelEndpointInput => ({
  name: kind === "llm" ? "LLM 档案" : "RAG 档案",
  base_url: "https://api.openai.com/v1",
  api_key: "",
  model: kind === "llm" ? "gpt-4o-mini" : "text-embedding-3-small",
});

const toForm = (profile: ModelProfile | undefined, kind: Kind): ModelEndpointInput => profile
  ? { name: profile.name, base_url: profile.base_url, api_key: "", model: profile.model }
  : emptyForm(kind);

export function ModelConfigurationPanel() {
  const [status, setStatus] = useState<ModelConfiguration | null>(null);
  const [llmForm, setLlmForm] = useState<ModelEndpointInput>(emptyForm("llm"));
  const [ragForm, setRagForm] = useState<ModelEndpointInput>(emptyForm("rag"));
  const [newNames, setNewNames] = useState({ llm: "新 LLM 档案", rag: "新 RAG 档案" });
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [testMessages, setTestMessages] = useState<Record<Kind, TestMessage>>({ llm: null, rag: null });

  const applyStatus = useCallback((next: ModelConfiguration) => {
    setStatus(next);
    setLlmForm(toForm(next.llm_profiles.find((profile) => profile.id === next.llm.active_profile_id), "llm"));
    setRagForm(toForm(next.rag_profiles.find((profile) => profile.id === next.rag.active_profile_id), "rag"));
  }, []);

  const load = useCallback(async () => {
    setState("loading");
    setMessage(null);
    try {
      applyStatus(await getModelConfiguration());
      setState("ready");
    } catch (error) {
      setState("error");
      setMessage(error instanceof ApiError ? error.message : "无法读取模型配置状态");
    }
  }, [applyStatus]);

  useEffect(() => { void load(); }, [load]);

  const perform = async (action: () => Promise<ModelConfiguration>, success: string) => {
    setState("saving");
    setMessage(null);
    try {
      applyStatus(await action());
      setMessage(success);
      setState("ready");
    } catch (error) {
      setState("error");
      setMessage(error instanceof ApiError ? error.message : "模型配置操作失败");
    }
  };

  const runTest = async (kind: Kind, form: ModelEndpointInput, profileId: string | null) => {
    setState("testing");
    setMessage(null);
    setTestMessages((messages) => ({ ...messages, [kind]: null }));
    try {
      const result = await testModelProfile(kind, form, profileId ?? undefined);
      setTestMessages((messages) => ({ ...messages, [kind]: { kind: "success", text: result.message } }));
      setState("ready");
    } catch (error) {
      const text = error instanceof ApiError ? error.message : "模型连接失败";
      setTestMessages((messages) => ({ ...messages, [kind]: { kind: "error", text } }));
      setState("error");
    }
  };

  const busy = state === "saving" || state === "testing";

  return <section className="model-config-panel">
    <div className="section-heading"><div><p className="eyebrow">MODEL CONFIGURATION</p><h3>模型配置</h3></div><KeyRound size={22} aria-hidden="true" /></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在读取配置状态</div>}
    {status && <div className="model-config-sections">
      <EndpointConfiguration kind="llm" title="LLM CONFIGURATION" subtitle="LLM 配置" description="用于对话、学习路线、课程和测验。" icon={<Bot size={20} />} endpoint={status.llm} profiles={status.llm_profiles} form={llmForm} newName={newNames.llm} busy={busy} testMessage={testMessages.llm} onFormChange={setLlmForm} onNewNameChange={(value) => setNewNames((names) => ({ ...names, llm: value }))} onCreate={() => perform(() => createModelProfile("llm", newNames.llm), "已新建 LLM 档案，请填写并保存配置。")} onActivate={(profileId) => perform(() => activateModelProfile("llm", profileId), "LLM 档案已切换并应用。")} onSave={() => status.llm.active_profile_id && perform(() => saveModelProfile("llm", status.llm.active_profile_id!, llmForm), "LLM 配置已保存，密钥不会再次显示。")} onDelete={() => status.llm.active_profile_id && perform(() => deleteModelProfile("llm", status.llm.active_profile_id!), "LLM 档案已删除。")} onTest={() => void runTest("llm", llmForm, status.llm.active_profile_id)} />
      <EndpointConfiguration kind="rag" title="RAG EMBEDDING CONFIGURATION" subtitle="RAG 向量模型配置" description="用于资料索引和检索。" icon={<Database size={20} />} endpoint={status.rag} profiles={status.rag_profiles} form={ragForm} newName={newNames.rag} busy={busy} testMessage={testMessages.rag} onFormChange={setRagForm} onNewNameChange={(value) => setNewNames((names) => ({ ...names, rag: value }))} onCreate={() => perform(() => createModelProfile("rag", newNames.rag), "已新建 RAG 档案，请填写并保存配置。")} onActivate={(profileId) => perform(() => activateModelProfile("rag", profileId), "RAG 档案已切换并应用。")} onSave={() => status.rag.active_profile_id && perform(() => saveModelProfile("rag", status.rag.active_profile_id!, ragForm), "RAG 向量模型配置已保存，密钥不会再次显示。")} onDelete={() => status.rag.active_profile_id && perform(() => deleteModelProfile("rag", status.rag.active_profile_id!), "RAG 档案已删除。")} onTest={() => void runTest("rag", ragForm, status.rag.active_profile_id)} />
    </div>}
    {message && <div className={state === "error" ? "model-config-message error" : "model-config-message"}><AlertCircle size={17} />{message}</div>}
  </section>;
}

function EndpointConfiguration({ kind, title, subtitle, description, icon, endpoint, profiles, form, newName, busy, testMessage, onFormChange, onNewNameChange, onCreate, onActivate, onSave, onDelete, onTest }: {
  kind: Kind; title: string; subtitle: string; description: string; icon: ReactNode; endpoint: ModelConfiguration["llm"]; profiles: ModelProfile[]; form: ModelEndpointInput; newName: string; busy: boolean; testMessage: TestMessage; onFormChange: (form: ModelEndpointInput) => void; onNewNameChange: (value: string) => void; onCreate: () => void; onActivate: (profileId: string) => void; onSave: () => void; onDelete: () => void; onTest: () => void;
}) {
  const update = (field: keyof ModelEndpointInput, value: string) => onFormChange({ ...form, [field]: value });
  const canTest = Boolean(form.api_key.trim() || endpoint.api_key_configured);
  return <section className="model-config-section">
    <div className="model-config-section-heading"><div><p className="eyebrow">{title}</p><h4>{subtitle}</h4><p>{description}</p></div>{icon}</div>
    <div className="model-profile-controls">
      <label>活动档案<select value={endpoint.active_profile_id ?? ""} onChange={(event) => onActivate(event.target.value)} disabled={busy || profiles.length === 0}><option value="" disabled>请选择档案</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
      <label>新档案名称<input value={newName} onChange={(event) => onNewNameChange(event.target.value)} disabled={busy} /></label>
      <button type="button" className="secondary-button icon-command" title="新建档案" onClick={onCreate} disabled={busy || !newName.trim()}><Plus size={16} />新建</button>
    </div>
    {endpoint.active_profile_id && <div className="model-config-form">
      <label>档案名称<input value={form.name} onChange={(event) => update("name", event.target.value)} disabled={busy} /></label>
      <label>服务地址<input value={form.base_url} onChange={(event) => update("base_url", event.target.value)} placeholder="https://api.example.com/v1" disabled={busy} />{kind === "rag" && <small className="model-config-hint">请填写基础地址（例如 https://api.example.com/v1），不要包含 /embeddings。</small>}</label>
      <label>{kind === "llm" ? "对话模型" : "向量模型"}<input value={form.model} onChange={(event) => update("model", event.target.value)} placeholder="模型名称" disabled={busy} /></label>
      <label>API Key<input type="password" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} placeholder={endpoint.api_key_configured ? "已配置，填写新值才会替换" : "输入 API Key"} autoComplete="off" disabled={busy} /></label>
      <div className="model-config-state"><span className={endpoint.ready ? "ready" : "missing"}>{subtitle} {endpoint.ready ? "已就绪" : "未配置"}</span></div>
      <div className="model-config-actions"><button type="button" className="secondary-button" onClick={onTest} disabled={busy || !canTest}><Wifi size={16} />测试连接</button><button type="button" className="command-button" onClick={onSave} disabled={busy}><Save size={16} />保存配置</button><button type="button" className="icon-button danger" title="删除当前档案" onClick={onDelete} disabled={busy}><Trash2 size={16} /></button></div>
      {testMessage && <div className={`model-config-message inline ${testMessage.kind === "error" ? "error" : ""}`} role="status">{testMessage.kind === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}{testMessage.text}</div>}
    </div>}
  </section>;
}
