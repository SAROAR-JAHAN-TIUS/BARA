// BARA Frontend – shared TypeScript types

export interface ScannedFile {
  path: string;
  language: string;
  file_type: string;
  category?: string;
}

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
  calling_context?: string;
  framework?: string;
  confidence?: "high" | "medium" | "low" | string;
  evidence?: string;
  is_external?: boolean;
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
  controller?: string;
  framework?: string;
  confidence?: "high" | "medium" | "low" | string;
  evidence?: string;
}

export interface ArchNode {
  id: string;
  kind:
    | "PROJECT"
    | "FRONTEND"
    | "FRONTEND_FILE"
    | "API_CLIENT"
    | "API_REQUEST"
    | "BACKEND"
    | "ROUTE"
    | "CONTROLLER"
    | "SERVICE"
    | "DATABASE"
    | "EXTERNAL_API"
    | "WEBSOCKET"
    | "GRAPHQL"
    | "AUTHENTICATION"
    | "CONFIGURATION"
    | "repository"
    | "frontend_page"
    | "frontend_component"
    | "frontend_service"
    | "api_call"
    | "backend_endpoint"
    | "backend_controller"
    | "backend_service"
    | "database"
    | "external_api"
    | "missing_endpoint";
  label: string;
  source_file?: string;
  details: Record<string, unknown>;
}

export interface ArchEdge {
  source: string;
  target: string;
  label: string;
  relation?: string;
  status?: "matched" | "mismatch" | "unhandled" | "external" | string;
  has_issue: boolean;
}

export interface Architecture {
  nodes: ArchNode[];
  edges: ArchEdge[];
  explanation?: string;
}

export interface ApiConnection {
  id: string;
  frontend_call?: ApiCall;
  backend_endpoint?: ApiEndpoint;
  caller_location?: string;
  route_handler?: string;
  service?: string;
  database?: string;
  protocol: "http" | "websocket" | "graphql" | string;
  status:
    | "MATCHED"
    | "MISSING_BACKEND_ENDPOINT"
    | "METHOD_MISMATCH"
    | "FIELD_MISMATCH"
    | "QUERY_PARAM_MISMATCH"
    | "PATH_PARAMETER_MISMATCH"
    | "CONTENT_TYPE_MISMATCH"
    | "AUTH_HEADER_MISMATCH"
    | "UNUSED_BACKEND_ENDPOINT"
    | "EXTERNAL"
    | "UNKNOWN_BACKEND"
    | string;
  resolved_path: string;
  method: string;
  issues: Issue[];
  line_number_frontend?: number;
  line_number_backend?: number;
}

export interface RepositoryTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  role?: string;
  language?: string;
  children?: RepositoryTreeNode[];
}

export interface Summary {
  total_frontend_calls: number;
  total_backend_endpoints: number;
  total_issues: number;
  matched_apis?: number;
  mismatched_apis?: number;
  external_apis?: number;
  architecture_nodes_count?: number;
  architecture_edges_count?: number;
  frontend_files_scanned: number;
  backend_files_scanned: number;
  project_type?: string;
  detected_technologies?: string[];
  backend_framework?: string;
  backend_status?: string;
  monorepo_packages?: string[];
  issues_by_type: Record<string, number>;
  issues_by_severity: { high: number; medium: number; low: number };
}

export interface AnalysisResult {
  analysis_id: string;
  source_type: "local" | "github";
  source: string;
  project_name: string;
  github_url?: string;
  project_type?: string;
  backend_framework?: string;
  backend_status?: string;
  detected_technologies?: string[];
  scanned_files?: ScannedFile[];
  frontend_calls: ApiCall[];
  backend_endpoints: ApiEndpoint[];
  issues: Issue[];
  architecture: Architecture;
  api_connections?: ApiConnection[];
  repository_tree?: RepositoryTreeNode;
  base_urls?: Record<string, string>;
  database_services?: Record<string, unknown>[];
  summary: Summary;
}
