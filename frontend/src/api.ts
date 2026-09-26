// BARA Frontend – API client

import axios from "axios";
import type { AnalysisResult } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

export async function analyzeProject(projectPath: string): Promise<AnalysisResult> {
  const { data } = await client.post<AnalysisResult>("/api/analyze", {
    project_path: projectPath,
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
