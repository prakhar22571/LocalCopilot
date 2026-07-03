import * as vscode from "vscode";
import { ReviewResponse } from "./reviewClient";

let activePanel: vscode.WebviewPanel | undefined;

const RISK_COLOR: Record<string, string> = {
  low: "#3fb950",
  medium: "#d29922",
  high: "#f85149",
};

export function showReview(title: string, result: ReviewResponse): void {
  if (!activePanel) {
    activePanel = vscode.window.createWebviewPanel(
      "localCopilotReview",
      "Local Copilot Review",
      vscode.ViewColumn.Beside,
      { enableScripts: false }
    );
    activePanel.onDidDispose(() => {
      activePanel = undefined;
    });
  }
  activePanel.title = title;
  activePanel.webview.html = renderHtml(title, result);
  activePanel.reveal(vscode.ViewColumn.Beside, true);
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderHtml(title: string, { review, metrics }: ReviewResponse): string {
  const riskColor = RISK_COLOR[review.risk_level] ?? "#8b949e";
  const tests = review.suggested_tests.map((t) => `<li>${escapeHtml(t)}</li>`).join("");

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family); padding: 1.5rem; color: var(--vscode-foreground); }
  h1 { font-size: 1.1rem; margin-bottom: 1rem; }
  .badges { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .badge { padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
  .change-type { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
  .risk { color: white; }
  .summary { line-height: 1.5; margin-bottom: 1.5rem; }
  h2 { font-size: 0.95rem; margin-top: 1.5rem; }
  ul { padding-left: 1.2rem; }
  li { margin-bottom: 0.4rem; }
  .metrics { margin-top: 2rem; font-size: 0.8rem; color: var(--vscode-descriptionForeground); }
  .metrics span { margin-right: 1.2rem; }
</style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <div class="badges">
    <span class="badge change-type">${escapeHtml(review.change_type)}</span>
    <span class="badge risk" style="background:${riskColor}">${escapeHtml(review.risk_level)} risk</span>
  </div>
  <p class="summary">${escapeHtml(review.summary)}</p>
  <h2>Suggested tests</h2>
  <ul>${tests}</ul>
  <div class="metrics">
    <span>model: ${escapeHtml(metrics.model)}</span>
    <span>${metrics.wall_clock_seconds.toFixed(1)}s</span>
    <span>${metrics.tokens_per_second.toFixed(1)} tok/s</span>
    <span>retries: ${metrics.retries}</span>
  </div>
</body>
</html>`;
}
