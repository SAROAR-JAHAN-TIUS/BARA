// BARA – Issues list component
import { useState } from "react";
import type { Issue, Summary } from "../types";
import { IssueDetail } from "./IssueDetail";

const ISSUE_TYPE_LABELS: Record<string, string> = {
  MISSING_BACKEND_ENDPOINT: "Missing Backend Endpoint",
  METHOD_MISMATCH: "HTTP Method Mismatch",
  REQUEST_FIELD_MISMATCH: "Request Field Mismatch",
  RESPONSE_FIELD_MISMATCH: "Response Field Mismatch",
  QUERY_PARAM_MISMATCH: "Query Parameter Mismatch",
  PATH_MISMATCH: "API Path Mismatch",
};

interface Props {
  issues: Issue[];
  summary?: Summary;
  selectedIssue?: Issue | null;
  onSelect?: (issue: Issue) => void;
}

export function IssueList({ issues, summary, selectedIssue, onSelect }: Props) {
  const [localSelected, setLocalSelected] = useState<Issue | null>(null);

  const selected = selectedIssue !== undefined ? selectedIssue : localSelected;
  const handleSelect = (issue: Issue) => {
    setLocalSelected(issue);
    onSelect?.(issue);
  };

  if (issues.length === 0) {
    if (
      summary &&
      summary.frontend_files_scanned === 0 &&
      summary.backend_files_scanned === 0
    ) {
      return (
        <div className="empty-state">
          <div className="icon">📂</div>
          <h3>No Supported Source Files Detected</h3>
          <p>
            BARA did not find any JavaScript/TypeScript frontend files (<code>.js</code>, <code>.jsx</code>, <code>.ts</code>, <code>.tsx</code>)
            or Python backend files (<code>.py</code>) in this project.
          </p>
          <div style={{ marginTop: 12, fontSize: 13, color: "var(--muted)" }}>
            Make sure the project contains supported full-stack source files.
          </div>
        </div>
      );
    }

    if (
      summary &&
      summary.total_frontend_calls === 0 &&
      summary.total_backend_endpoints === 0
    ) {
      return (
        <div className="empty-state">
          <div className="icon">🔍</div>
          <h3>No API Calls or Endpoints Found</h3>
          <p>
            Scanned {summary.frontend_files_scanned} frontend file(s) and {summary.backend_files_scanned} backend file(s),
            but no frontend API calls (fetch/axios) or backend FastAPI routes (@app.get/post/...) were detected.
          </p>
        </div>
      );
    }

    return (
      <div className="empty-state">
        <div className="icon">✅</div>
        <h3>No Integration Issues Detected</h3>
        <p>
          BARA analyzed {summary?.total_frontend_calls ?? 0} frontend API call(s) and{" "}
          {summary?.total_backend_endpoints ?? 0} backend endpoint(s). All detected contracts match successfully!
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="issues-list">
        {issues.map((issue, i) => {
          const label = ISSUE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type;
          const path =
            issue.frontend_location?.file
              ? `${issue.frontend_location.file}:${issue.frontend_location.line}`
              : issue.actual ?? "";
          const isSelected = selected === issue;
          return (
            <div
              key={i}
              className={`issue-card ${isSelected ? "selected" : ""}`}
              onClick={() => handleSelect(issue)}
            >
              <div className="issue-card-header">
                <span className={`badge badge-${issue.severity}`}>
                  {issue.severity.toUpperCase()}
                </span>
                <span className="issue-type">{issue.issue_type}</span>
              </div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
              {path && <div className="issue-path">{path}</div>}
              <div
                style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}
              >
                {issue.explanation.slice(0, 120)}
                {issue.explanation.length > 120 ? "…" : ""}
              </div>
            </div>
          );
        })}
      </div>

      {selected && (
        <IssueDetail issue={selected} />
      )}
    </div>
  );
}
