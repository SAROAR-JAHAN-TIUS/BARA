// BARA – Main App component
import { useState } from "react";
import "./index.css";
import "./App.css";
import type { AnalysisResult } from "./types";
import { HomePage } from "./pages/HomePage";
import { ResultsPage } from "./pages/ResultsPage";

function Navbar() {
  return (
    <nav className="navbar">
      <span className="navbar-brand">
        <span>BARA</span>
      </span>
      <span style={{ color: "var(--muted)", fontSize: 13 }}>
        Backend Architecture &amp; API Analyzer
      </span>
    </nav>
  );
}

export default function App() {
  const [result, setResult] = useState<AnalysisResult | null>(null);

  return (
    <div className="app">
      <Navbar />
      {result ? (
        <ResultsPage result={result} onNewAnalysis={() => setResult(null)} />
      ) : (
        <HomePage onResult={setResult} />
      )}
    </div>
  );
}
