# BARA Frontend

The interactive user interface for BARA (Backend Architecture & Relationship Analyzer), built with **React 19**, **TypeScript**, and **Vite**.

## Features

- **Local Folder Selection**: Native operating system directory picker (`webkitdirectory`) with real-time file packaging and security validation.
- **GitHub Repository Explorer**: Instant shallow clone and analysis for any public GitHub repository.
- **7 Deep Inspection Views**:
  1. **Issues**: Interactive contract mismatch explorer with side-by-side frontend vs backend code diffs and suggested fixes.
  2. **Architecture**: Dual-mode interactive canvas (`Request Flow` animated storyteller + `Architecture Overview` multi-tier graph).
  3. **Frontend**: Discovered HTTP clients, base URLs, callers, query parameters, and code snippets.
  4. **Backend**: Routes, methods, controller functions, and request/response models.
  5. **API Connections**: Complete contract matrix (matched, mismatched, unused backend endpoints, external calls).
  6. **Database / Services**: Detected ORMs, database drivers, and third-party APIs.
  7. **Repository Structure**: Hierarchical directory browser categorized by architectural roles.
- **Storyteller Request Flow Player**: 5-tier animated packet simulation with playback controls (`Play`, `Pause`, `Replay`, `Prev`, `Next`, `0.5x`, `1x`, `2x`) and camera tracking.

## Development Commands

```bash
# Install dependencies
npm install

# Run Vite development server (http://localhost:5173)
npm run dev

# Run unit and integration tests (Vitest)
npm test

# Build production bundle (TypeScript check + Vite production build)
npm run build
```

For full system architecture, backend setup, and end-to-end instructions, see the main [README.md](../README.md).
