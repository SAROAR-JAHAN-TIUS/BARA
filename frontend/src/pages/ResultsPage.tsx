// BARA – Results page
import { useState } from "react";
import type { AnalysisResult, Issue } from "../types";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";
import { IssueList } from "../components/IssueList";

type Tab = "architecture" | "issues" | "endpoints" | "calls";

interface Props {
  result: AnalysisResult;
  onNewAnalysis: () => void;
}

export function ResultsPage({ result, onNewAnalysis }: Props) {
  const [tab, setTab] = useState<Tab>("issues");
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const { summary } = result;

  return (
    <div className="page">
      {/* Header */}
      <div className="results-header">
        <div>
          <h2>Analysis Results</h2>
          <p>{result.project_path}</p>
        </div>
        <button className="btn-ghost" onClick={onNewAnalysis}>
          ← Analyze Another Project
        </button>
      </div>

      {/* Summary stats */}
      <div className="summary-grid">
        <div className="summary-stat">
          <div className={`num ${summary.total_issues > 0 ? "num-red" : "num-green"}`}>
            {summary.total_issues}
          </div>
          <div className="label">Issues Found</div>
        </div>
        <div className="summary-stat">
          <div className={`num ${summary.issues_by_severity.high > 0 ? "num-red" : "num-green"}`}>
            {summary.issues_by_severity.high}
          </div>
          <div className="label">High Severity</div>
        </div>
        <div className="summary-stat">
          <div className="num num-blue">{summary.total_frontend_calls}</div>
          <div className="label">Frontend API Calls</div>
        </div>
        <div className="summary-stat">
          <div className="num num-blue">{summary.total_backend_endpoints}</div>
          <div className="label">Backend Endpoints</div>
        </div>
        <div className="summary-stat">
          <div className="num" style={{ color: "var(--muted)" }}>
            {summary.frontend_files_scanned}
          </div>
          <div className="label">Frontend Files</div>
        </div>
        <div className="summary-stat">
          <div className="num" style={{ color: "var(--muted)" }}>
            {summary.backend_files_scanned}
          </div>
          <div className="label">Backend Files</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${tab === "issues" ? "active" : ""}`}
          onClick={() => setTab("issues")}
        >
          Issues ({summary.total_issues})
        </button>
        <button
          className={`tab ${tab === "architecture" ? "active" : ""}`}
          onClick={() => setTab("architecture")}
        >
          Architecture
        </button>
        <button
          className={`tab ${tab === "endpoints" ? "active" : ""}`}
          onClick={() => setTab("endpoints")}
        >
          Backend Endpoints ({result.backend_endpoints.length})
        </button>
        <button
          className={`tab ${tab === "calls" ? "active" : ""}`}
          onClick={() => setTab("calls")}
        >
          Frontend Calls ({result.frontend_calls.length})
        </button>
      </div>

      {/* Tab content */}
      {tab === "issues" && (
        <IssueList
          issues={result.issues}
          selectedIssue={selectedIssue}
          onSelect={setSelectedIssue}
        />
      )}

      {tab === "architecture" && (
        <ArchitectureDiagram
          architecture={result.architecture}
          issues={result.issues}
          onIssueClick={(issue) => {
            setSelectedIssue(issue);
            setTab("issues");
          }}
        />
      )}

      {tab === "endpoints" && (
        <div className="ep-list">
          {result.backend_endpoints.length === 0 ? (
            <div className="empty-state">
              <div className="icon">⚙️</div>
              <h3>No backend endpoints detected</h3>
            </div>
          ) : (
            result.backend_endpoints.map((ep, i) => (
              <div key={i} className="ep-item">
                <span className={`method-tag method-${ep.method}`}>{ep.method}</span>
                <span className="ep-path">{ep.path}</span>
                {ep.request_fields.length > 0 && (
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>
                    body: [{ep.request_fields.join(", ")}]
                  </span>
                )}
                <span className="ep-file">
                  {ep.source_file}:{ep.line_number}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "calls" && (
        <div className="ep-list">
          {result.frontend_calls.length === 0 ? (
            <div className="empty-state">
              <div className="icon">🖥️</div>
              <h3>No frontend API calls detected</h3>
            </div>
          ) : (
            result.frontend_calls.map((call, i) => (
              <div key={i} className="ep-item">
                <span className={`method-tag method-${call.method}`}>{call.method}</span>
                <span className="ep-path">{call.path}</span>
                {call.query_params.length > 0 && (
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>
                    ?{call.query_params.join("&")}
                  </span>
                )}
                {call.body_fields.length > 0 && (
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>
                    body: [{call.body_fields.join(", ")}]
                  </span>
                )}
                <span className="ep-file">
                  {call.source_file}:{call.line_number}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
