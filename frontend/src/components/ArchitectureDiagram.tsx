// BARA – Architecture diagram component
import type { Architecture, Issue } from "../types";

interface Props {
  architecture: Architecture;
  issues: Issue[];
  onIssueClick?: (issue: Issue) => void;
}

const NODE_ICONS: Record<string, string> = {
  frontend_component: "🖥️",
  backend_endpoint: "⚙️",
  service: "🔧",
  database: "🗄️",
  missing_endpoint: "❌",
};

export function ArchitectureDiagram({ architecture, issues, onIssueClick }: Props) {
  const { nodes, edges } = architecture;

  const frontendNodes = nodes.filter((n) => n.kind === "frontend_component");
  const backendNodes = nodes.filter(
    (n) => n.kind === "backend_endpoint" || n.kind === "missing_endpoint"
  );

  const issuePathSet = new Set(
    issues.flatMap((i) => [
      i.frontend_location?.file ?? "",
      i.backend_location?.file ?? "",
    ])
  );

  const edgeMap = new Map<string, typeof edges[0][]>();
  for (const e of edges) {
    if (!edgeMap.has(e.source)) edgeMap.set(e.source, []);
    edgeMap.get(e.source)!.push(e);
  }

  if (nodes.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">🏗️</div>
        <h3>No architecture detected</h3>
        <p>No frontend or backend components were found.</p>
      </div>
    );
  }

  return (
    <div className="arch-diagram">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 80px 1fr",
          gap: "0",
          alignItems: "start",
        }}
      >
        {/* Frontend column */}
        <div>
          <div
            style={{
              fontSize: 11,
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: ".08em",
              marginBottom: 12,
            }}
          >
            Frontend
          </div>
          <div className="arch-layer">
            {frontendNodes.map((node) => {
              const hasIssue = issuePathSet.has(node.source_file ?? "");
              return (
                <div
                  key={node.id}
                  className={`arch-node ${hasIssue ? "has-issue" : ""}`}
                >
                  <span className="node-icon">{NODE_ICONS[node.kind] ?? "📄"}</span>
                  <div>
                    <div className="node-label">{node.label}</div>
                  </div>
                </div>
              );
            })}
            {frontendNodes.length === 0 && (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                No frontend detected
              </div>
            )}
          </div>
        </div>

        {/* Arrow column */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            paddingTop: 36,
            gap: 4,
          }}
        >
          {edges.map((e, i) => (
            <div key={i} className="arch-connector">
              <div className={`arch-arrow ${e.has_issue ? "issue" : ""}`}>→</div>
              <div
                className="arch-edge-label"
                style={{ color: e.has_issue ? "var(--red)" : undefined }}
              >
                {e.label}
              </div>
            </div>
          ))}
          {edges.length === 0 && (
            <div className="arch-arrow">→</div>
          )}
        </div>

        {/* Backend column */}
        <div>
          <div
            style={{
              fontSize: 11,
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: ".08em",
              marginBottom: 12,
            }}
          >
            Backend Endpoints
          </div>
          <div className="arch-layer">
            {backendNodes.map((node) => {
              const isMissing = node.kind === "missing_endpoint";
              const relatedIssues = issues.filter(
                (i) =>
                  i.backend_location?.file === node.source_file ||
                  (isMissing &&
                    (node.details as { path?: string }).path &&
                    i.actual === "(not found)")
              );
              return (
                <div
                  key={node.id}
                  className={`arch-node ${isMissing ? "missing" : ""} ${
                    relatedIssues.length > 0 ? "has-issue clickable" : ""
                  }`}
                  onClick={() =>
                    relatedIssues.length > 0 && onIssueClick?.(relatedIssues[0])
                  }
                  title={
                    relatedIssues.length > 0
                      ? "Click to view issue"
                      : undefined
                  }
                >
                  <span className="node-icon">{NODE_ICONS[node.kind] ?? "⚙️"}</span>
                  <div>
                    <div className="node-label">{node.label}</div>
                    {node.source_file && (
                      <div className="node-sub">{node.source_file}</div>
                    )}
                  </div>
                </div>
              );
            })}
            {backendNodes.length === 0 && (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                No backend detected
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
