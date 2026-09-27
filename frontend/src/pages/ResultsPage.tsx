// BARA – 7-Tab Analysis Results Page
import { useState } from "react";
import type { AnalysisResult, Issue, ApiConnection } from "../types";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";
import { IssueList } from "../components/IssueList";
import { RepositoryStructureView } from "../components/RepositoryStructureView";

type Tab =
  | "issues"
  | "architecture"
  | "frontend"
  | "backend"
  | "connections"
  | "database"
  | "repository";

interface Props {
  result: AnalysisResult;
  onNewAnalysis: () => void;
}

export function ResultsPage({ result, onNewAnalysis }: Props) {
  const [tab, setTab] = useState<Tab>("issues");
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [connFilter, setConnFilter] = useState<string>("ALL");

  const { summary } = result;

  // Filter connections
  const filteredConnections = (result.api_connections || []).filter((conn: ApiConnection) => {
    if (connFilter === "ALL") return true;
    if (connFilter === "MATCHED") return conn.status === "MATCHED";
    if (connFilter === "MISMATCH")
      return [
        "METHOD_MISMATCH",
        "FIELD_MISMATCH",
        "QUERY_PARAM_MISMATCH",
        "PATH_PARAMETER_MISMATCH",
      ].includes(conn.status);
    if (connFilter === "MISSING") return conn.status === "MISSING_BACKEND_ENDPOINT";
    if (connFilter === "UNUSED") return conn.status === "UNUSED_BACKEND_ENDPOINT";
    if (connFilter === "EXTERNAL") return conn.status === "EXTERNAL";
    if (connFilter === "UNKNOWN_BACKEND") return conn.status === "UNKNOWN_BACKEND";
    return true;
  });

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "MATCHED":
        return "badge-db";
      case "METHOD_MISMATCH":
      case "FIELD_MISMATCH":
      case "QUERY_PARAM_MISMATCH":
      case "PATH_PARAMETER_MISMATCH":
        return "badge-controller";
      case "MISSING_BACKEND_ENDPOINT":
      case "UNKNOWN_BACKEND":
        return "badge-route";
      case "UNUSED_BACKEND_ENDPOINT":
        return "badge-config";
      case "EXTERNAL":
        return "badge-service";
      default:
        return "badge-default";
    }
  };

  return (
    <div className="page">
      {/* Header */}
      <div className="results-header">
        <div>
          <h2>Analysis Results</h2>
          <p>
            {result.source_type === "github" ? (
              <>
                <span style={{ color: "var(--muted)", marginRight: 6 }}>🐙</span>
                <a
                  href={result.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "var(--accent)" }}
                >
                  {result.project_name}
                </a>
              </>
            ) : (
              <>
                <span style={{ color: "var(--muted)", marginRight: 6 }}>📁</span>
                {result.source}
              </>
            )}
          </p>

          {/* Detected Stack & Technologies */}
          <div className="tech-badges">
            {result.project_type && result.project_type !== "unknown" && (
              <span className={`project-type-badge ${result.project_type}`}>
                {result.project_type.replace("-", " ")}
              </span>
            )}
            {result.backend_status && (
              <span
                className={`backend-status-badge ${
                  result.backend_status.includes("Framework detected")
                    ? "detected"
                    : result.backend_status.includes("Unknown")
                    ? "unknown"
                    : "none"
                }`}
              >
                {result.backend_status}
              </span>
            )}
            {result.detected_technologies &&
              result.detected_technologies.map((tech) => (
                <span key={tech} className="tech-pill">
                  {tech}
                </span>
              ))}
          </div>
        </div>
        <button className="btn-ghost" onClick={onNewAnalysis}>
          ← Analyze Another Project
        </button>
      </div>

      {/* Informative notice banner if 0 files or single-stack */}
      {summary.frontend_files_scanned === 0 && summary.backend_files_scanned === 0 && (
        <div className="notice-banner warning">
          <span className="notice-icon">⚠️</span>
          <div>
            <strong>No supported frontend or backend source files were detected.</strong>
            <p>
              BARA scans JavaScript/TypeScript files (<code>.js</code>, <code>.jsx</code>, <code>.ts</code>, <code>.tsx</code>)
              for frontend API calls and Python, Go, Java, Ruby, PHP, C#, or Node.js backend routes.
              This repository does not contain supported full-stack application code.
            </p>
          </div>
        </div>
      )}
      {summary.frontend_files_scanned > 0 && summary.backend_files_scanned === 0 && (
        <div className="notice-banner info">
          <span className="notice-icon">ℹ️</span>
          <div>
            <strong>Frontend files detected, but no backend routes found.</strong>
            <p>
              BARA scanned {summary.frontend_files_scanned} frontend file(s), but found no backend routes.
              Any API calls made by the frontend will show as missing backend endpoints.
            </p>
          </div>
        </div>
      )}
      {summary.backend_files_scanned > 0 && summary.frontend_files_scanned === 0 && (
        <div className="notice-banner info">
          <span className="notice-icon">ℹ️</span>
          <div>
            <strong>Backend routes detected, but no frontend files found.</strong>
            <p>
              BARA scanned {summary.backend_files_scanned} backend file(s), but found no JavaScript/TypeScript frontend files.
            </p>
          </div>
        </div>
      )}

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
          <div className="num" style={{ color: "#48bb78" }}>
            {summary.matched_apis ?? 0}
          </div>
          <div className="label">Matched APIs</div>
        </div>
        <div className="summary-stat">
          <div className="num" style={{ color: "var(--red)" }}>
            {summary.mismatched_apis ?? 0}
          </div>
          <div className="label">Mismatched APIs</div>
        </div>
        <div className="summary-stat">
          <div className="num num-blue">{summary.external_apis ?? 0}</div>
          <div className="label">External APIs</div>
        </div>
        <div className="summary-stat">
          <div className="num num-blue">{summary.total_frontend_calls}</div>
          <div className="label">Frontend Calls</div>
        </div>
        <div className="summary-stat">
          <div className="num num-blue">{summary.total_backend_endpoints}</div>
          <div className="label">Backend Endpoints</div>
        </div>
        <div className="summary-stat">
          <div className="num" style={{ color: "var(--muted)" }}>
            {result.api_connections?.length ?? 0}
          </div>
          <div className="label">Connections</div>
        </div>
      </div>

      {/* 7 Required Tabs */}
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
          Architecture ({result.architecture.nodes.length})
        </button>
        <button
          className={`tab ${tab === "frontend" ? "active" : ""}`}
          onClick={() => setTab("frontend")}
        >
          Frontend ({result.frontend_calls.length})
        </button>
        <button
          className={`tab ${tab === "backend" ? "active" : ""}`}
          onClick={() => setTab("backend")}
        >
          Backend ({result.backend_endpoints.length})
        </button>
        <button
          className={`tab ${tab === "connections" ? "active" : ""}`}
          onClick={() => setTab("connections")}
        >
          API Connections ({result.api_connections?.length ?? 0})
        </button>
        <button
          className={`tab ${tab === "database" ? "active" : ""}`}
          onClick={() => setTab("database")}
        >
          Database / Services ({result.database_services?.length ?? 0})
        </button>
        <button
          className={`tab ${tab === "repository" ? "active" : ""}`}
          onClick={() => setTab("repository")}
        >
          Repository Structure
        </button>
      </div>

      {/* 1. Issues Tab */}
      {tab === "issues" && (
        <IssueList
          issues={result.issues}
          summary={summary}
          selectedIssue={selectedIssue}
          onSelect={setSelectedIssue}
        />
      )}

      {/* 2. Architecture Tab (Animated Interactive Flow Graph) */}
      {tab === "architecture" && (
        <ArchitectureDiagram
          architecture={result.architecture}
          issues={result.issues}
          frontendCalls={result.frontend_calls}
          backendEndpoints={result.backend_endpoints}
          projectType={result.project_type}
          detectedTechnologies={result.detected_technologies}
          backendFramework={result.backend_framework}
          onIssueClick={(issue) => {
            setSelectedIssue(issue);
            setTab("issues");
          }}
        />
      )}

      {/* 3. Frontend Tab */}
      {tab === "frontend" && (
        <div>
          {result.base_urls && Object.keys(result.base_urls).length > 0 && (
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                padding: "12px 16px",
                marginBottom: 16,
              }}
            >
              <strong style={{ fontSize: 13, color: "var(--accent)" }}>
                Resolved Base URLs & Environment Variables:
              </strong>
              <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                {Object.entries(result.base_urls).map(([k, v]) => (
                  <span key={k} className="tech-pill">
                    <code>{k}</code> = <strong>{v}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="ep-list">
            {result.frontend_calls.length === 0 ? (
              <div className="empty-state">
                <div className="icon">🖥️</div>
                <h3>No frontend API calls detected</h3>
              </div>
            ) : (
              result.frontend_calls.map((call, i) => (
                <div
                  key={i}
                  className="ep-item"
                  style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={`method-tag method-${call.method}`}>{call.method}</span>
                      <span className="ep-path">{call.path}</span>
                      {call.calling_context && (
                        <span className="tag-pill frontend">{call.calling_context}</span>
                      )}
                      {call.framework && (
                        <span className="tech-pill">{call.framework}</span>
                      )}
                      {call.confidence && (
                        <span className={`confidence-pill ${call.confidence}`}>{call.confidence}</span>
                      )}
                      {call.is_external && (
                        <span className="status-pill external">External</span>
                      )}
                    </div>
                    <span className="ep-file">
                      {call.source_file}:{call.line_number}
                    </span>
                  </div>

                  {call.query_params.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      Query params: ?{call.query_params.join("&")}
                    </div>
                  )}
                  {call.body_fields.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      Body fields: [{call.body_fields.join(", ")}]
                    </div>
                  )}
                  {call.evidence && (
                    <div className="evidence-snippet">{call.evidence}</div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 4. Backend Tab */}
      {tab === "backend" && (
        <div className="ep-list">
          {result.backend_endpoints.length === 0 ? (
            <div className="empty-state">
              <div className="icon">⚙️</div>
              <h3>No backend endpoints detected</h3>
            </div>
          ) : (
            result.backend_endpoints.map((ep, i) => (
              <div
                key={i}
                className="ep-item"
                style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={`method-tag method-${ep.method}`}>{ep.method}</span>
                    <span className="ep-path">{ep.path}</span>
                    {ep.controller && (
                      <span className="tag-pill backend">{ep.controller}</span>
                    )}
                    {ep.framework && (
                      <span className="tech-pill">{ep.framework}</span>
                    )}
                    {ep.confidence && (
                      <span className={`confidence-pill ${ep.confidence}`}>{ep.confidence}</span>
                    )}
                  </div>
                  <span className="ep-file">
                    {ep.source_file}:{ep.line_number}
                  </span>
                </div>

                {ep.request_fields.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    Request fields: [{ep.request_fields.join(", ")}]
                  </div>
                )}
                {ep.response_fields.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    Response fields: [{ep.response_fields.join(", ")}]
                  </div>
                )}
                {ep.evidence && (
                  <div className="evidence-snippet">{ep.evidence}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* 5. API Connections Tab */}
      {tab === "connections" && (
        <div className="conn-tab-container">
          {/* Filters */}
          <div className="conn-filter-bar">
            {["ALL", "MATCHED", "MISMATCH", "MISSING", "UNUSED", "EXTERNAL", "UNKNOWN_BACKEND"].map(
              (f) => (
                <button
                  key={f}
                  className={`conn-filter-btn ${connFilter === f ? "active" : ""}`}
                  onClick={() => setConnFilter(f)}
                >
                  {f.replace("_", " ")}
                </button>
              )
            )}
          </div>

          <div className="conn-table-card">
            {filteredConnections.length === 0 ? (
              <div className="empty-state">
                <div className="icon">🔌</div>
                <h3>No connections match filter: {connFilter}</h3>
              </div>
            ) : (
              <table className="conn-table">
                <thead>
                  <tr>
                    <th>Protocol</th>
                    <th>Status</th>
                    <th>Method & Path</th>
                    <th>Frontend Caller</th>
                    <th>Backend Handler</th>
                    <th>Issues</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredConnections.map((conn: ApiConnection) => (
                    <tr key={conn.id}>
                      <td>
                        <span className="lang-pill">{conn.protocol.toUpperCase()}</span>
                      </td>
                      <td>
                        <span className={`role-badge ${getStatusBadgeClass(conn.status)}`}>
                          {conn.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span className={`method-tag method-${conn.method}`}>{conn.method}</span>
                          <strong style={{ fontFamily: "monospace", fontSize: 13 }}>
                            {conn.resolved_path}
                          </strong>
                        </div>
                      </td>
                      <td>
                        {conn.caller_location ? (
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>
                            {conn.caller_location}
                          </span>
                        ) : (
                          <span style={{ fontSize: 11, color: "var(--muted)" }}>—</span>
                        )}
                      </td>
                      <td>
                        {conn.route_handler ? (
                          <span style={{ fontSize: 12, color: "var(--accent)" }}>
                            {conn.route_handler}
                          </span>
                        ) : (
                          <span style={{ fontSize: 11, color: "var(--muted)" }}>—</span>
                        )}
                      </td>
                      <td>
                        {conn.issues && conn.issues.length > 0 ? (
                          <button
                            className="role-badge badge-route"
                            style={{ cursor: "pointer", border: "none" }}
                            onClick={() => {
                              setSelectedIssue(conn.issues[0]);
                              setTab("issues");
                            }}
                          >
                            {conn.issues.length} Issue(s)
                          </button>
                        ) : (
                          <span style={{ color: "#48bb78", fontSize: 12 }}>✓ OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* 6. Database / Services Tab */}
      {tab === "database" && (
        <div className="services-container">
          <div className="services-grid">
            {(result.database_services && result.database_services.length > 0) ? (
              result.database_services.map((svc: Record<string, unknown>, idx: number) => (
                <div key={idx} className="service-box">
                  <div className="service-header">
                    <span className="service-name">
                      {svc.type === "database" ? "🗄️" : "🌐"} {String(svc.name)}
                    </span>
                    <span className={`role-badge ${svc.type === "database" ? "badge-db" : "badge-service"}`}>
                      {String(svc.type).toUpperCase()}
                    </span>
                  </div>
                  <div className="service-detail">
                    Status: <strong style={{ color: "var(--text)" }}>{String(svc.status)}</strong>
                  </div>
                  {Boolean(svc.connected_endpoints_count) && (
                    <div className="service-detail">
                      Connected Endpoints: {String(svc.connected_endpoints_count)}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="empty-state" style={{ gridColumn: "1 / -1" }}>
                <div className="icon">🗄️</div>
                <h3>No Database or External Services configured</h3>
                <p>No ORM or 3rd-party SDK markers were detected in configuration or dependency files.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. Repository Structure Tab */}
      {tab === "repository" && (
        <RepositoryStructureView tree={result.repository_tree} />
      )}
    </div>
  );
}
