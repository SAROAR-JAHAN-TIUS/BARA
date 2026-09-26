// BARA – Home / analyze page
import { useState } from "react";
import { analyzeProject } from "../api";
import type { AnalysisResult } from "../types";

interface Props {
  onResult: (result: AnalysisResult) => void;
}

export function HomePage({ onResult }: Props) {
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(projectPath: string) {
    if (!projectPath.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeProject(projectPath.trim());
      onResult(result);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Failed to connect to BARA backend. Is it running?";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="home-hero">
        <h1>
          <span>BARA</span> – Architecture Analyzer
        </h1>
        <p>
          Detect frontend/backend API mismatches, visualize your application
          architecture, and get beginner-friendly explanations of integration
          problems.
        </p>

        <div className="analyze-form">
          <input
            type="text"
            placeholder="Enter absolute path to your project directory…"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze(path)}
            disabled={loading}
          />
          <button
            className="btn-primary"
            onClick={() => handleAnalyze(path)}
            disabled={loading || !path.trim()}
          >
            {loading ? "Analyzing…" : "Analyze →"}
          </button>
        </div>

        <div className="quick-demo">
          <button
            className="btn-ghost"
            onClick={() => handleAnalyze("/home/baby/BARA/examples/demo-project")}
            disabled={loading}
          >
            ▶ Run Demo Project Analysis
          </button>
        </div>

        {loading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span style={{ color: "var(--muted)" }}>
              Scanning project and analyzing API contracts…
            </span>
          </div>
        )}

        {error && (
          <div className="error-box" style={{ maxWidth: 640, margin: "20px auto 0" }}>
            {error}
          </div>
        )}
      </div>

      {/* Feature cards */}
      <div className="features-grid">
        <div className="feature-card">
          <div className="icon">🔍</div>
          <h3>Real Analysis</h3>
          <p>Scans your actual source files — no hardcoded results.</p>
        </div>
        <div className="feature-card">
          <div className="icon">🔗</div>
          <h3>API Contract Check</h3>
          <p>Compares frontend calls against backend endpoints automatically.</p>
        </div>
        <div className="feature-card">
          <div className="icon">⚠️</div>
          <h3>Mismatch Detection</h3>
          <p>Finds path, method, field, and query parameter mismatches.</p>
        </div>
        <div className="feature-card">
          <div className="icon">📖</div>
          <h3>Beginner Friendly</h3>
          <p>Every issue explained in plain language with a concrete fix.</p>
        </div>
        <div className="feature-card">
          <div className="icon">🏗️</div>
          <h3>Architecture View</h3>
          <p>See how your frontend and backend connect at a glance.</p>
        </div>
        <div className="feature-card">
          <div className="icon">⚡</div>
          <h3>Fast & Offline</h3>
          <p>Deterministic static analysis — no AI or external services required.</p>
        </div>
      </div>
    </div>
  );
}
