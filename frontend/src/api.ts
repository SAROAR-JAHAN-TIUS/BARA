// BARA Frontend – API client

import axios from "axios";
import type { AnalysisResult } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

/**
 * Extract canonical https://github.com/<owner>/<repo> from arbitrary GitHub URL.
 * Strips query parameters (?utm_source=...), hash fragments (#readme), .git suffix,
 * and subpaths like /tree/main.
 */
export function normalizeGithubUrl(input: string): string | null {
  try {
    const trimmed = input.trim();
    if (!trimmed.startsWith("https://")) {
      return null;
    }
    const url = new URL(trimmed);
    const host = url.hostname.toLowerCase();
    if (host !== "github.com" && host !== "www.github.com") {
      return null;
    }
    const parts = url.pathname.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
    if (parts.length !== 2) {
      return null;
    }
    const owner = parts[0];
    const repo = parts[1].replace(/\.git$/i, "");
    if (!/^[A-Za-z0-9_.-]+$/.test(owner) || !/^[A-Za-z0-9_.-]+$/.test(repo)) {
      return null;
    }
    return `https://github.com/${owner}/${repo}`;
  } catch {
    return null;
  }
}

/** Return true if the string looks like a public GitHub repository HTTPS URL. */
export function isGithubUrl(input: string): boolean {
  return normalizeGithubUrl(input) !== null;
}

export interface ProjectFile {
  file: File;
  relativePath: string;
}

/**
 * Analyze an uploaded local folder directly from browser folder picker.
 */
export async function analyzeUploadedFolder(
  folderName: string,
  files: ProjectFile[]
): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("folder_name", folderName);
  const paths: string[] = [];

  for (const item of files) {
    formData.append("files", item.file, item.file.name);
    paths.push(item.relativePath);
  }
  formData.append("paths", JSON.stringify(paths));

  const { data } = await client.post<AnalysisResult>("/api/analyze/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    timeout: 120000,
  });
  return data;
}

export async function analyzeProject(
  sourceType: "local" | "github",
  source: string
): Promise<AnalysisResult> {
  let cleanSource = source.trim();
  if (sourceType === "github") {
    const normalized = normalizeGithubUrl(cleanSource);
    if (normalized) {
      cleanSource = normalized;
    }
  }
  const { data } = await client.post<AnalysisResult>("/api/analyze", {
    source_type: sourceType,
    source: cleanSource,
  });
  return data;
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  const { data } = await client.get<AnalysisResult>(`/api/analysis/${analysisId}`);
  return data;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await client.get("/health");
    return true;
  } catch {
    return false;
  }
}
