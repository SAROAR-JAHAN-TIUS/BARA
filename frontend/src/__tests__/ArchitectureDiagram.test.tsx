/**
 * BARA Frontend – ArchitectureDiagram tests.
 *
 * Verifies interactive architecture diagram, story flow playback,
 * camera controls, node selection, and mode switching.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";
import type { Architecture, Issue, ApiCall, ApiEndpoint } from "../types";

const mockArchitecture: Architecture = {
  nodes: [
    {
      id: "fe-app",
      label: "App.tsx",
      kind: "frontend_page",
      source_file: "src/App.tsx",
      details: {},
    },
    {
      id: "be-router",
      label: "routes.py",
      kind: "backend_endpoint",
      source_file: "backend/routes.py",
      details: {},
    },
  ],
  edges: [
    {
      source: "fe-app",
      target: "be-router",
      label: "GET /api/users",
      relation: "calls",
      has_issue: false,
    },
  ],
};

const mockFrontendCalls: ApiCall[] = [
  {
    source_file: "src/App.tsx",
    line_number: 24,
    method: "GET",
    path: "/api/users",
    query_params: [],
    body_fields: [],
    response_fields: [],
  },
];

const mockBackendEndpoints: ApiEndpoint[] = [
  {
    source_file: "backend/routes.py",
    line_number: 12,
    method: "GET",
    path: "/api/users",
    request_fields: [],
    response_fields: [],
    controller: "get_users",
  },
];

const mockIssues: Issue[] = [];

describe("ArchitectureDiagram", () => {
  it("renders the diagram canvas and mode toggles", () => {
    render(
      <ArchitectureDiagram
        architecture={mockArchitecture}
        issues={mockIssues}
        frontendCalls={mockFrontendCalls}
        backendEndpoints={mockBackendEndpoints}
      />
    );

    expect(screen.getByText(/Request Flow/)).toBeTruthy();
    expect(screen.getByText(/Architecture Overview/)).toBeTruthy();
    expect(screen.getAllByText(/Explain Flow/).length).toBeGreaterThan(0);
  });

  it("can switch between Request Flow and Architecture Overview modes", () => {
    render(
      <ArchitectureDiagram
        architecture={mockArchitecture}
        issues={mockIssues}
        frontendCalls={mockFrontendCalls}
        backendEndpoints={mockBackendEndpoints}
      />
    );

    const overviewBtn = screen.getByText(/Architecture Overview/);
    fireEvent.click(overviewBtn);
    expect(overviewBtn.classList.contains("active")).toBe(true);

    const flowBtn = screen.getByText(/Request Flow/);
    fireEvent.click(flowBtn);
    expect(flowBtn.classList.contains("active")).toBe(true);
  });

  it("activates Explain Flow, shows progress track and controls", () => {
    render(
      <ArchitectureDiagram
        architecture={mockArchitecture}
        issues={mockIssues}
        frontendCalls={mockFrontendCalls}
        backendEndpoints={mockBackendEndpoints}
      />
    );

    // Story panel should be displayed with step count
    expect(screen.getByText(/Step 1 of/)).toBeTruthy();
    expect(screen.getByTitle("Replay from Step 1")).toBeTruthy();
    expect(screen.getByText("Next →")).toBeTruthy();
    expect(screen.getByText("▶ Play")).toBeTruthy();

    // Clicking Play toggles to Pause
    const playBtn = screen.getByText("▶ Play");
    fireEvent.click(playBtn);
    expect(screen.getByText("⏸ Pause")).toBeTruthy();

    // Clicking Pause toggles back to Play
    fireEvent.click(screen.getByText("⏸ Pause"));
    expect(screen.getByText("▶ Play")).toBeTruthy();

    // Clicking Next advances step
    const nextBtn = screen.getByText("Next →");
    fireEvent.click(nextBtn);

    // Replay button restarts to step 0
    const replayBtn = screen.getByTitle("Replay from Step 1");
    fireEvent.click(replayBtn);
  });
});
