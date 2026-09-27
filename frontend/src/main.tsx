import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Last-resort global handlers – prevent silent blank pages
window.addEventListener("error", (e) => {
  console.error("[BARA] Uncaught global error:", e.error);
});
window.addEventListener("unhandledrejection", (e) => {
  console.error("[BARA] Unhandled promise rejection:", e.reason);
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
