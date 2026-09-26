// BARA Frontend – shared TypeScript types

export interface Location {
  file: string;
  line: number;
}

export interface Issue {
  issue_type: string;
  severity: "high" | "medium" | "low";
  frontend_location?: Location;
  backend_location?: Location;
  expected?: string;
  actual?: string;
  explanation: string;
  suggested_fix: string;
}

export interface ApiCall {
  method: string;
  path: string;
  query_params: string[];
  body_fields: string[];
  response_fields: string[];
  source_file: string;
  line_number: number;
}

export interface ApiEndpoint {
  method: string;
  path: string;
  request_model?: string;
  request_fields: string[];
  response_model?: string;
  response_fields: string[];
  source_file: string;
  line_number: number;
}

export interface ArchNode {
  id: string;
  kind: "frontend_component" | "backend_endpoint" | "service" | "database" | "missing_endpoint";
  label: string;
  source_file?: string;
  details: Record<string, unknown>;
}

export interface ArchEdge {
  source: string;
  target: string;
  label: string;
  has_issue: boolean;
}

export interface Architecture {
  nodes: ArchNode[];
  edges: ArchEdge[];
}

export interface Summary {
  total_frontend_calls: number;
  total_backend_endpoints: number;
  total_issues: number;
  issues_by_type: Record<string, number>;
  issues_by_severity: { high: number; medium: number; low: number };
  frontend_files_scanned: number;
  backend_files_scanned: number;
}

export interface AnalysisResult {
  analysis_id: string;
  project_path: string;
  frontend_calls: ApiCall[];
  backend_endpoints: ApiEndpoint[];
  issues: Issue[];
  architecture: Architecture;
  summary: Summary;
}
