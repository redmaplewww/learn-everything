"use client";

import { AlertCircle, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { generateQuiz, submitQuizAnswer, type QuizAnswer, type QuizGeneration, type WorkspaceNode } from "../../lib/api";
import { formatError } from "../../lib/errors";

type LoadState = "idle" | "loading" | "ready" | "error";

export function QuizPanel({ projectId, nodes }: { projectId: number; nodes: WorkspaceNode[] }) {
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [count, setCount] = useState(3);
  const [qtype, setQtype] = useState("mixed");
  const [quiz, setQuiz] = useState<QuizGeneration | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<QuizAnswer | null>(null);
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const nodeSelectionKey = nodes.map((node) => node.id).join(",");
  const selectedNode = nodes.find((node) => String(node.id) === selectedNodeId) ?? null;
  useEffect(() => { setSelectedNodeId(""); setQuiz(null); setIndex(0); setFeedback(null); }, [projectId, nodeSelectionKey]);
  const question = quiz?.questions[index] ?? null;
  const generate = async () => {
    if (!selectedNodeId) { setError("请选择一个知识点"); return; }
    setState("loading"); setError(null);
    try { const next = await generateQuiz(projectId, { node_ids: [Number(selectedNodeId)], count, qtype }); setQuiz(next); setIndex(0); setAnswer(""); setFeedback(null); setState("ready"); }
    catch (generationError) { setError(formatError(generationError)); setState("error"); }
  };
  const submit = async () => {
    if (!question || !answer.trim()) { setError("请输入答案后再提交"); return; }
    setState("loading"); setError(null);
    try { setFeedback(await submitQuizAnswer(projectId, question.id, answer)); setState("ready"); }
    catch (submissionError) { setError(formatError(submissionError)); setState("error"); }
  };
  const next = () => { setIndex((value) => value + 1); setAnswer(""); setFeedback(null); setError(null); };
  return <section className="quiz-panel"><div className="section-heading"><div><p className="eyebrow">KNOWLEDGE CHECK</p><h3>查漏测验</h3></div></div>
    <div className="quiz-form"><label>知识点<select value={selectedNodeId} onChange={(event) => setSelectedNodeId(event.target.value)} disabled={!nodes.length || state === "loading"}><option value="">{nodes.length ? "请选择知识点" : "当前项目没有知识点"}</option>{nodes.map((node) => <option value={node.id} key={node.id} title={`${node.code} ${node.title}`}>{node.code} {node.title}</option>)}</select></label>{selectedNode && <p className="quiz-selection-detail" title={selectedNode.title}>已选：{selectedNode.code} {selectedNode.title}</p>}<label>题目数量<input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Number(event.target.value))} /></label><label>题型<select value={qtype} onChange={(event) => setQtype(event.target.value)}><option value="mixed">混合</option><option value="choice">选择</option><option value="fill">填空</option><option value="short">简答</option><option value="practice">实操</option></select></label><button type="button" className="command-button" onClick={() => void generate()} disabled={!nodes.length || state === "loading"}>生成测验</button></div>
    {state === "loading" && <div className="review-state"><LoaderCircle className="spin" size={18} />正在处理测验</div>}
    {error && <div className="review-state detail-error"><AlertCircle size={18} />{error}</div>}
    {question && state !== "loading" && <div className="quiz-question"><span>第 {index + 1} / {quiz?.questions.length} 题 · {question.qtype}</span><strong>{question.stem}</strong>{question.options.map((option) => <button type="button" className={`quiz-option ${answer === option ? "active" : ""}`} key={option} onClick={() => setAnswer(option)}>{option}</button>)}<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="输入你的答案" /><button type="button" className="command-button" onClick={() => void submit()} disabled={Boolean(feedback)}>提交答案</button>{feedback && <div className={feedback.is_correct ? "quiz-feedback correct" : "quiz-feedback incorrect"}><strong>{feedback.is_correct ? "回答正确" : "需要巩固"}</strong><p>{feedback.feedback}</p>{feedback.mastery !== null && <span>当前掌握度 {Math.round(feedback.mastery * 100)}%</span>}{index + 1 < (quiz?.questions.length ?? 0) && <button type="button" className="secondary-button" onClick={next}>下一题</button>}</div>}</div>}
  </section>;
}
