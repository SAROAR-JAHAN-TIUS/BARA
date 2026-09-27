// BARA – Synchronized Interactive Animated Architecture Graph & Flow Storyteller
import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import type { Architecture, Issue, ApiCall, ApiEndpoint, ArchNode } from "../types";

interface Props {
  architecture: Architecture;
  issues: Issue[];
  frontendCalls?: ApiCall[];
  backendEndpoints?: ApiEndpoint[];
  projectType?: string;
  detectedTechnologies?: string[];
  backendFramework?: string;
  onIssueClick?: (issue: Issue) => void;
}

interface FlowNode {
  id: string;
  tier: number; // 0: Frontend, 1: API Request, 2: Backend Route, 3: Service, 4: Database/External
  label: string;
  sub?: string;
  badge: string;
  badgeType: "frontend" | "api" | "backend" | "service" | "database" | "external" | "missing";
  sourceFile?: string;
  lineNumber?: number;
  evidence?: string;
  controller?: string;
  framework?: string;
  confidence?: string;
  status?: "matched" | "mismatch" | "missing" | "external";
  x: number;
  y: number;
}

interface FlowEdge {
  id: string;
  sourceId: string;
  targetId: string;
  label: string;
  status: "matched" | "mismatch" | "missing" | "external";
  method: string;
  path: string;
  hasIssue: boolean;
  issueDetails?: string;
  evidence?: string;
  feCaller?: string;
  feLine?: number;
  beEndpoint?: string;
  beLine?: number;
}

interface StoryStep {
  stage: "Frontend" | "API Request" | "Backend" | "Service" | "Database" | "Response";
  title: string;
  subtitle: string;
  location?: string;
  description: string;
  activeNodeId: string;
  activeEdgeId?: string;
  direction: "downstream" | "upstream" | "halt";
}

interface ApiFlowItem {
  id: string;
  method: string;
  path: string;
  caller: string;
  status: "matched" | "mismatch" | "missing" | "external";
  call: ApiCall;
  endpoint?: ApiEndpoint;
  nodes: FlowNode[];
  edges: FlowEdge[];
  steps: StoryStep[];
}

const TIER_COLUMNS = [
  { tier: 0, title: "1. Frontend Layer", x: 80, icon: "🖥️" },
  { tier: 1, title: "2. API Request", x: 370, icon: "⚡" },
  { tier: 2, title: "3. Backend Route", x: 660, icon: "⚙️" },
  { tier: 3, title: "4. Backend Service", x: 950, icon: "🔧" },
  { tier: 4, title: "5. Data & External", x: 1240, icon: "🗄️" },
];

const EMPTY_CALLS: ApiCall[] = [];
const EMPTY_ENDPOINTS: ApiEndpoint[] = [];
const EMPTY_TECHS: string[] = [];

