// BARA – Issue detail panel component
import type { Issue } from "../types";

const SEVERITY_LABELS: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
  MISSING_BACKEND_ENDPOINT: "Missing Backend Endpoint",
  METHOD_MISMATCH: "HTTP Method Mismatch",
  REQUEST_FIELD_MISMATCH: "Request Field Mismatch",
  RESPONSE_FIELD_MISMATCH: "Response Field Mismatch",
  QUERY_PARAM_MISMATCH: "Query Parameter Mismatch",
  PATH_MISMATCH: "API Path Mismatch",
};

interface Props {
  issue: Issue;
}

export function IssueDetail({ issue }: Props) {
  const label = ISSUE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type;
  const sevClass = `badge badge-${issue.severity}`;

  return (
    <div className="detail-panel">
      <h3>
        {label}{" "}
        <span className={sevClass}>
          {SEVERITY_LABELS[issue.severity] ?? issue.severity}
        </span>
      </h3>

      {/* What happened */}
      <div className="explanation-box">{issue.explanation}</div>

      {/* Expected vs Actual */}
      {(issue.expected || issue.actual) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          {issue.actual && (
            <div className="detail-row">
              <div className="dr-label">Actual (what was sent/used)</div>
              <div className="dr-value mono">{issue.actual}</div>
            </div>
          )}
          {issue.expected && (
            <div className="detail-row">
              <div className="dr-label">Expected (what the other side needs)</div>
              <div className="dr-value mono">{issue.expected}</div>
            </div>
          )}
        </div>
      )}

      {/* Locations */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 14,
        }}
      >
        {issue.frontend_location && (
          <div className="detail-row">
            <div className="dr-label">Frontend location</div>
            <div className="dr-value mono">
              {issue.frontend_location.file}:{issue.frontend_location.line}
            </div>
          </div>
        )}
        {issue.backend_location && (
          <div className="detail-row">
            <div className="dr-label">Backend location</div>
            <div className="dr-value mono">
              {issue.backend_location.file}:{issue.backend_location.line}
            </div>
          </div>
        )}
      </div>

      {/* Fix */}
      <div className="dr-label" style={{ marginBottom: 8 }}>
        💡 Suggested fix
      </div>
      <div className="fix-box">{issue.suggested_fix}</div>
    </div>
  );
}
