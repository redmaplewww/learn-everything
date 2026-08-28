"use client";

import { AlertCircle, KeyRound, LoaderCircle, Save, Wifi } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getModelConfiguration,
  saveModelConfiguration,
  testModelConfiguration,
  type ModelConfiguration,
  type ModelConfigurationInput,
} from "../../lib/api";

type State = "loading" | "ready" | "saving" | "testing" | "error";

const emptyForm: ModelConfigurationInput = {
  base_url: "https://api.openai.com/v1",
  api_key: "",
  chat_model: "gpt-4o-mini",
  embedding_model: "",
};

export function ModelConfigurationPanel() {
  const [form, setForm] = useState<ModelConfigurationInput>(emptyForm);
  const [status, setStatus] = useState<ModelConfiguration | null>(null);
  const [state, setState] = useState<State>("loading");
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    setMessage(null);
    try {
      const current = await getModelConfiguration();
      setStatus(current);
      setForm((value) => ({ ...value, base_url: current.base_url, chat_model: current.chat_model, embedding_model: current.embedding_model }));
      setState("ready");
    } catch (error) {
      setState("error");
      setMessage(error instanceof ApiError ? error.message : "无法读取模型配置状态");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const update = (field: keyof ModelConfigurationInput, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };
  const runTest = async () => {
    setState("testing"); setMessage(null);
    try { setMessage((await testModelConfiguration(form)).message); setState("ready"); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : "模型连接失败"); setState("error"); }
  };
  const save = async () => {
    setState("saving"); setMessage(null);
    try { setStatus(await saveModelConfiguration(form)); setForm((current) => ({ ...current, api_key: "" })); setMessage("配置已保存，密钥不会再次显示。"); setState("ready"); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : "保存模型配置失败"); setState("error"); }
  };
  const busy = state === "saving" || state === "testing";

  return <section className="model-config-panel">
    <div className="section-heading"><div><p className="eyebrow">MODEL CONFIGURATION</p><h3>模型配置</h3></div><KeyRound size={22} aria-hidden="true" /></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在读取配置状态</div>}
    {state !== "loading" && <div className="model-config-form">
      <label>接口地址<input value={form.base_url} onChange={(event) => update("base_url", event.target.value)} placeholder="https://api.example.com/v1" disabled={busy} /></label>
      <label>对话模型<input value={form.chat_model} onChange={(event) => update("chat_model", event.target.value)} placeholder="模型名称" disabled={busy} /></label>
      <label>向量模型（资料库可选）<input value={form.embedding_model} onChange={(event) => update("embedding_model", event.target.value)} placeholder="向量模型名称" disabled={busy} /></label>
      <label>API Key<input type="password" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} placeholder={status?.api_key_configured ? "已配置，填写新值才会替换" : "输入 API Key"} autoComplete="off" disabled={busy} /></label>
      <div className="model-config-state"><span className={status?.chat_ready ? "ready" : "missing"}>对话 {status?.chat_ready ? "已就绪" : "未配置"}</span><span className={status?.rag_ready ? "ready" : "missing"}>资料问答 {status?.rag_ready ? "已就绪" : "需向量模型"}</span></div>
      <div className="model-config-actions"><button type="button" className="secondary-button" onClick={() => void runTest()} disabled={busy || !form.api_key.trim()}><Wifi size={16} />测试连接</button><button type="button" className="command-button" onClick={() => void save()} disabled={busy || !form.api_key.trim()}><Save size={16} />保存配置</button></div>
    </div>}
    {message && <div className={state === "error" ? "model-config-message error" : "model-config-message"}><AlertCircle size={17} />{message}</div>}
  </section>;
}