export function ArchitectureDiagram({
  architecture,
  issues,
  frontendCalls = EMPTY_CALLS,
  backendEndpoints = EMPTY_ENDPOINTS,
  detectedTechnologies = EMPTY_TECHS,
  onIssueClick,
}: Props) {
  // Mode: "flow" (Interactive Animated Request Flow) or "overview" (Static Architecture)
  const [viewMode, setViewMode] = useState<"flow" | "overview">("flow");

  // Flow playback state
  const [selectedFlowIndex, setSelectedFlowIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [speed, setSpeed] = useState<number>(1);
  const [explainFlow, setExplainFlow] = useState<boolean>(true);
  const [showFlowDropdown, setShowFlowDropdown] = useState<boolean>(false);

  // Inspectors & selection
  const [selectedEdge, setSelectedEdge] = useState<FlowEdge | null>(null);
  const [selectedNode, setSelectedNode] = useState<FlowNode | ArchNode | null>(null);

  // Canvas pan & zoom state
  const [zoom, setZoom] = useState<number>(0.95);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 30, y: 40 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);

  // Overview mode filters
  const [overviewFilter, setOverviewFilter] = useState<"all" | "issues" | "frontend" | "backend">("all");
  const [overviewSearch, setOverviewSearch] = useState<string>("");
  const [overviewSelectedId, setOverviewSelectedId] = useState<string | null>(null);

  // Database technologies detected
  const dbTechs = useMemo(() => {
    return detectedTechnologies.filter((t) =>
      [
        "SQLAlchemy",
        "Prisma",
        "Mongoose",
        "TypeORM",
        "Sequelize",
        "Hibernate",
        "GORM",
        "Entity Framework",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "SQLite",
        "Redis",
      ].includes(t)
    );
  }, [detectedTechnologies]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 1. Build Story-Driven API Flows from Real Analysis Data (No Fabrications)
  // ─────────────────────────────────────────────────────────────────────────────
  const apiFlows = useMemo<ApiFlowItem[]>(() => {
    if (frontendCalls.length > 0) {
      return frontendCalls.map((call, idx) => {
        const callPath = call.path || (call as any).endpoint || "/";
        const callFile = call.source_file || (call as any).caller_file || "Frontend Component";
        const flowId = `flow-${call.method}-${callPath}-${idx}`;
        const callerName =
          call.calling_context || (callFile.includes("/") ? callFile.split("/").pop() : callFile) || "Frontend Component";

        const matchingIssue = issues.find(
          (iss) =>
            iss.frontend_location?.file === callFile &&
            iss.frontend_location?.line === call.line_number
        );

        // Normalize path params for matching
        const cleanCallPath = callPath
          .replace(/:\w+/g, ":param")
          .replace(/\{\w+\}/g, ":param")
          .replace(/\[\w+\]/g, ":param");

        const matchedEp = backendEndpoints.find((ep) => {
          const cleanEpPath = ep.path
            .replace(/:\w+/g, ":param")
            .replace(/\{\w+\}/g, ":param")
            .replace(/\[\w+\]/g, ":param");
          return (
            ep.method.toUpperCase() === call.method.toUpperCase() &&
            (ep.path === call.path || cleanEpPath === cleanCallPath)
          );
        });

        const diffMethodEp = !matchedEp
          ? backendEndpoints.find((ep) => {
              const cleanEpPath = ep.path
                .replace(/:\w+/g, ":param")
                .replace(/\{\w+\}/g, ":param")
                .replace(/\[\w+\]/g, ":param");
              return ep.path === call.path || cleanEpPath === cleanCallPath;
            })
          : undefined;

        let status: "matched" | "mismatch" | "missing" | "external" = "matched";
        if (call.is_external || call.path.startsWith("http://") || call.path.startsWith("https://")) {
          status = "external";
        } else if (matchingIssue || diffMethodEp) {
          status = "mismatch";
        } else if (!matchedEp) {
          status = "missing";
        }

        const nodes: FlowNode[] = [];
        const edges: FlowEdge[] = [];
        const steps: StoryStep[] = [];

        // 1. Frontend Node
        const feId = `node-fe-${idx}`;
        nodes.push({
          id: feId,
          tier: 0,
          label: callerName,
          sub: `${call.source_file}:${call.line_number}`,
          badge: "Frontend",
          badgeType: "frontend",
          sourceFile: call.source_file,
          lineNumber: call.line_number,
          evidence: call.evidence,
          confidence: call.confidence,
          framework: call.framework,
          x: TIER_COLUMNS[0].x,
          y: 220,
        });

        // 2. API Request Node
        const apiId = `node-api-${idx}`;
        nodes.push({
          id: apiId,
          tier: 1,
          label: `${call.method} ${call.path}`,
          sub:
            call.body_fields.length > 0
              ? `body: {${call.body_fields.slice(0, 2).join(", ")}}`
              : "HTTP Request",
          badge: "API Request",
          badgeType: "api",
          sourceFile: call.source_file,
          lineNumber: call.line_number,
          evidence: call.evidence,
          x: TIER_COLUMNS[1].x,
          y: 220,
        });

        // Edge: Frontend ➔ API Request
        const edgeFeApi: FlowEdge = {
          id: `edge-fe-api-${idx}`,
          sourceId: feId,
          targetId: apiId,
          label: `${call.method} ${call.path}`,
          status: "matched",
          method: call.method,
          path: call.path,
          hasIssue: false,
          feCaller: callerName,
          feLine: call.line_number,
          evidence: call.evidence,
        };
        edges.push(edgeFeApi);

        // Story Step 1: Frontend
        steps.push({
          stage: "Frontend",
          title: "Frontend Component",
          subtitle: callerName,
          location: `${call.source_file}:${call.line_number}`,
          description: `The frontend component '${callerName}' triggers the action in ${call.source_file}:${call.line_number}.`,
          activeNodeId: feId,
          activeEdgeId: edgeFeApi.id,
          direction: "downstream",
        });

        // Story Step 2: API Request
        steps.push({
          stage: "API Request",
          title: "API Request Dispatched",
          subtitle: `${call.method} ${call.path}`,
          location: `${call.source_file}:${call.line_number}`,
          description: `The frontend client (${call.framework || "fetch"}) sends a ${call.method} request to '${call.path}' across the network layer.`,
          activeNodeId: apiId,
          activeEdgeId: edgeFeApi.id,
          direction: "downstream",
        });

        if (status === "external") {
          const extId = `node-ext-${idx}`;
          const domain =
            call.path.replace(/^https?:\/\//, "").split("/")[0] || "External Service";
          nodes.push({
            id: extId,
            tier: 4,
            label: `🌐 ${domain}`,
            sub: call.path,
            badge: "External API",
            badgeType: "external",
            status: "external",
            evidence: call.evidence,
            x: TIER_COLUMNS[4].x,
            y: 220,
          });

          const edgeApiExt: FlowEdge = {
            id: `edge-api-ext-${idx}`,
            sourceId: apiId,
            targetId: extId,
            label: `Remote Call`,
            status: "external",
            method: call.method,
            path: call.path,
            hasIssue: false,
            feCaller: callerName,
            feLine: call.line_number,
            evidence: call.evidence,
          };
          edges.push(edgeApiExt);

          steps.push({
            stage: "Database",
            title: "External Service Invocation",
            subtitle: domain,
            description: `The HTTP request is forwarded out-of-process to the remote external API '${call.path}'.`,
            activeNodeId: extId,
            activeEdgeId: edgeApiExt.id,
            direction: "downstream",
          });

          steps.push({
            stage: "Response",
            title: "External Response Received",
            subtitle: `HTTP 200 ➔ ${callerName}`,
            description: `The remote service '${domain}' responds, and data is returned to '${callerName}'.`,
            activeNodeId: feId,
            activeEdgeId: edgeApiExt.id,
            direction: "upstream",
          });
        } else if (status === "missing") {
          const missingId = `node-missing-${idx}`;
          nodes.push({
            id: missingId,
            tier: 2,
            label: `⚠️ ${call.method} ${call.path}`,
            sub: "No matching backend route detected",
            badge: "Missing Route",
            badgeType: "missing",
            status: "missing",
            x: TIER_COLUMNS[2].x,
            y: 220,
          });

          const edgeApiMissing: FlowEdge = {
            id: `edge-api-missing-${idx}`,
            sourceId: apiId,
            targetId: missingId,
            label: `404 Not Found`,
            status: "missing",
            method: call.method,
            path: call.path,
            hasIssue: true,
            issueDetails: `Frontend calls '${call.path}', but no backend route exists to handle it.`,
            feCaller: callerName,
            feLine: call.line_number,
            evidence: call.evidence,
          };
          edges.push(edgeApiMissing);

          steps.push({
            stage: "Backend",
            title: "⚠️ Missing Backend Endpoint",
            subtitle: `${call.method} ${call.path}`,
            description: `No backend route was found for '${call.method} ${call.path}'. The browser or client receives a 404 Not Found error.`,
            activeNodeId: missingId,
            activeEdgeId: edgeApiMissing.id,
            direction: "halt",
          });
        } else if (status === "mismatch") {
          const mismatchId = `node-mismatch-${idx}`;
          const expectedMethod = diffMethodEp
            ? diffMethodEp.method
            : matchingIssue?.expected || "GET";
          nodes.push({
            id: mismatchId,
            tier: 2,
            label: `⚠️ ${expectedMethod} ${call.path}`,
            sub: diffMethodEp
              ? `${diffMethodEp.source_file}:${diffMethodEp.line_number}`
              : "Method Mismatch",
            badge: "Method Mismatch",
            badgeType: "missing",
            status: "mismatch",
            sourceFile: diffMethodEp?.source_file,
            lineNumber: diffMethodEp?.line_number,
            x: TIER_COLUMNS[2].x,
            y: 220,
          });

          const edgeApiMismatch: FlowEdge = {
            id: `edge-api-mismatch-${idx}`,
            sourceId: apiId,
            targetId: mismatchId,
            label: `Mismatch: ${call.method} ≠ ${expectedMethod}`,
            status: "mismatch",
            method: call.method,
            path: call.path,
            hasIssue: true,
            issueDetails:
              matchingIssue?.explanation ||
              `Frontend sends ${call.method}, but backend only accepts ${expectedMethod}.`,
            feCaller: callerName,
            feLine: call.line_number,
            evidence: call.evidence,
          };
          edges.push(edgeApiMismatch);

          steps.push({
            stage: "Backend",
            title: "⚠️ Method Mismatch Detected",
            subtitle: `${call.method} vs ${expectedMethod}`,
            location: diffMethodEp
              ? `${diffMethodEp.source_file}:${diffMethodEp.line_number}`
              : undefined,
            description: `The backend route at '${call.path}' expects ${expectedMethod}, but the frontend sent ${call.method}.`,
            activeNodeId: mismatchId,
            activeEdgeId: edgeApiMismatch.id,
            direction: "halt",
          });
        } else if (matchedEp) {
          // 3. Backend Route Node
          const beId = `node-be-${idx}`;
          nodes.push({
            id: beId,
            tier: 2,
            label: `⚙️ ${matchedEp.method} ${matchedEp.path}`,
            sub: `${matchedEp.source_file}:${matchedEp.line_number}`,
            badge: matchedEp.framework || "Backend Route",
            badgeType: "backend",
            sourceFile: matchedEp.source_file,
            lineNumber: matchedEp.line_number,
            framework: matchedEp.framework,
            controller: matchedEp.controller,
            status: "matched",
            evidence: matchedEp.evidence,
            x: TIER_COLUMNS[2].x,
            y: 220,
          });

          const edgeApiBe: FlowEdge = {
            id: `edge-api-be-${idx}`,
            sourceId: apiId,
            targetId: beId,
            label: `${matchedEp.method} ${matchedEp.path}`,
            status: "matched",
            method: call.method,
            path: call.path,
            hasIssue: false,
            feCaller: callerName,
            feLine: call.line_number,
            beEndpoint: `${matchedEp.method} ${matchedEp.path}`,
            beLine: matchedEp.line_number,
            evidence: matchedEp.evidence,
          };
          edges.push(edgeApiBe);

          // Story Step 3: Backend Route Interception
          steps.push({
            stage: "Backend",
            title: "Backend Route Match",
            subtitle: `${matchedEp.method} ${matchedEp.path}`,
            location: `${matchedEp.source_file}:${matchedEp.line_number}`,
            description: `The backend router (${matchedEp.framework || "Server"}) matches ${matchedEp.method} ${matchedEp.path} in ${matchedEp.source_file}:${matchedEp.line_number}.`,
            activeNodeId: beId,
            activeEdgeId: edgeApiBe.id,
            direction: "downstream",
          });

          // 4. Controller / Service Node
          const srvId = `node-srv-${idx}`;
          const hasController = Boolean(matchedEp.controller);
          nodes.push({
            id: srvId,
            tier: 3,
            label: hasController ? `🔧 ${matchedEp.controller}` : "🔧 Route Handler",
            sub: hasController ? matchedEp.source_file : "Inline Handler",
            badge: hasController ? "Controller" : "Handler",
            badgeType: "service",
            controller: matchedEp.controller,
            sourceFile: matchedEp.source_file,
            lineNumber: matchedEp.line_number,
            evidence: matchedEp.evidence,
            x: TIER_COLUMNS[3].x,
            y: 220,
          });

          const edgeBeSrv: FlowEdge = {
            id: `edge-be-srv-${idx}`,
            sourceId: beId,
            targetId: srvId,
            label: "dispatches",
            status: "matched",
            method: matchedEp.method,
            path: matchedEp.path,
            hasIssue: false,
          };
          edges.push(edgeBeSrv);

          // Story Step 4: Service / Handler Execution
          steps.push({
            stage: "Service",
            title: hasController ? "Controller Handler" : "Route Handler Execution",
            subtitle: matchedEp.controller || "Inline Service Handler",
            location: `${matchedEp.source_file}:${matchedEp.line_number}`,
            description: hasController
              ? `Handler function '${matchedEp.controller}' processes request validation and executes business logic.`
              : "Service layer not separated into a dedicated class — business logic is handled directly in the route function.",
            activeNodeId: srvId,
            activeEdgeId: edgeBeSrv.id,
            direction: "downstream",
          });

          // 5. Database Layer (if detected)
          const dbId = `node-db-${idx}`;
          const hasDb = dbTechs.length > 0;
          const dbLabel = hasDb ? `🗄️ ${dbTechs[0]}` : "🗄️ In-Memory / Direct Return";
          nodes.push({
            id: dbId,
            tier: 4,
            label: dbLabel,
            sub: hasDb ? `${dbTechs.join(", ")} ORM` : "No Database Configured",
            badge: hasDb ? "Database" : "Direct",
            badgeType: "database",
            status: "matched",
            x: TIER_COLUMNS[4].x,
            y: 220,
          });

          const edgeSrvDb: FlowEdge = {
            id: `edge-srv-db-${idx}`,
            sourceId: srvId,
            targetId: dbId,
            label: hasDb ? "queries" : "returns",
            status: "matched",
            method: matchedEp.method,
            path: matchedEp.path,
            hasIssue: false,
          };
          edges.push(edgeSrvDb);

          // Story Step 5: Database
          steps.push({
            stage: "Database",
            title: hasDb ? "Database Persistence" : "Data Layer",
            subtitle: hasDb ? dbTechs.join(", ") : "In-Memory",
            description: hasDb
              ? `The service queries the database layer (${dbTechs.join(", ")}) to read or persist records.`
              : "Database layer not detected in this repository — response is generated directly by application logic.",
            activeNodeId: dbId,
            activeEdgeId: edgeSrvDb.id,
            direction: "downstream",
          });

          // Story Step 6: Response Return
          steps.push({
            stage: "Response",
            title: "HTTP 200 OK Returned",
            subtitle: `HTTP 200 ➔ ${callerName}`,
            location: `${call.source_file}:${call.line_number}`,
            description: `The backend responds with HTTP 200 OK. Frontend '${callerName}' receives the response payload and updates UI state.`,
            activeNodeId: feId,
            activeEdgeId: edgeApiBe.id,
            direction: "upstream",
          });
        }

        return {
          id: flowId,
          method: call.method,
          path: call.path,
          caller: callerName,
          status,
          call,
          endpoint: matchedEp,
          nodes,
          edges,
          steps,
        };
      });
    }

    // Backend-only fallback
    if (backendEndpoints.length > 0) {
      return backendEndpoints.map((ep, idx) => {
        const flowId = `flow-be-${ep.method}-${ep.path}-${idx}`;
        const beId = `node-be-${idx}`;
        const srvId = `node-srv-${idx}`;

        const nodes: FlowNode[] = [
          {
            id: beId,
            tier: 2,
            label: `⚙️ ${ep.method} ${ep.path}`,
            sub: `${ep.source_file}:${ep.line_number}`,
            badge: ep.framework || "Backend Route",
            badgeType: "backend",
            sourceFile: ep.source_file,
            lineNumber: ep.line_number,
            framework: ep.framework,
            controller: ep.controller,
            status: "matched",
            x: TIER_COLUMNS[2].x,
            y: 220,
          },
          {
            id: srvId,
            tier: 3,
            label: `🔧 ${ep.controller || "Route Handler"}`,
            sub: ep.source_file,
            badge: "Service",
            badgeType: "service",
            controller: ep.controller,
            x: TIER_COLUMNS[3].x,
            y: 220,
          },
        ];

        const edges: FlowEdge[] = [
          {
            id: `edge-be-srv-${idx}`,
            sourceId: beId,
            targetId: srvId,
            label: "handles",
            status: "matched",
            method: ep.method,
            path: ep.path,
            hasIssue: false,
          },
        ];

        const steps: StoryStep[] = [
          {
            stage: "Backend",
            title: "Incoming Route Request",
            subtitle: `${ep.method} ${ep.path}`,
            location: `${ep.source_file}:${ep.line_number}`,
            description: `Backend router matches ${ep.method} ${ep.path} in ${ep.source_file}:${ep.line_number}.`,
            activeNodeId: beId,
            direction: "downstream",
          },
          {
            stage: "Service",
            title: "Controller Execution",
            subtitle: ep.controller || "Service Handler",
            description: `Dispatched to handler '${ep.controller || "Route Handler"}'.`,
            activeNodeId: srvId,
            direction: "downstream",
          },
        ];

        return {
          id: flowId,
          method: ep.method,
          path: ep.path,
          caller: "Client",
          status: "matched",
          call: {
            method: ep.method,
            path: ep.path,
            query_params: [],
            body_fields: ep.request_fields,
            response_fields: ep.response_fields,
            source_file: ep.source_file,
            line_number: ep.line_number,
          },
          endpoint: ep,
          nodes,
          edges,
          steps,
        };
      });
    }

    return [];
  }, [frontendCalls, backendEndpoints, issues, dbTechs]);

  // Current active flow
  const currentFlow = apiFlows[selectedFlowIndex] || apiFlows[0] || null;
  const activeStep =
    currentFlow && currentFlow.steps[currentStep] ? currentFlow.steps[currentStep] : null;

  // Node Map for fast lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, FlowNode>();
    if (currentFlow) {
      currentFlow.nodes.forEach((n) => map.set(n.id, n));
    }
    return map;
  }, [currentFlow]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 2. Camera Controls & Node Focusing (With Context Preservation)
  // ─────────────────────────────────────────────────────────────────────────────
  const focusNode = useCallback((node: FlowNode, targetZoom = 1.05) => {
    if (!viewportRef.current) return;
    const rect = viewportRef.current.getBoundingClientRect();
    const vw = rect.width || 900;
    const vh = rect.height || 550;

    // Node card dimensions: width 210, height 70
    const nodeCenterX = node.x + 105;
    const nodeCenterY = node.y + 35;

    // Shift Y slightly up by 40px so the bottom story explanation card never covers the node!
    const targetPanX = vw / 2 - nodeCenterX * targetZoom;
    const targetPanY = vh / 2 - 40 - nodeCenterY * targetZoom;

    setZoom(targetZoom);
    setPan({ x: targetPanX, y: targetPanY });
  }, []);

  const fitGraphToScreen = useCallback(() => {
    if (!viewportRef.current || !currentFlow || currentFlow.nodes.length === 0) return;
    const rect = viewportRef.current.getBoundingClientRect();
    const vw = rect.width || 900;
    const vh = rect.height || 550;

    const xs = currentFlow.nodes.map((n) => n.x);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs) + 220;
    const graphWidth = maxX - minX || 1000;

    const targetZoom = Math.min(1.0, Math.max(0.55, (vw - 120) / graphWidth));
    const targetPanX = (vw - graphWidth * targetZoom) / 2 - minX * targetZoom;
    const targetPanY = (vh - 200 * targetZoom) / 2 - 120 * targetZoom;

    setZoom(targetZoom);
    setPan({ x: targetPanX, y: targetPanY });
  }, [currentFlow]);

  // Automatically center camera when currentStep changes in Explain Flow
  useEffect(() => {
    if (!explainFlow || !activeStep) return;
    const activeNode = nodeMap.get(activeStep.activeNodeId);
    if (activeNode) {
      focusNode(activeNode, 1.02);
    }
  }, [currentStep, activeStep?.activeNodeId, explainFlow, focusNode, nodeMap]);

  // Fit to screen on initial mount or flow change
  useEffect(() => {
    fitGraphToScreen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFlowIndex, viewMode]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 3. Playback Timer: Step Progression
  // ─────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isPlaying || !currentFlow || currentFlow.steps.length === 0) return;

    // Step duration: 2500ms at 1x, 4000ms at 0.5x, 1300ms at 2x
    const stepDuration = Math.round(2500 / speed);
    const timer = setTimeout(() => {
      if (currentStep < currentFlow.steps.length - 1) {
        setCurrentStep((prev) => prev + 1);
      } else {
        setIsPlaying(false);
      }
    }, stepDuration);

    return () => clearTimeout(timer);
  }, [isPlaying, currentStep, currentFlow, speed]);

  // ─────────────────────────────────────────────────────────────────────────────
  // 4. User Interaction Handlers (Pausing when User Interacts)
  // ─────────────────────────────────────────────────────────────────────────────
  const handleNodeClick = (node: FlowNode) => {
    // Immediately pause explanation to not fight user
    setIsPlaying(false);
    setSelectedNode(node);
    setSelectedEdge(null);
    focusNode(node, 1.15);
  };

  const handleEdgeClick = (edge: FlowEdge) => {
    // Immediately pause explanation
    setIsPlaying(false);
    setSelectedEdge(edge);
    setSelectedNode(null);
  };

  const handleSelectFlow = (idx: number) => {
    setSelectedFlowIndex(idx);
    setCurrentStep(0);
    setIsPlaying(false);
    setSelectedEdge(null);
    setSelectedNode(null);
    setShowFlowDropdown(false);
  };

  const handlePreviousStep = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleNextStep = () => {
    if (currentFlow && currentStep < currentFlow.steps.length - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleReplay = () => {
    setCurrentStep(0);
    setIsPlaying(true);
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // 5. Canvas Drag & Wheel Handlers
  // ─────────────────────────────────────────────────────────────────────────────
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 0.08 : -0.08;
    setZoom((prev) => Math.min(2.0, Math.max(0.4, prev + zoomDelta)));
  };

  const activeEdge = useMemo(() => {
    if (!currentFlow || !activeStep?.activeEdgeId) return null;
    return currentFlow.edges.find((e) => e.id === activeStep.activeEdgeId) || null;
  }, [currentFlow, activeStep]);

  return (
    <div className="flow-graph-container">
      {/* ── Top Toolbar ── */}
      <div className="flow-toolbar">
        {/* Left: Mode Toggle & Flow Selector */}
        <div className="flow-toolbar-left" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div className="flow-mode-switch">
            <button
              className={`flow-mode-btn ${viewMode === "flow" ? "active" : ""}`}
              onClick={() => setViewMode("flow")}
              title="Animated Request ↔ Response Data Flow"
            >
              ⚡ Request Flow ({apiFlows.length})
            </button>
            <button
              className={`flow-mode-btn ${viewMode === "overview" ? "active" : ""}`}
              onClick={() => setViewMode("overview")}
              title="Full Application Architecture Overview"
            >
              📐 Architecture Overview ({architecture?.nodes?.length || 0})
            </button>
          </div>

          {/* Flow Selector Dropdown */}
          {viewMode === "flow" && apiFlows.length > 0 && (
            <div style={{ position: "relative" }}>
              <button
                className="flow-control-btn"
                onClick={() => setShowFlowDropdown(!showFlowDropdown)}
                style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}
              >
                <span>Flow:</span>
                <span className={`method-tag method-${currentFlow?.method}`}>
                  {currentFlow?.method}
                </span>
                <span style={{ fontFamily: "monospace" }}>{currentFlow?.path}</span>
                <span>▾</span>
              </button>

              {showFlowDropdown && (
                <div
                  style={{
                    position: "absolute",
                    top: "100%",
                    left: 0,
                    marginTop: 6,
                    width: 320,
                    maxHeight: 350,
                    overflowY: "auto",
                    background: "rgba(21, 27, 38, 0.98)",
                    backdropFilter: "blur(14px)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    boxShadow: "0 12px 36px rgba(0,0,0,0.6)",
                    zIndex: 100,
                    padding: 6,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--muted)",
                      padding: "6px 8px",
                      textTransform: "uppercase",
                    }}
                  >
                    Select Request Flow to Explain:
                  </div>
                  {apiFlows.map((flow, i) => (
                    <div
                      key={flow.id}
                      onClick={() => handleSelectFlow(i)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: 6,
                        cursor: "pointer",
                        background:
                          selectedFlowIndex === i ? "rgba(79, 126, 247, 0.15)" : "transparent",
                        border:
                          selectedFlowIndex === i
                            ? "1px solid var(--accent)"
                            : "1px solid transparent",
                        marginBottom: 4,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className={`method-tag method-${flow.method}`}>{flow.method}</span>
                        <strong style={{ fontFamily: "monospace", fontSize: 12 }}>
                          {flow.path}
                        </strong>
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--muted)",
                          marginTop: 2,
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>{flow.caller}</span>
                        <span className={`status-pill ${flow.status}`}>{flow.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {viewMode === "flow" && (
            <button
              className={`flow-control-btn ${explainFlow ? "active-toggle" : ""}`}
              onClick={() => setExplainFlow(!explainFlow)}
              title="Toggle Story Explanation Panel"
            >
              💡 Explain Flow
            </button>
          )}
        </div>

        {/* Right: Camera Controls */}
        <div className="flow-toolbar-right">
          <button className="flow-control-btn" onClick={fitGraphToScreen} title="Fit Entire Flow to Screen">
            Fit to Screen
          </button>
          <button
            className="flow-control-btn"
            onClick={() => {
              setZoom(1.0);
              setPan({ x: 40, y: 40 });
            }}
            title="Reset Pan & Zoom"
          >
            Reset
          </button>
        </div>
      </div>

      {/* ── Main Canvas Viewport ── */}
      {viewMode === "flow" && (
        <div
          ref={viewportRef}
          className={`flow-canvas-viewport ${isDragging ? "dragging" : ""}`}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onWheel={handleWheel}
          style={{ position: "relative", width: "100%", height: 600, overflow: "hidden" }}
        >
          {/* Zoom Overlay Buttons */}
          <div className="flow-zoom-controls">
            <button
              className="zoom-btn"
              onClick={() => setZoom((z) => Math.min(2.0, z + 0.15))}
              title="Zoom In"
            >
              +
            </button>
            <button
              className="zoom-btn"
              onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
              title="Zoom Out"
            >
              −
            </button>
            <button className="zoom-btn" onClick={fitGraphToScreen} title="Fit to Screen">
              ↺
            </button>
          </div>

          {/* Smooth Canvas Transform Container */}
          <div
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "0 0",
              width: 1550,
              height: 600,
              position: "absolute",
              transition: isDragging ? "none" : "transform 0.65s cubic-bezier(0.22, 1, 0.36, 1)",
            }}
          >
            {/* Column Headers */}
            <div className="tier-column-headers">
              {TIER_COLUMNS.map((col) => (
                <div
                  key={col.tier}
                  className="tier-col-header"
                  style={{ width: 280, paddingLeft: col.tier === 0 ? 80 : 40 }}
                >
                  <span>{col.icon}</span>
                  <span>{col.title}</span>
                </div>
              ))}
            </div>

            {/* SVG Layer: Connecting Bezier Curves & Animated Particles */}
            <svg className="flow-svg-layer" width={1550} height={600}>
              <defs>
                <marker
                  id="arrow-downstream"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#48bb78" />
                </marker>
                <marker
                  id="arrow-upstream"
                  viewBox="0 0 10 10"
                  refX="2"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 10 1 L 0 5 L 10 9 z" fill="#38b2ac" />
                </marker>
                <marker
                  id="arrow-mismatch"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--red)" />
                </marker>
              </defs>

              {currentFlow &&
                currentFlow.edges.map((edge) => {
                  const srcNode = nodeMap.get(edge.sourceId);
                  const tgtNode = nodeMap.get(edge.targetId);
                  if (!srcNode || !tgtNode) return null;

                  const x1 = srcNode.x + 210;
                  const y1 = srcNode.y + 35;
                  const x2 = tgtNode.x;
                  const y2 = tgtNode.y + 35;

                  const dx = x2 - x1;
                  const cp1x = x1 + dx * 0.45;
                  const cp1y = y1;
                  const cp2x = x1 + dx * 0.55;
                  const cp2y = y2;
                  const pathD = `M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`;

                  const isActive = activeEdge?.id === edge.id;
                  const isDownstream = activeStep?.direction === "downstream";
                  const isUpstream = activeStep?.direction === "upstream";
                  const isMismatch = edge.status === "mismatch";
                  const isDimmed = explainFlow && activeEdge && !isActive;

                  return (
                    <g key={edge.id} onClick={() => handleEdgeClick(edge)}>
                      {/* Transparent wider path for easy clicking */}
                      <path
                        d={pathD}
                        stroke="transparent"
                        strokeWidth={16}
                        fill="none"
                        style={{ cursor: "pointer" }}
                      />
                      {/* Main Bezier curve */}
                      <path
                        d={pathD}
                        className={`flow-path-edge ${isActive ? "active-edge" : ""} ${
                          isDimmed ? "dimmed-edge" : ""
                        } ${isUpstream ? "upstream" : isDownstream ? "downstream" : ""} ${isMismatch ? "mismatch" : ""}`}
                        markerEnd={
                          isMismatch
                            ? "url(#arrow-mismatch)"
                            : isActive && isUpstream
                            ? "url(#arrow-upstream)"
                            : "url(#arrow-downstream)"
                        }
                      />

                      {/* Traveling Pulse Particle */}
                      {isActive && (
                        <g>
                          <circle
                            r={6}
                            fill={isUpstream ? "#38b2ac" : isMismatch ? "var(--red)" : "#48bb78"}
                            className="pulse-circle"
                          >
                            <animateMotion
                              dur={`${Math.max(0.6, 1.4 / speed)}s`}
                              repeatCount="indefinite"
                              path={pathD}
                              keyPoints={isUpstream ? "1;0" : "0;1"}
                              keyTimes="0;1"
                            />
                          </circle>
                        </g>
                      )}
                    </g>
                  );
                })}
            </svg>

            {/* HTML Layer: Node Cards */}
            {currentFlow &&
              currentFlow.nodes.map((node) => {
                const isActive = activeStep?.activeNodeId === node.id;
                const isDimmed = explainFlow && activeStep && !isActive;
                const isMismatch = node.status === "mismatch";
                const isMissing = node.status === "missing";
                const isExternal = node.status === "external";

                return (
                  <div
                    key={node.id}
                    className={`canvas-node-card ${isActive ? "active-step-node" : ""} ${
                      isDimmed ? "dimmed-node" : ""
                    } ${isActive && (isMismatch || isMissing) ? "mismatch-pulse" : ""} ${
                      isActive && isExternal ? "external-pulse" : ""
                    }`}
                    style={{
                      left: node.x,
                      top: node.y,
                      cursor: "pointer",
                    }}
                    onClick={() => handleNodeClick(node)}
                    title="Click to focus & inspect node"
                  >
                    <div className="node-card-top">
                      <span className={`node-card-badge ${node.badgeType}`}>{node.badge}</span>
                      {node.confidence && (
                        <span className={`confidence-pill ${node.confidence}`}>
                          {node.confidence}
                        </span>
                      )}
                    </div>
                    <div className="node-card-label" title={node.label}>
                      {node.label}
                    </div>
                    {node.sub && (
                      <div className="node-card-sub" title={node.sub}>
                        {node.sub}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>

          {/* ── Compact Story "Explain Flow" Panel ── */}
          {explainFlow && activeStep && (
            <div className="flow-story-panel">
              {/* Header */}
              <div className="flow-story-header">
                <div className="flow-story-title">
                  <span>📖</span>
                  <span>Explain Flow</span>
                </div>
                <div className="flow-story-counter">
                  Step {currentStep + 1} of {currentFlow?.steps.length}
                </div>
              </div>

              {/* Progress Track & Clickable Step Bullets */}
              <div className="flow-progress-track">
                {currentFlow?.steps.map((s, idx) => (
                  <React.Fragment key={idx}>
                    <button
                      className={`flow-step-bullet ${idx < currentStep ? "completed" : ""} ${
                        idx === currentStep ? "active" : ""
                      }`}
                      onClick={() => {
                        setCurrentStep(idx);
                        setIsPlaying(false);
                      }}
                      title={`Jump to Step ${idx + 1}: ${s.stage}`}
                    >
                      {idx + 1}
                    </button>
                    {idx < currentFlow.steps.length - 1 && (
                      <div
                        className={`flow-step-line ${idx < currentStep ? "active" : ""}`}
                      />
                    )}
                  </React.Fragment>
                ))}
              </div>

              {/* Stages Breadcrumb */}
              <div className="flow-stages-row">
                {["Frontend", "API Request", "Backend", "Service", "Database"].map(
                  (st, i) => (
                    <React.Fragment key={st}>
                      <span
                        className={`flow-stage-pill ${activeStep.stage === st ? "active" : ""}`}
                      >
                        {st}
                      </span>
                      {i < 4 && <span>→</span>}
                    </React.Fragment>
                  )
                )}
              </div>

              {/* Narrative Content */}
              <div className="flow-story-body">
                <div className="flow-story-stage-tag">{activeStep.stage}</div>
                <div className="flow-story-main-title">{activeStep.title}</div>
                {activeStep.location && (
                  <div className="flow-story-location">{activeStep.location}</div>
                )}
                <div className="flow-story-desc">{activeStep.description}</div>
              </div>

              {/* Playback & Step Controls */}
              <div className="flow-story-footer">
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="flow-story-nav-btn"
                    onClick={handlePreviousStep}
                    disabled={currentStep === 0}
                    title="Previous Step"
                  >
                    ← Previous
                  </button>
                  <button
                    className="flow-story-nav-btn primary"
                    onClick={() => setIsPlaying(!isPlaying)}
                    title={isPlaying ? "Pause Flow" : "Play Flow"}
                  >
                    {isPlaying ? "⏸ Pause" : "▶ Play"}
                  </button>
                  <button
                    className="flow-story-nav-btn"
                    onClick={handleNextStep}
                    disabled={!currentFlow || currentStep === currentFlow.steps.length - 1}
                    title="Next Step"
                  >
                    Next →
                  </button>
                </div>

                <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  <button
                    className="flow-story-nav-btn"
                    onClick={handleReplay}
                    title="Replay from Step 1"
                  >
                    ↻
                  </button>
                  <div className="speed-selector" style={{ transform: "scale(0.9)" }}>
                    {[0.5, 1, 2].map((s) => (
                      <button
                        key={s}
                        className={`speed-btn ${speed === s ? "active" : ""}`}
                        onClick={() => setSpeed(s)}
                      >
                        {s}x
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Edge / Connection Inspector Drawer ── */}
          {selectedEdge && (
            <div className="flow-edge-drawer">
              <div className="node-inspector-header">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={`method-tag method-${selectedEdge.method}`}>
                    {selectedEdge.method}
                  </span>
                  <strong style={{ fontSize: 13 }}>{selectedEdge.path}</strong>
                </div>
                <button className="btn-ghost" onClick={() => setSelectedEdge(null)}>
                  ✕
                </button>
              </div>

              <div className="node-inspector-body">
                <div className="inspector-row">
                  <span className="inspector-label">Status</span>
                  <span className={`status-pill ${selectedEdge.status}`}>
                    {selectedEdge.status.toUpperCase()}
                  </span>
                </div>

                <div className="inspector-row">
                  <span className="inspector-label">Frontend Caller</span>
                  <span className="inspector-value">
                    {selectedEdge.feCaller || "Frontend Page"}
                    {selectedEdge.feLine ? ` (Line ${selectedEdge.feLine})` : ""}
                  </span>
                </div>

                {selectedEdge.beEndpoint && (
                  <div className="inspector-row">
                    <span className="inspector-label">Backend Route Endpoint</span>
                    <span className="inspector-value">
                      {selectedEdge.beEndpoint}
                      {selectedEdge.beLine ? ` (Line ${selectedEdge.beLine})` : ""}
                    </span>
                  </div>
                )}

                <div className="inspector-row">
                  <span className="inspector-label">Data Flow</span>
                  <span className="inspector-value">
                    Frontend ➔ API Request ➔ Backend Route ➔ Service ➔ Database
                  </span>
                </div>

                {selectedEdge.issueDetails && (
                  <div className="inspector-issue-box">
                    <strong>Mismatch Explanation:</strong>
                    <p style={{ margin: "4px 0 0", fontSize: 12 }}>
                      {selectedEdge.issueDetails}
                    </p>
                    {onIssueClick && (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 11, padding: "2px 8px", marginTop: 6 }}
                        onClick={() => {
                          const found = issues.find(
                            (i) =>
                              i.frontend_location?.line === selectedEdge.feLine ||
                              i.explanation === selectedEdge.issueDetails
                          );
                          if (found) onIssueClick(found);
                        }}
                      >
                        View Fix in Issues Tab →
                      </button>
                    )}
                  </div>
                )}

                {selectedEdge.evidence && (
                  <div className="inspector-row">
                    <span className="inspector-label">Source Evidence</span>
                    <div className="evidence-snippet">{selectedEdge.evidence}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Node Inspector Drawer ── */}
          {selectedNode && (
            <div className="flow-edge-drawer" style={{ left: 20, right: "auto" }}>
              <div className="node-inspector-header">
                <strong>{selectedNode.label}</strong>
                <button className="btn-ghost" onClick={() => setSelectedNode(null)}>
                  ✕
                </button>
              </div>
              <div className="node-inspector-body">
                {"sourceFile" in selectedNode && selectedNode.sourceFile && (
                  <div className="inspector-row">
                    <span className="inspector-label">Source File</span>
                    <span className="inspector-value mono">
                      {selectedNode.sourceFile}
                      {"lineNumber" in selectedNode && selectedNode.lineNumber
                        ? `:${selectedNode.lineNumber}`
                        : ""}
                    </span>
                  </div>
                )}

                {"controller" in selectedNode && selectedNode.controller && (
                  <div className="inspector-row">
                    <span className="inspector-label">Controller / Handler</span>
                    <span className="inspector-value mono">{String(selectedNode.controller)}</span>
                  </div>
                )}

                {"framework" in selectedNode && selectedNode.framework && (
                  <div className="inspector-row">
                    <span className="inspector-label">Framework</span>
                    <span className="tech-pill">{String(selectedNode.framework)}</span>
                  </div>
                )}

                {"evidence" in selectedNode && selectedNode.evidence && (
                  <div className="inspector-row">
                    <span className="inspector-label">Source Evidence</span>
                    <div className="evidence-snippet">{String(selectedNode.evidence)}</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Secondary Mode: Static Architecture Overview ── */}
      {/* ── Secondary Mode: Static Architecture Overview ── */}
      {viewMode === "overview" && (() => {
        const archNodes = architecture?.nodes || [];
        const archEdges = architecture?.edges || [];

        return (
        <div style={{ padding: 18 }}>
          {architecture?.explanation && (
            <div className="notice-banner info" style={{ marginBottom: 16 }}>
              <span className="notice-icon">ℹ️</span>
              <div>
                <strong>Architecture Note</strong>
                <p>{architecture.explanation}</p>
              </div>
            </div>
          )}

          {/* Overview Filter Bar */}
          <div className="arch-controls" style={{ marginBottom: 16 }}>
            <div className="arch-filters">
              <button
                className={`arch-filter-btn ${overviewFilter === "all" ? "active" : ""}`}
                onClick={() => setOverviewFilter("all")}
              >
                All Components ({archNodes.length})
              </button>
              <button
                className={`arch-filter-btn ${overviewFilter === "issues" ? "active" : ""}`}
                onClick={() => setOverviewFilter("issues")}
              >
                ⚠️ Issues ({issues.length})
              </button>
              <button
                className={`arch-filter-btn ${overviewFilter === "frontend" ? "active" : ""}`}
                onClick={() => setOverviewFilter("frontend")}
              >
                🖥️ Frontend (
                {archNodes.filter((n) => n.kind.startsWith("frontend_")).length})
              </button>
              <button
                className={`arch-filter-btn ${overviewFilter === "backend" ? "active" : ""}`}
                onClick={() => setOverviewFilter("backend")}
              >
                ⚙️ Backend (
                {
                  archNodes.filter(
                    (n) => n.kind.startsWith("backend_") || n.kind === "missing_endpoint"
                  ).length
                }
                )
              </button>
            </div>

            <input
              type="text"
              className="arch-search-input"
              placeholder="Search components or routes..."
              value={overviewSearch}
              onChange={(e) => setOverviewSearch(e.target.value)}
            />
          </div>

          {/* 3-Column Architecture Grid */}
          <div className="arch-grid">
            {/* Frontend Column */}
            <div className="arch-column">
              <div className="arch-column-header">
                <span>🖥️ Frontend Layer</span>
              </div>
              <div className="arch-layer">
                {archNodes
                  .filter((n) => n.kind.startsWith("frontend_"))
                  .filter(
                    (n) =>
                      !overviewSearch ||
                      n.label.toLowerCase().includes(overviewSearch.toLowerCase())
                  )
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`arch-node clickable ${
                        overviewSelectedId === node.id ? "selected" : ""
                      }`}
                      onClick={() =>
                        setOverviewSelectedId(
                          overviewSelectedId === node.id ? null : node.id
                        )
                      }
                    >
                      <span className="node-icon">📄</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="node-label">{node.label}</div>
                        {node.source_file && (
                          <div className="node-sub">{node.source_file}</div>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            {/* Edge Connections Column */}
            <div className="arch-edges-column">
              <div className="arch-column-header">
                <span>API Connections ({archEdges.length})</span>
              </div>
              <div className="arch-edges-list">
                {archEdges.map((edge, i) => (
                  <div
                    key={i}
                    className={`arch-connector ${edge.has_issue ? "issue" : ""}`}
                  >
                    <div className="arch-arrow">→</div>
                    <div className="arch-edge-label">{edge.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Backend Column */}
            <div className="arch-column">
              <div className="arch-column-header">
                <span>⚙️ Backend & Data</span>
              </div>
              <div className="arch-layer">
                {archNodes
                  .filter(
                    (n) =>
                      n.kind.startsWith("backend_") ||
                      n.kind === "database" ||
                      n.kind === "external_api"
                  )
                  .filter(
                    (n) =>
                      !overviewSearch ||
                      n.label.toLowerCase().includes(overviewSearch.toLowerCase())
                  )
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`arch-node clickable ${
                        overviewSelectedId === node.id ? "selected" : ""
                      }`}
                      onClick={() =>
                        setOverviewSelectedId(
                          overviewSelectedId === node.id ? null : node.id
                        )
                      }
                    >
                      <span className="node-icon">
                        {node.kind === "database"
                          ? "🗄️"
                          : node.kind === "external_api"
                          ? "🌐"
                          : "⚙️"}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="node-label">{node.label}</div>
                        {node.source_file && (
                          <div className="node-sub">{node.source_file}</div>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
        );
      })()}
    </div>
  );
}
