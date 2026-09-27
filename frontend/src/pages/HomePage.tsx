// BARA – Home / analyze page
import React, { useState, useRef } from "react";
import { analyzeProject, analyzeUploadedFolder, isGithubUrl, type ProjectFile } from "../api";
import type { AnalysisResult } from "../types";

interface Props {
  onResult: (result: AnalysisResult) => void;
}

type SourceType = "local" | "github";
type Status = "idle" | "cloning" | "analyzing" | "error";

interface SelectedFolder {
  name: string;
  files: ProjectFile[];
}

export function HomePage({ onResult }: Props) {
  const [sourceType, setSourceType] = useState<SourceType>("local");
  const [selectedFolder, setSelectedFolder] = useState<SelectedFolder | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const folderInputRef = useRef<HTMLInputElement>(null);
  const loading = status === "cloning" || status === "analyzing";

  function switchSourceType(type: SourceType) {
    if (loading) return;
    setSourceType(type);
    setError(null);
  }

  function handleTriggerFolderPicker() {
    if (loading) return;
    if (folderInputRef.current) {
      folderInputRef.current.value = "";
      folderInputRef.current.click();
    }
  }

  function handleFolderSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const filesArray = Array.from(fileList);
    const samplePath = filesArray[0].webkitRelativePath || filesArray[0].name;
    const folderName = samplePath.split("/")[0] || "project";

    const ignoredDirs = new Set([
      "node_modules",
      ".git",
      "__pycache__",
      ".venv",
      "venv",
      "env",
      "dist",
      "build",
      ".next",
      ".nuxt",
      ".svelte-kit",
      ".idea",
      ".vscode",
      "coverage",
      ".cache",
      ".turbo",
    ]);

    const ignoredExts = new Set([
      "png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "mp4", "mp3", "wav",
      "zip", "tar", "gz", "pdf", "exe", "dll", "so", "dylib", "pyc", "woff",
      "woff2", "ttf", "eot", "lock", "map",
    ]);

    const validFiles: ProjectFile[] = [];

    for (const file of filesArray) {
      const rawRel = file.webkitRelativePath || file.name;
      const segments = rawRel.split("/").filter(Boolean);

      // Skip ignored directories
      const hasIgnoredDir = segments.some((seg) => ignoredDirs.has(seg.toLowerCase()));
      if (hasIgnoredDir) continue;

      // Skip files > 8MB
      if (file.size > 8 * 1024 * 1024) continue;

      const ext = file.name.includes(".") ? file.name.split(".").pop()?.toLowerCase() : "";
      if (ext && ignoredExts.has(ext)) continue;

      let relativePath = rawRel;
      if (segments.length > 1 && segments[0] === folderName) {
        relativePath = segments.slice(1).join("/");
      }

      validFiles.push({ file, relativePath });
    }

    if (validFiles.length === 0) {
      setError("No readable source code files were found in the selected folder.");
      setStatus("error");
      setSelectedFolder(null);
      return;
    }

    setError(null);
    setSelectedFolder({
      name: folderName,
      files: validFiles,
    });
  }

  async function handleAnalyze() {
    setError(null);

    if (sourceType === "local") {
      if (!selectedFolder) return;
      setStatus("analyzing");
    } else {
      const url = githubUrl.trim();
      if (!url) return;
      if (!isGithubUrl(url)) {
        setError("Invalid GitHub URL. Expected format: https://github.com/owner/repo");
        setStatus("error");
        return;
      }
      setStatus("cloning");
    }

    try {
      let result: AnalysisResult;

      if (sourceType === "local" && selectedFolder) {
        result = await analyzeUploadedFolder(selectedFolder.name, selectedFolder.files);
      } else {
        result = await analyzeProject("github", githubUrl.trim());
      }

      // Defensive: ensure summary has required fields
      const defaultSummary = {
        total_frontend_calls: 0,
        total_backend_endpoints: 0,
        total_issues: 0,
        issues_by_type: {},
        issues_by_severity: { high: 0, medium: 0, low: 0 },
        frontend_files_scanned: 0,
        backend_files_scanned: 0,
      };
      const safeSummary = { ...defaultSummary, ...result.summary };
      safeSummary.issues_by_severity = {
        ...defaultSummary.issues_by_severity,
        ...(safeSummary.issues_by_severity ?? {}),
      };

      const safeResult = {
        ...result,
        summary: safeSummary,
        frontend_calls: result.frontend_calls ?? [],
        backend_endpoints: result.backend_endpoints ?? [],
        issues: result.issues ?? [],
        architecture: result.architecture ?? { nodes: [], edges: [] },
      };

      setStatus("idle");
      onResult(safeResult);
    } catch (err: unknown) {
      setStatus("error");
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setError(
        detail ??
          "Failed to connect to BARA backend. Is the backend running on port 8000?"
      );
    }
  }

  function getStatusMessage(): string {
    if (status === "cloning") return "Cloning GitHub repository…";
    if (status === "analyzing") return "Scanning project and analyzing API contracts…";
    return "";
  }

  const isAnalyzeDisabled =
    loading ||
    (sourceType === "local" ? !selectedFolder : !githubUrl.trim());

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

        {/* Source type selector tabs */}
        <div className="source-tabs">
          <button
            className={`source-tab ${sourceType === "local" ? "active" : ""}`}
            onClick={() => switchSourceType("local")}
            disabled={loading}
          >
            📁 Local Project
          </button>
          <button
            className={`source-tab ${sourceType === "github" ? "active" : ""}`}
            onClick={() => switchSourceType("github")}
            disabled={loading}
          >
            🐙 GitHub Repository
          </button>
        </div>

        {/* Local Folder / GitHub Input Box */}
        <div className="source-input-container">
          {sourceType === "local" ? (
            <div className="local-folder-picker-box">
              {/* Native OS directory picker input */}
              <input
                type="file"
                ref={folderInputRef}
                onChange={handleFolderSelected}
                // @ts-expect-error webkitdirectory is standard for folder picking
                webkitdirectory=""
                directory=""
                multiple
                style={{ display: "none" }}
              />

              <button
                type="button"
                className="btn-add-folder"
                onClick={handleTriggerFolderPicker}
                disabled={loading}
              >
                <span className="btn-folder-icon">📁</span>
                <span>{selectedFolder ? "Change Local Folder" : "Add Local Folder"}</span>
              </button>

              <div className="folder-selection-display">
                {selectedFolder ? (
                  <div className="selected-folder-chip">
                    <span className="folder-chip-icon">📂</span>
                    <span className="folder-chip-name">{selectedFolder.name}</span>
                    <span className="folder-chip-meta">
                      ({selectedFolder.files.length} source files ready)
                    </span>
                    <button
                      type="button"
                      className="folder-chip-remove"
                      onClick={() => setSelectedFolder(null)}
                      disabled={loading}
                      title="Remove folder"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="no-folder-text">No folder selected</div>
                )}
              </div>
            </div>
          ) : (
            <div className="github-url-box">
              <input
                type="text"
                placeholder="https://github.com/owner/repository"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                disabled={loading}
                aria-label="GitHub repository URL"
              />
            </div>
          )}

          <button
            className="btn-primary analyze-action-btn"
            onClick={handleAnalyze}
            disabled={isAnalyzeDisabled}
          >
            {loading
              ? "Working…"
              : sourceType === "github"
                ? "Clone & Analyze →"
                : "Analyze →"}
          </button>
        </div>

        {/* Source type hint */}
        {!loading && (
          <div
            style={{
              marginTop: 10,
              fontSize: 13,
              color: "var(--muted)",
              textAlign: "center",
            }}
          >
            {sourceType === "github"
              ? "Repository will be shallow-cloned and analyzed. Previous clones are cleaned up."
              : selectedFolder
                ? `Selected folder "${selectedFolder.name}" with ${selectedFolder.files.length} code files. Ready to analyze.`
                : "Select any local project directory from your computer to analyze."}
          </div>
        )}

        {/* Status indicator */}
        {loading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span style={{ color: "var(--muted)" }}>
              {getStatusMessage()}
            </span>
            {status === "cloning" && (
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Running git clone --depth 1 …
              </span>
            )}
          </div>
        )}

        {/* Error display */}
        {status === "error" && error && (
          <div
            className="error-box"
            style={{ maxWidth: 680, margin: "20px auto 0" }}
            role="alert"
          >
            <strong>Analysis failed</strong>
            <br />
            {error}
            <br />
            <button
              className="btn-ghost"
              style={{ marginTop: 12, fontSize: 12 }}
              onClick={() => {
                setStatus("idle");
                setError(null);
              }}
            >
              Try again
            </button>
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
          <div className="icon">📁</div>
          <h3>Local Projects</h3>
          <p>
            Enter an absolute path on this machine and analyze it directly.
          </p>
        </div>
        <div className="feature-card">
          <div className="icon">🐙</div>
          <h3>Any GitHub Repo</h3>
          <p>
            Paste any public GitHub URL — BARA shallow-clones and analyzes it
            automatically.
          </p>
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
          <div className="icon">⚡</div>
          <h3>Fast & Deterministic</h3>
          <p>Static analysis — no AI, no external services, no code execution.</p>
        </div>
      </div>
    </div>
  );
}
