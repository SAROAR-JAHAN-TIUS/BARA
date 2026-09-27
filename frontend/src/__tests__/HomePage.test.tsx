/**
 * BARA Frontend – HomePage tests.
 *
 * Verifies the local folder picker workflow, GitHub repository tab,
 * file validation, and analysis submission.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { HomePage } from "../pages/HomePage";
import * as api from "../api";

vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    analyzeProject: vi.fn(),
    analyzeUploadedFolder: vi.fn(),
  };
});

describe("HomePage Folder Picker Workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Local Project mode with Add Local Folder button by default", () => {
    render(<HomePage onResult={vi.fn()} />);

    expect(screen.getByText("📁 Local Project")).toBeTruthy();
    expect(screen.getByText("🐙 GitHub Repository")).toBeTruthy();
    expect(screen.getByText("Add Local Folder")).toBeTruthy();
    expect(screen.getByText("No folder selected")).toBeTruthy();

    const analyzeBtn = screen.getByRole("button", { name: "Analyze →" });
    expect((analyzeBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("switches to GitHub mode and enables analyze when URL is provided", () => {
    render(<HomePage onResult={vi.fn()} />);

    const githubTab = screen.getByText("🐙 GitHub Repository");
    fireEvent.click(githubTab);

    const input = screen.getByLabelText("GitHub repository URL");
    expect(input).toBeTruthy();

    const analyzeBtn = screen.getByRole("button", { name: "Clone & Analyze →" });
    expect((analyzeBtn as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(input, { target: { value: "https://github.com/tiangolo/fastapi" } });
    expect((analyzeBtn as HTMLButtonElement).disabled).toBe(false);
  });

  it("handles folder selection and enables analysis", async () => {
    const mockOnResult = vi.fn();
    (api.analyzeUploadedFolder as any).mockResolvedValue({
      analysis_id: "test-123",
      source_type: "local",
      source: "cool-project",
      project_name: "cool-project",
      frontend_calls: [],
      backend_endpoints: [],
      issues: [],
      architecture: { nodes: [], edges: [] },
      summary: {},
    });

    const { container } = render(<HomePage onResult={mockOnResult} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    // Create fake files
    const file1 = new File(["console.log(1)"], "App.tsx", { type: "text/plain" });
    Object.defineProperty(file1, "webkitRelativePath", {
      value: "cool-project/src/App.tsx",
    });

    const file2 = new File(["def api(): pass"], "main.py", { type: "text/plain" });
    Object.defineProperty(file2, "webkitRelativePath", {
      value: "cool-project/backend/main.py",
    });

    fireEvent.change(fileInput, {
      target: { files: [file1, file2] },
    });

    // Folder status should update
    expect(screen.getByText("cool-project")).toBeTruthy();
    expect(screen.getByText("(2 source files ready)")).toBeTruthy();

    const analyzeBtn = screen.getByRole("button", { name: "Analyze →" });
    expect((analyzeBtn as HTMLButtonElement).disabled).toBe(false);

    // Click Analyze
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(api.analyzeUploadedFolder).toHaveBeenCalledTimes(1);
      expect(api.analyzeUploadedFolder).toHaveBeenCalledWith("cool-project", expect.any(Array));
      expect(mockOnResult).toHaveBeenCalledTimes(1);
    });
  });

  it("allows clearing the selected folder", () => {
    const { container } = render(<HomePage onResult={vi.fn()} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["code"], "index.js", { type: "text/plain" });
    Object.defineProperty(file, "webkitRelativePath", {
      value: "my-app/index.js",
    });

    fireEvent.change(fileInput, {
      target: { files: [file] },
    });

    expect(screen.getByText("my-app")).toBeTruthy();

    const removeBtn = screen.getByTitle("Remove folder");
    fireEvent.click(removeBtn);

    expect(screen.getByText("No folder selected")).toBeTruthy();
    const analyzeBtn = screen.getByRole("button", { name: "Analyze →" });
    expect((analyzeBtn as HTMLButtonElement).disabled).toBe(true);
  });
});
