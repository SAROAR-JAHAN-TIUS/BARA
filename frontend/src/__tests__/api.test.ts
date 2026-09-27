/**
 * BARA Frontend – API utility tests.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { isGithubUrl } from "../api";

describe("isGithubUrl", () => {
  it("accepts a standard GitHub HTTPS URL", () => {
    expect(isGithubUrl("https://github.com/facebook/react")).toBe(true);
  });

  it("accepts a URL with .git suffix", () => {
    expect(isGithubUrl("https://github.com/facebook/react.git")).toBe(true);
  });

  it("accepts a URL with trailing slash", () => {
    expect(isGithubUrl("https://github.com/facebook/react/")).toBe(true);
  });

  it("accepts URL with .git and trailing slash", () => {
    expect(isGithubUrl("https://github.com/microsoft/vscode.git/")).toBe(true);
  });

  it("accepts URL with hyphens, dots, underscores", () => {
    expect(isGithubUrl("https://github.com/SAROAR-JAHAN-TIUS/helping")).toBe(true);
    expect(isGithubUrl("https://github.com/my_user/my.repo")).toBe(true);
  });

  it("accepts URL with query parameters (e.g. ?utm_source)", () => {
    expect(isGithubUrl("https://github.com/codecrafters-io/build-your-own-x?utm_source")).toBe(true);
    expect(isGithubUrl("https://github.com/facebook/react?tab=readme-ov-file&utm_source=twitter")).toBe(true);
  });

  it("accepts URL with hash fragments (e.g. #readme)", () => {
    expect(isGithubUrl("https://github.com/facebook/react#readme")).toBe(true);
  });

  it("trims whitespace", () => {
    expect(isGithubUrl("  https://github.com/owner/repo  ")).toBe(true);
  });

  it("rejects a local path", () => {
    expect(isGithubUrl("/home/user/projects/my-app")).toBe(false);
  });

  it("rejects HTTP (non-HTTPS) GitHub URL", () => {
    expect(isGithubUrl("http://github.com/owner/repo")).toBe(false);
  });

  it("rejects non-GitHub HTTPS URL", () => {
    expect(isGithubUrl("https://gitlab.com/owner/repo")).toBe(false);
  });

  it("rejects GitHub URL without repo name", () => {
    expect(isGithubUrl("https://github.com/owner")).toBe(false);
  });

  it("rejects GitHub URL with extra path segments", () => {
    expect(isGithubUrl("https://github.com/owner/repo/tree/main")).toBe(false);
  });

  it("rejects empty string", () => {
    expect(isGithubUrl("")).toBe(false);
  });

  it("rejects a random string", () => {
    expect(isGithubUrl("not-a-url-at-all")).toBe(false);
  });
});

// ─── analyzeProject tests (mocked axios) ──────────────────────────────────────

vi.mock("axios", () => {
  const mockPost = vi.fn();
  const mockGet = vi.fn();
  return {
    default: {
      create: () => ({
        post: mockPost,
        get: mockGet,
      }),
    },
    __mockPost: mockPost,
    __mockGet: mockGet,
  };
});

const axiosMock = await import("axios");
const mockPost = (axiosMock as unknown as { __mockPost: ReturnType<typeof vi.fn> }).__mockPost;
const { analyzeProject } = await import("../api");

describe("analyzeProject", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends { source_type: 'local', source } for a local path", async () => {
    const fakeResult = {
      analysis_id: "test-id",
      source_type: "local",
      source: "/home/user/app",
      project_name: "app",
      github_url: null,
      frontend_calls: [],
      backend_endpoints: [],
      issues: [],
      architecture: { nodes: [], edges: [] },
      summary: {
        total_frontend_calls: 0,
        total_backend_endpoints: 0,
        total_issues: 0,
        issues_by_type: {},
        issues_by_severity: { high: 0, medium: 0, low: 0 },
        frontend_files_scanned: 0,
        backend_files_scanned: 0,
      },
    };
    mockPost.mockResolvedValueOnce({ data: fakeResult });

    const result = await analyzeProject("local", "  /home/user/app  ");
    expect(mockPost).toHaveBeenCalledWith("/api/analyze", {
      source_type: "local",
      source: "/home/user/app",
    });
    expect(result.source_type).toBe("local");
    expect(result.project_name).toBe("app");
  });

  it("sends { source_type: 'github', source } for a GitHub URL", async () => {
    const fakeResult = {
      analysis_id: "test-id-2",
      source_type: "github",
      source: "https://github.com/owner/repo",
      project_name: "owner/repo",
      github_url: "https://github.com/owner/repo",
      frontend_calls: [],
      backend_endpoints: [],
      issues: [],
      architecture: { nodes: [], edges: [] },
      summary: {
        total_frontend_calls: 0,
        total_backend_endpoints: 0,
        total_issues: 0,
        issues_by_type: {},
        issues_by_severity: { high: 0, medium: 0, low: 0 },
        frontend_files_scanned: 0,
        backend_files_scanned: 0,
      },
    };
    mockPost.mockResolvedValueOnce({ data: fakeResult });

    const result = await analyzeProject("github", "https://github.com/owner/repo");
    expect(mockPost).toHaveBeenCalledWith("/api/analyze", {
      source_type: "github",
      source: "https://github.com/owner/repo",
    });
    expect(result.source_type).toBe("github");
    expect(result.project_name).toBe("owner/repo");
  });

  it("throws when the backend returns an error", async () => {
    mockPost.mockRejectedValueOnce({
      response: { status: 400, data: { detail: "Path does not exist" } },
    });

    await expect(analyzeProject("local", "/nonexistent")).rejects.toBeTruthy();
  });
});
