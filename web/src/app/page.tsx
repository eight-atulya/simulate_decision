"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface Job {
  id: string;
  concept: string;
  status: string;
  iterations: number;
  created_at: string;
  progress?: {
    current_stage: string;
    status: string;
    elapsed_seconds: number;
  };
}

interface Stats {
  total: number;
  pending: number;
  running: number;
  success: number;
  failed: number;
}

interface JobResult {
  status: string;
  iterations: number;
  purified_atoms: string;
  blueprint: string;
  strategy_history: string[];
  completed_at: string;
  metadata?: {
    final_output?: Record<string, Record<string, any>>;
    pipeline_name?: string;
    stages_executed?: string[];
    converged?: boolean;
  };
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatCommand {
  cmd: string;
  label: string;
  instruction: string;
}

export default function Home() {
  const [concept, setConcept] = useState("");
  const [iterations, setIterations] = useState(3);
  const [pipeline, setPipeline] = useState("standard");
  const [analysisMode, setAnalysisMode] = useState<"standard" | "story">("standard");
  const [storyTemplate, setStoryTemplate] = useState("user_story");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, pending: 0, running: 0, success: 0, failed: 0 });
  const [loading, setLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState(true);
  
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [jobResult, setJobResult] = useState<JobResult | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [chatSystemPrompt, setChatSystemPrompt] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const chatCommands: ChatCommand[] = [
    { cmd: "/first-principles", label: "First Principles", instruction: "Analyze this using first principles reasoning. Break down to fundamental truths and build up from there." },
    { cmd: "/flaws", label: "Find Flaws", instruction: "Critically analyze and identify any logical flaws, assumptions, or weaknesses in this argument." },
    { cmd: "/argue", label: "Solid Argument", instruction: "Build a strong, logical argument for this position. Use evidence and sound reasoning." },
    { cmd: "/simplify", label: "Simplify", instruction: "Simplify this concept to its core essence. Explain in simple terms anyone can understand." },
    { cmd: "/deep", label: "Deep Analysis", instruction: "Provide a deep, thorough analysis covering all angles, implications, and nuances." },
  ];

  const handleChatCommand = (cmd: ChatCommand) => {
    setChatSystemPrompt(cmd.instruction);
    setChatInput(cmd.instruction);
  };

  const sendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    const systemPrompt = chatSystemPrompt;
    setChatInput("");
    setChatSystemPrompt(null);
    setChatMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setChatLoading(true);

    try {
      const history = chatMessages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      
      const response = await fetch("http://localhost:8000/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: userMessage, 
          history,
          systemPrompt: systemPrompt || undefined
        })
      });

      if (!response.ok) throw new Error("Chat failed");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value);
          const lines = text.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.content) {
                  assistantMessage += data.content;
                  setChatMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last?.role === "assistant") {
                      return [...prev.slice(0, -1), { ...last, content: assistantMessage }];
                    }
                    return [...prev, { role: "assistant", content: assistantMessage }];
                  });
                }
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Chat error:", err);
    } finally {
      setChatLoading(false);
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(label);
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      setCopyFeedback('Failed');
      setTimeout(() => setCopyFeedback(null), 2000);
    }
  };

  const generateHTML = (job: Job, result: JobResult) => {
    const record = {
      timestamp: job.created_at,
      concept: job.concept,
      status: result.status.toUpperCase(),
      iterations: result.iterations,
      purified_atoms: result.purified_atoms,
      blueprint: result.blueprint,
      error: null,
      strategy_history: result.strategy_history || []
    };
    
    // Build atoms list HTML
    let atomsHtml = '';
    if (record.purified_atoms) {
      const atoms = record.purified_atoms.split(',').map(a => a.trim()).filter(Boolean);
      atomsHtml = atoms.map(a => '<div class="list-item">' + a + '</div>').join('');
    } else {
      atomsHtml = '<div class="list-item">No atoms available</div>';
    }
    
    // Build blueprint HTML
    let blueprintHtml = '';
    if (record.blueprint) {
      blueprintHtml = record.blueprint
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\*\s(.+)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>');
      blueprintHtml = '<p>' + blueprintHtml + '</p>';
    } else {
      blueprintHtml = '<p>No blueprint generated</p>';
    }
    
    const html = '<!DOCTYPE html>' +
'<html lang="en">' +
'<head>' +
'  <meta charset="UTF-8" />' +
'  <meta name="viewport" content="width=device-width, initial-scale=1.0" />' +
'  <title>SimulateDecision Dashboard</title>' +
'  <style>' +
'    :root { --bg: #0a0a0c; --panel: #121318; --panel-2: #181a21; --text: #f5f7fb; --muted: #9ea6b5; --line: rgba(255,255,255,0.08); --accent: #ff3b30; --good: #22c55e; }' +
'    * { box-sizing: border-box; } html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: Arial, sans-serif; } body { min-height: 100vh; }' +
'    .wrap { max-width: 1200px; margin: 0 auto; padding: 2rem; }' +
'    .hero { display: grid; grid-template-columns: 1.5fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }' +
'    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 1.5rem; }' +
'    h1 { font-size: 1.5rem; margin: 0 0 0.5rem; } h2 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }' +
'    p { color: var(--muted); line-height: 1.6; }' +
'    .stat { background: var(--panel-2); padding: 1rem; border-radius: 12px; text-align: center; }' +
'    .stat .label { font-size: 0.75rem; color: var(--muted); }' +
'    .stat .value { font-size: 1.75rem; font-weight: 700; }' +
'    .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 2rem; }' +
'    .list { display: grid; gap: 0.5rem; margin-top: 0.75rem; }' +
'    .list-item { background: var(--panel-2); padding: 0.875rem; border-radius: 8px; font-size: 0.875rem; }' +
'    .list-item small { display: block; color: var(--muted); font-size: 0.7rem; text-transform: uppercase; margin-bottom: 0.25rem; }' +
'    details { border: 1px solid var(--line); border-radius: 12px; background: var(--panel); overflow: hidden; margin-top: 1rem; }' +
'    summary { padding: 1rem; font-weight: 700; cursor: pointer; background: var(--panel-2); }' +
'    .details-body { padding: 1rem; font-size: 0.875rem; line-height: 1.7; }' +
'    .mono { font-family: monospace; font-size: 0.75rem; white-space: pre-wrap; background: var(--panel-2); padding: 1rem; border-radius: 8px; }' +
'    @media (max-width: 768px) { .hero, .stats-grid { grid-template-columns: 1fr; } }' +
'  </style>' +
'</head>' +
'<body>' +
'  <main class="wrap">' +
'    <div class="hero">' +
'      <div class="card">' +
'        <h1>' + record.concept + '</h1>' +
'        <p>Analysis result generated by SimulateDecision - Policy-Driven Autonomous Analysis Engine</p>' +
'        <div class="stats-grid">' +
'          <div class="stat"><div class="label">Status</div><div class="value">' + record.status + '</div></div>' +
'          <div class="stat"><div class="label">Iterations</div><div class="value">' + record.iterations + '</div></div>' +
'        </div>' +
'      </div>' +
'      <div class="card">' +
'        <h2>Core Concept</h2>' +
'        <p>' + (record.purified_atoms ? record.purified_atoms.split(',').slice(0, 3).join(', ') : 'No atoms') + '</p>' +
'      </div>' +
'    </div>' +
'    <div class="card">' +
'      <h2>Purified Atoms</h2>' +
'      <div class="list">' + atomsHtml + '</div>' +
'    </div>' +
'    <div class="card">' +
'      <h2>Blueprint</h2>' +
'      <details open><summary>Technical Implementation</summary><div class="details-body">' + blueprintHtml + '</div></details>' +
'    </div>' +
'    <div class="card">' +
'      <h2>Raw Data</h2>' +
'      <div class="mono">' + JSON.stringify(record, null, 2) + '</div>' +
'    </div>' +
'  </main>' +
'</body>' +
'</html>';
    
    return html;
  };

  const downloadHTML = () => {
    if (!selectedJob || !jobResult) return;
    
    const html = generateHTML(selectedJob, jobResult);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulate-decision-${selectedJob.id.slice(0, 8)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const checkApi = async () => {
    try {
      const res = await fetch("http://localhost:8000/health");
      setApiOnline(res.ok);
    } catch {
      setApiOnline(false);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await fetch("http://localhost:8000/jobs");
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch {}
  };

  const fetchStats = async () => {
    try {
      const res = await fetch("http://localhost:8000/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {}
  };

  const submitAnalysis = async () => {
    if (!concept.trim()) return;
    setLoading(true);
    try {
      if (analysisMode === "story") {
        await fetch("http://localhost:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            concept, 
            iterations, 
            pipeline: storyTemplate 
          }),
        });
      } else {
        await fetch("http://localhost:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ concept, iterations, pipeline }),
        });
      }
      setConcept("");
      fetchJobs();
      fetchStats();
    } finally {
      setLoading(false);
    }
  };

  const deleteJob = async (id: string) => {
    await fetch(`http://localhost:8000/jobs/${id}`, { method: "DELETE" });
    fetchJobs();
    fetchStats();
  };

  const cancelJob = async (id: string) => {
    await fetch(`http://localhost:8000/jobs/${id}/cancel`, { method: "POST" });
    fetchJobs();
    fetchStats();
  };

  const rerunJob = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/jobs/${id}/rerun`, { method: "POST" });
      if (res.ok) {
        const newJob = await res.json();
        fetchJobs();
        fetchStats();
        // Optionally show a success message or navigate to the new job
        alert(`Job rerunning as: ${newJob.id.slice(0, 8)}`);
      } else {
        alert("Failed to rerun job");
      }
    } catch (error) {
      alert("Error rerunning job");
    }
  };

  const viewJobResult = async (job: Job) => {
    setSelectedJob(job);
    setResultLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/results/${job.id}`);
      if (res.ok) {
        const data = await res.json();
        setJobResult(data);
      }
    } catch {
      setJobResult(null);
    } finally {
      setResultLoading(false);
    }
  };

  const closeModal = () => {
    setSelectedJob(null);
    setJobResult(null);
  };

  useEffect(() => {
    checkApi();
    fetchJobs();
    fetchStats();
    const interval = setInterval(() => {
      checkApi();
      fetchJobs();
      fetchStats();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container">
      <header className="header">
        <div className="header-brand">
          <div className="app-icon">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="20" cy="20" r="18" stroke="url(#brainGradient)" strokeWidth="2" fill="none"/>
              <path d="M14 16C14 16 16 12 20 12C24 12 26 16 26 16" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round"/>
              <path d="M20 18V28" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round"/>
              <path d="M17 23L20 28L23 23" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="20" cy="12" r="2" fill="#a78bfa"/>
              <circle cx="14" cy="16" r="2" fill="#6366f1"/>
              <circle cx="26" cy="16" r="2" fill="#6366f1"/>
              <defs>
                <linearGradient id="brainGradient" x1="4" y1="4" x2="36" y2="36">
                  <stop stopColor="#a78bfa"/>
                  <stop offset="1" stopColor="#6366f1"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div>
            <h1 className="title">SimulateDecision</h1>
            <p className="subtitle">Policy-Driven Autonomous Analysis</p>
          </div>
        </div>
        <div className="header-actions">
          <div className={`status-badge ${apiOnline ? 'online' : 'offline'}`}>
            <span className="status-dot"></span>
            {apiOnline ? 'API Online' : 'API Offline'}
          </div>
          <button className="chat-toggle" onClick={() => setChatOpen(!chatOpen)}>
            <span className="chat-toggle-pulse"></span>
            <svg viewBox="0 0 24 24" fill="none" className="chat-toggle-icon">
              <path d="M12 4C7 4 3 7 3 11c0 2.5 1.5 4.5 3 6v3c0 1 1 2 2 2h6c1 0 2-1 2-2v-3c1.5-1.5 3-3.5 3-6 0-4-4-7-9-7z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <path d="M8 9v2M16 9v2M12 13v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="8" cy="10" r="1" fill="currentColor"/>
              <circle cx="16" cy="10" r="1" fill="currentColor"/>
            </svg>
            <span className="chat-toggle-text">AI Chat</span>
          </button>
        </div>
      </header>

      <section className="analyze-section">
        <div className="card">
          <div className="card-header">
            <h2>
              <svg viewBox="0 0 24 24" fill="none" className="section-icon">
                <path d="M13 10V3L4 14h7v7l9-4-9-4z" stroke="url(#analyzeGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <defs>
                  <linearGradient id="analyzeGrad" x1="4" y1="3" x2="20" y2="14">
                    <stop stopColor="#a78bfa"/>
                    <stop offset="1" stopColor="#6366f1"/>
                  </linearGradient>
                </defs>
              </svg>
              Analyze
            </h2>
            <p>AI-powered concept & story analysis</p>
          </div>
          
          {/* Analysis Mode Toggle */}
          <div className="mode-toggle">
            <button
              className={`mode-btn ${analysisMode === "standard" ? "active" : ""}`}
              onClick={() => setAnalysisMode("standard")}
            >
              <span className="mode-icon">🔬</span>
              <span className="mode-label">Concept Analysis</span>
            </button>
            <button
              className={`mode-btn ${analysisMode === "story" ? "active" : ""}`}
              onClick={() => setAnalysisMode("story")}
            >
              <span className="mode-icon">📖</span>
              <span className="mode-label">Story Decomposition</span>
            </button>
          </div>
          
          <div className="form-stack">
            <textarea
              className="input-area"
              placeholder={analysisMode === "story" 
                ? "As a user, I want to... / Our company needs to... / We have a problem where..."
                : "What makes AI conscious and how can it think like a human..."}
              rows={4}
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
            />
            <div className="form-row">
              <div className="input-group">
                <label>Iterations</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={iterations}
                  onChange={(e) => setIterations(Number(e.target.value))}
                />
              </div>
              
              {analysisMode === "standard" ? (
                <div className="input-group">
                  <label>Pipeline</label>
                  <select
                    value={pipeline}
                    onChange={(e) => setPipeline(e.target.value)}
                  >
                    <option value="basic">Basic</option>
                    <option value="standard">Standard</option>
                    <option value="full">Full (with critique)</option>
                    <option value="synthesis">Synthesis</option>
                    <option value="iterative">Iterative</option>
                  </select>
                </div>
              ) : (
                <div className="input-group">
                  <label>Story Template</label>
                  <select
                    value={storyTemplate}
                    onChange={(e) => setStoryTemplate(e.target.value)}
                  >
                    <option value="user_story">User Story → Specs</option>
                    <option value="business_analysis">Business Analysis</option>
                    <option value="technical_story">Technical Decomposition</option>
                    <option value="problem_decomposition">Problem Analysis</option>
                    <option value="decision_framework">Decision Framework</option>
                  </select>
                </div>
              )}
              <button
                className="button-primary"
                onClick={submitAnalysis}
                disabled={loading || !concept.trim()}
              >
                {loading ? (
                  <span className="loading">⟳ Processing...</span>
                ) : (
                  <span>🚀 Start Analysis</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="stats-section">
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Total Jobs</span>
            <span className="stat-value">{stats.total}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Pending</span>
            <span className="stat-value stat-pending">{stats.pending}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Running</span>
            <span className="stat-value stat-running">{stats.running}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Completed</span>
            <span className="stat-value stat-success">{stats.success}</span>
          </div>
        </div>
      </section>

      <section className="jobs-section">
        <div className="card">
          <div className="card-header">
            <h2>📋 Recent Jobs</h2>
            <span className="job-count">{jobs.length} jobs</span>
          </div>
          <div className="jobs-list">
            {jobs.length === 0 ? (
              <div className="empty-state">
                <p>No jobs yet. Submit your first analysis above!</p>
              </div>
            ) : (
              jobs.slice(0, 10).map((job) => (
                <div key={job.id} className="job-item">
                  <div className="job-info">
                    <p className="job-concept">{job.concept}</p>
                    <p className="job-meta">
                      <span className="job-id">#{job.id.slice(0, 8)}</span>
                      <span className="job-iterations">{job.iterations} iterations</span>
                      <span className="job-time">{new Date(job.created_at).toLocaleString()}</span>
                    </p>
                    {job.status === "running" && job.progress && (
                      <div className="job-progress">
                        <span className="progress-stage">{job.progress.current_stage}</span>
                        <span className="progress-time">{Math.floor(job.progress.elapsed_seconds / 60)}m {job.progress.elapsed_seconds % 60}s</span>
                      </div>
                    )}
                  </div>
                  <div className="job-actions">
                    {job.status === "success" && (
                      <button
                        className="button-view"
                        onClick={() => viewJobResult(job)}
                      >
                        👁 View
                      </button>
                    )}
                    <span className={`status-badge-large ${job.status}`}>
                      {job.status}
                    </span>
                    {job.status === "running" && (
                      <button
                        className="button-cancel"
                        onClick={() => cancelJob(job.id)}
                      >
                        ✕ Cancel
                      </button>
                    )}
                    {job.status === "failed" && (
                      <button
                        className="button-rerun"
                        onClick={() => rerunJob(job.id)}
                      >
                        🔄 Rerun
                      </button>
                    )}
                    <button
                      className="button-delete"
                      onClick={() => deleteJob(job.id)}
                    >
                      🗑
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* Modal */}
      {selectedJob && (
        <div 
          className={`modal-overlay ${isFullscreen ? 'fullscreen' : ''}`} 
          onClick={() => isFullscreen ? setIsFullscreen(false) : closeModal()}
        >
          <div 
            className={`modal ${isFullscreen ? 'modal-fullscreen' : ''}`} 
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h2>📊 Analysis Result</h2>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button 
                  className="button-export"
                  onClick={downloadHTML}
                  disabled={!jobResult}
                  title="Download as HTML dashboard"
                >
                  📥 Export
                </button>
                <button 
                  className="button-export"
                  onClick={() => setIsFullscreen(!isFullscreen)}
                  title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                >
                  {isFullscreen ? '⬜ Exit' : '⛶ Full'}
                </button>
                <button className="modal-close" onClick={closeModal}>✕</button>
              </div>
            </div>
            
            <div className="modal-body">
              {resultLoading ? (
                <div className="loading-state">
                  <span className="spinner"></span>
                  <p>Loading results...</p>
                </div>
              ) : jobResult ? (
                <div className="result-content">
                  <div className="result-section">
                    <div className="result-header">
                      <h3>📝 Concept</h3>
                      <span className="status-badge-large success">Completed</span>
                    </div>
                    <p className="result-concept">{selectedJob.concept}</p>
                  </div>
                  
                  <div className="result-grid">
                    <div className="result-stat">
                      <span className="label">Iterations</span>
                      <span className="value">{jobResult.iterations}</span>
                    </div>
                    <div className="result-stat">
                      <span className="label">Status</span>
                      <span className="value success">{jobResult.status}</span>
                    </div>
                    <div className="result-stat">
                      <span className="label">Completed</span>
                      <span className="value">
                        {jobResult.completed_at ? new Date(jobResult.completed_at).toLocaleString() : 'N/A'}
                      </span>
                    </div>
                  </div>
                  
                  <div className="result-section">
                    <div className="result-section-header">
                      <h3>🔬 Purified Atoms</h3>
                      <button 
                        className="copy-button"
                        onClick={() => copyToClipboard(jobResult.purified_atoms || '', 'atoms')}
                      >
                        {copyFeedback === 'atoms' ? '✓ Copied' : '📋 Copy'}
                      </button>
                    </div>
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {jobResult.purified_atoms || 'No atoms generated'}
                      </ReactMarkdown>
                    </div>
                  </div>
                  
                  <div className="result-section">
                    <div className="result-section-header">
                      <h3>🏗️ Blueprint</h3>
                      <button 
                        className="copy-button"
                        onClick={() => copyToClipboard(jobResult.blueprint || '', 'blueprint')}
                      >
                        {copyFeedback === 'blueprint' ? '✓ Copied' : '📋 Copy'}
                      </button>
                    </div>
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {jobResult.blueprint || 'No blueprint generated'}
                      </ReactMarkdown>
                    </div>
                  </div>
                  
                  {jobResult.metadata && (
                    <div className="result-section">
                      <div className="result-section-header">
                        <h3>⚙️ Pipeline Info</h3>
                      </div>
                      <div className="pipeline-info">
                        <div className="info-item">
                          <span className="info-label">Pipeline:</span>
                          <span className="info-value">{jobResult.metadata.pipeline_name || 'N/A'}</span>
                        </div>
                        <div className="info-item">
                          <span className="info-label">Converged:</span>
                          <span className={`info-value ${jobResult.metadata.converged ? 'success' : 'failed'}`}>
                            {jobResult.metadata.converged ? 'Yes' : 'No'}
                          </span>
                        </div>
                        <div className="info-item">
                          <span className="info-label">Stages:</span>
                          <span className="info-value">{jobResult.metadata.stages_executed?.join(', ') || 'N/A'}</span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {jobResult.metadata?.final_output && (
                    <div className="result-section">
                      <div className="result-section-header">
                        <h3>📊 Stage Results</h3>
                      </div>
                      <div className="stages-grid">
                        {Object.entries(jobResult.metadata.final_output).map(([stageName, stageData]) => (
                          <div key={stageName} className="stage-card">
                            <h4>{stageName.replace(/_/g, ' ')}</h4>
                            {Object.entries(stageData).map(([key, value]) => (
                              <div key={key} className="stage-output">
                                <span className="output-key">{key.replace(/_/g, ' ')}:</span>
                                {typeof value === 'string' && value.length > 200 ? (
                                  <details>
                                    <summary>View content</summary>
                                    <div className="output-value">
                                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                        {value}
                                      </ReactMarkdown>
                                    </div>
                                  </details>
                                ) : (
                                  <div className="output-value">
                                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                      {String(value)}
                                    </ReactMarkdown>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state">
                  <p>No results available for this job</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        messages={chatMessages}
        input={chatInput}
        setInput={setChatInput}
        onSubmit={sendChatMessage}
        loading={chatLoading}
        commands={chatCommands}
        activeCommand={chatSystemPrompt ? chatCommands.find(c => c.instruction === chatSystemPrompt)?.cmd || null : null}
        onCommandClick={handleChatCommand}
      />
    </div>
  );
}

function ChatPanel({ 
  open, 
  onClose, 
  messages, 
  input, 
  setInput, 
  onSubmit, 
  loading,
  commands,
  activeCommand,
  onCommandClick 
}: { 
  open: boolean; 
  onClose: () => void;
  messages: ChatMessage[];
  input: string;
  setInput: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  commands?: ChatCommand[];
  activeCommand?: string | null;
  onCommandClick?: (cmd: ChatCommand) => void;
}) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    systemPrompt: "",
    context: "",
    message: ""
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    setFormData(prev => ({ ...prev, message: input }));
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isFullscreen) {
      e.preventDefault();
      onSubmit(e as any);
    }
  };

  const handleCommandSelect = (cmd: ChatCommand) => {
    setFormData(prev => ({ ...prev, systemPrompt: cmd.instruction }));
  };

  const handleSendFromForm = () => {
    const fullMessage = formData.systemPrompt 
      ? `[System: ${formData.systemPrompt}]\n\n[Context: ${formData.context}]\n\n${formData.message}`
      : formData.context 
        ? `[Context: ${formData.context}]\n\n${formData.message}`
        : formData.message;
    
    setInput(fullMessage);
    setIsFullscreen(false);
    onSubmit({ preventDefault: () => {} } as React.FormEvent);
  };

  if (!open) return null;

  if (isFullscreen) {
    return (
      <div className="chat-fullscreen-overlay" onClick={() => setIsFullscreen(false)}>
        <div className="chat-fullscreen-modal form-modal premium-form" onClick={e => e.stopPropagation()}>
          <div className="form-header">
            <div className="form-header-content">
              <div className="form-brand">
                <svg viewBox="0 0 32 32" className="form-brand-icon">
                  <defs>
                    <linearGradient id="formGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#a78bfa"/>
                      <stop offset="100%" stopColor="#6366f1"/>
                    </linearGradient>
                  </defs>
                  <circle cx="16" cy="16" r="14" stroke="url(#formGrad)" strokeWidth="2" fill="none"/>
                  <path d="M10 14C10 14 13 10 16 10C19 10 22 14 22 14" stroke="url(#formGrad)" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M16 15V22" stroke="url(#formGrad)" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M13 19L16 22L19 19" stroke="url(#formGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <div>
                  <h3>Compose Message</h3>
                  <p>Create a detailed request for the AI</p>
                </div>
              </div>
            </div>
            <button className="form-close" onClick={() => setIsFullscreen(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          
          <div className="form-body premium-body">
            <div className="form-grid">
              <div className="form-section primary-field">
                <label className="form-label">
                  <span className="label-icon">
                    <svg viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9z" clipRule="evenodd"/>
                    </svg>
                  </span>
                  Your Message
                  <span className="required">*</span>
                </label>
                <textarea
                  className="form-textarea message-field"
                  placeholder="Describe what you want to accomplish, ask questions, or request analysis..."
                  value={formData.message}
                  onChange={e => setFormData(prev => ({ ...prev, message: e.target.value }))}
                  rows={6}
                  autoFocus
                />
              </div>
              
              <div className="form-sidebar">
                <div className="form-section compact">
                  <label className="form-label">
                    <span className="label-icon">
                      <svg viewBox="0 0 20 20" fill="currentColor">
                        <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"/>
                      </svg>
                    </span>
                    Quick Add
                  </label>
                  <div className="quick-actions">
                    <button 
                      type="button"
                      className="quick-action-btn"
                      onClick={() => setFormData(prev => ({ ...prev, context: prev.context + '\n\n## Previous Context\n' }))}
                      title="Add context section"
                    >
                      <span>📋</span> Add Context
                    </button>
                    <button 
                      type="button"
                      className="quick-action-btn"
                      onClick={() => setFormData(prev => ({ ...prev, context: prev.context + '\n\n## Code\n```\n\n```' }))}
                      title="Add code block"
                    >
                      <span>💻</span> Add Code
                    </button>
                    <button 
                      type="button"
                      className="quick-action-btn"
                      onClick={() => setFormData(prev => ({ ...prev, context: prev.context + '\n\n## Constraints\n- ' }))}
                      title="Add constraints"
                    >
                      <span>⚡</span> Add Constraints
                    </button>
                  </div>
                </div>
                
                <div className="form-section compact">
                  <label className="form-label">
                    <span className="label-icon">
                      <svg viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
                      </svg>
                    </span>
                    AI Mode
                  </label>
                  <div className="mode-selector">
                    {commands?.slice(0, 3).map(cmd => (
                      <button
                        key={cmd.cmd}
                        type="button"
                        className={`mode-btn ${formData.systemPrompt === cmd.instruction ? 'active' : ''}`}
                        onClick={() => handleCommandSelect(cmd)}
                      >
                        {cmd.cmd.replace('/', '')}
                      </button>
                    ))}
                  </div>
                  <select 
                    className="mode-select"
                    value={commands?.find(c => c.instruction === formData.systemPrompt) ? formData.systemPrompt : 'custom'}
                    onChange={e => {
                      if (e.target.value === 'custom') return;
                      const cmd = commands?.find(c => c.cmd === e.target.value);
                      if (cmd) handleCommandSelect(cmd);
                    }}
                  >
                    <option value="custom">More modes...</option>
                    {commands?.map(cmd => (
                      <option key={cmd.cmd} value={cmd.cmd}>{cmd.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            
            <div className="form-section expandable">
              <div className="section-header">
                <label className="form-label">
                  <span className="label-icon">
                    <svg viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M18 13V5a2 2 0 00-2-2H4a2 2 0 00-2 2v8a2 2 0 002 2h3l3 3 3-3h3a2 2 0 002-2zM5 7a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1zm1 3a1 1 0 100 2h3a1 1 0 100-2H6z" clipRule="evenodd"/>
                    </svg>
                  </span>
                  Context
                  <span className="optional">(optional)</span>
                </label>
                <span className="char-count">{formData.context.length} chars</span>
              </div>
              <textarea
                className="form-textarea context-field"
                placeholder="Background information, constraints, examples, or reference material..."
                value={formData.context}
                onChange={e => setFormData(prev => ({ ...prev, context: e.target.value }))}
                rows={4}
              />
            </div>
            
            <div className="form-section expandable">
              <div className="section-header">
                <label className="form-label">
                  <span className="label-icon">
                    <svg viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 10-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                    </svg>
                  </span>
                  System Prompt
                  <span className="optional">(optional)</span>
                </label>
                <button 
                  type="button" 
                  className="expand-toggle"
                  onClick={() => setFormData(prev => ({ ...prev, systemPrompt: prev.systemPrompt ? '' : 'Analyze this using first principles reasoning.' }))}
                >
                  {formData.systemPrompt ? 'Collapse' : 'Expand'}
                </button>
              </div>
              {formData.systemPrompt && (
                <textarea
                  className="form-textarea system-field"
                  placeholder="Define how the AI should behave, what approach to take..."
                  value={formData.systemPrompt}
                  onChange={e => setFormData(prev => ({ ...prev, systemPrompt: e.target.value }))}
                  rows={3}
                />
              )}
            </div>
          </div>
          
          <div className="form-footer">
            <div className="footer-hint">
              <span>💡 Tip:</span> Use context and system prompt for better results
            </div>
            <div className="footer-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsFullscreen(false)}>
                Cancel
              </button>
              <button 
                type="button" 
                className="btn-send" 
                onClick={handleSendFromForm}
                disabled={!formData.message.trim()}
              >
                <svg viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
                </svg>
                Send Message
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-panel-overlay" onClick={onClose}>
      <div className={`chat-panel ${focusMode ? 'focus-mode-panel' : ''}`} onClick={e => e.stopPropagation()}>
        <div className="chat-header">
          <div className="chat-header-title">
            <svg viewBox="0 0 24 24" fill="none" className="chat-header-icon">
              <path d="M12 4C7 4 3 7 3 11c0 2.5 1.5 4.5 3 6v3c0 1 1 2 2 2h6c1 0 2-1 2-2v-3c1.5-1.5 3-3.5 3-6 0-4-4-7-9-7z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <path d="M8 9v2M16 9v2M12 13v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="8" cy="10" r="1" fill="currentColor"/>
              <circle cx="16" cy="10" r="1" fill="currentColor"/>
            </svg>
            <h3>{focusMode ? 'Focus Mode' : 'AI Assistant'}</h3>
          </div>
          <div className="chat-header-actions">
            {!focusMode && (
              <button className="focus-mode-btn" onClick={() => setFocusMode(true)} title="Enter Focus Mode">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 8V4h4M4 16v4h4M20 8V4h-4M20 16v4h-4M8 4H4v4M16 4h4v4M8 20H4v-4M16 20h4v-4"/>
                </svg>
              </button>
            )}
            {focusMode && (
              <button className="focus-mode-exit" onClick={() => setFocusMode(false)} title="Exit Focus Mode">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 14h6v6M20 10h-6V4M4 10l4-4M20 14l-4 4"/>
                </svg>
              </button>
            )}
            <button className="chat-close" onClick={onClose} title="Close Chat">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
        
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="welcome-icon">
                <svg viewBox="0 0 48 48" fill="none">
                  <circle cx="24" cy="24" r="20" stroke="url(#welcomeGrad)" strokeWidth="2" fill="none"/>
                  <path d="M16 22C16 22 20 16 24 16C28 16 32 22 32 22" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M24 24V36" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round"/>
                  <path d="M20 30L24 36L28 30" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <defs>
                    <linearGradient id="welcomeGrad" x1="8" y1="8" x2="40" y2="40">
                      <stop stopColor="#a78bfa"/>
                      <stop offset="1" stopColor="#6366f1"/>
                    </linearGradient>
                  </defs>
                </svg>
              </div>
              <p>Start a conversation</p>
              <span>Use commands below for structured analysis</span>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div key={i} className={`chat-message ${msg.role}`}>
              <div className="message-bubble">
                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="chat-message assistant">
              <div className="message-bubble streaming">
                <span className="streaming-dot"></span>
                <span className="streaming-dot"></span>
                <span className="streaming-dot"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        {commands && commands.length > 0 && (
          <div className="chat-commands">
            {commands.map(cmd => (
              <button
                key={cmd.cmd}
                className={`command-chip ${activeCommand === cmd.cmd ? 'active' : ''}`}
                onClick={() => onCommandClick?.(cmd)}
              >
                {cmd.cmd}
              </button>
            ))}
          </div>
        )}
        
        <div className="chat-input-area">
          <button 
            className="expand-btn" 
            onClick={() => setIsFullscreen(true)}
            title="Open fullscreen editor"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 8V4h4M4 16v4h4M20 8V4h-4M20 16v4h-4"/>
            </svg>
          </button>
          <textarea
            className="chat-input"
            placeholder="Type a message..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={4}
          />
          <button 
            className="chat-send" 
            onClick={() => onSubmit({ preventDefault: () => {} } as React.FormEvent)}
            disabled={loading || !input.trim()}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
