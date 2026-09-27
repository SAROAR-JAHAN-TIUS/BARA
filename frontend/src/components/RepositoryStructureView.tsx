// BARA – Repository Structure View Component
import React, { useState } from "react";
import type { RepositoryTreeNode } from "../types";

interface Props {
  tree?: RepositoryTreeNode;
}

export function RepositoryStructureView({ tree }: Props) {
  const [filter, setFilter] = useState("");
  const [collapsedPaths, setCollapsedPaths] = useState<Record<string, boolean>>({});

  if (!tree) {
    return (
      <div className="empty-state">
        <div className="icon">📂</div>
        <h3>No repository tree available</h3>
        <p>Run analysis to inspect project structure.</p>
      </div>
    );
  }

  const toggleCollapse = (path: string) => {
    setCollapsedPaths((prev) => ({
      ...prev,
      [path]: !prev[path],
    }));
  };

  const getRoleBadgeClass = (role?: string) => {
    switch (role?.toLowerCase()) {
      case "page":
        return "badge-page";
      case "component":
        return "badge-component";
      case "route":
        return "badge-route";
      case "controller":
        return "badge-controller";
      case "service":
        return "badge-service";
      case "db":
      case "model":
        return "badge-db";
      case "config":
        return "badge-config";
      default:
        return "badge-default";
    }
  };

  const renderNode = (node: RepositoryTreeNode, depth = 0): React.ReactNode => {
    const isDir = node.type === "directory";
    const isCollapsed = Boolean(collapsedPaths[node.path]);

    // Check filter match
    if (filter) {
      const q = filter.toLowerCase();
      const matchesNode =
        node.name.toLowerCase().includes(q) ||
        (node.role && node.role.toLowerCase().includes(q)) ||
        (node.language && node.language.toLowerCase().includes(q));

      // For directories, check if any child matches
      const hasMatchingChild = (n: RepositoryTreeNode): boolean => {
        if (!n.children) return false;
        return n.children.some(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            (c.role && c.role.toLowerCase().includes(q)) ||
            (c.language && c.language.toLowerCase().includes(q)) ||
            hasMatchingChild(c)
        );
      };

      if (!matchesNode && isDir && !hasMatchingChild(node)) {
        return null;
      }
    }

    return (
      <div key={node.path || node.name} style={{ marginLeft: depth * 16 }}>
        <div
          className={`repo-tree-row ${isDir ? "clickable-dir" : ""}`}
          onClick={() => (isDir ? toggleCollapse(node.path) : undefined)}
          style={{
            display: "flex",
            alignItems: "center",
            padding: "4px 8px",
            borderRadius: 4,
            cursor: isDir ? "pointer" : "default",
          }}
        >
          <span style={{ width: 20, textAlign: "center", marginRight: 6 }}>
            {isDir ? (isCollapsed ? "📁" : "📂") : "📄"}
          </span>
          <span style={{ fontWeight: isDir ? 600 : 400, fontFamily: "monospace", fontSize: 13 }}>
            {node.name}
          </span>

          <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
            {node.role && (
              <span className={`role-badge ${getRoleBadgeClass(node.role)}`}>
                {node.role.toUpperCase()}
              </span>
            )}
            {node.language && (
              <span className="lang-pill">{node.language}</span>
            )}
          </div>
        </div>

        {isDir && !isCollapsed && node.children && node.children.length > 0 && (
          <div className="repo-tree-children">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="repo-structure-container">
      <div className="repo-search-bar" style={{ marginBottom: 16 }}>
        <input
          type="text"
          placeholder="Filter files by name, role (page, route, controller, db), or language..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="search-input"
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text)",
          }}
        />
      </div>

      <div
        className="tree-view-panel"
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 12,
          maxHeight: 650,
          overflowY: "auto",
        }}
      >
        {renderNode(tree)}
      </div>
    </div>
  );
}
