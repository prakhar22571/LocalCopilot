import * as vscode from "vscode";
import { checkHealth, reviewDiff, ReviewClientError } from "./reviewClient";
import { getWorkingTreeDiff, getStagedDiff, getRefDiff, GitError } from "./gitDiff";
import { showReview } from "./panel";

function config() {
  const cfg = vscode.workspace.getConfiguration("localCopilot");
  return {
    serverUrl: cfg.get<string>("serverUrl", "http://127.0.0.1:8000"),
    model: cfg.get<string>("model", "granite4:3b"),
    temperature: cfg.get<number>("temperature", 0.0),
  };
}

async function runReview(title: string, getDiff: () => Promise<string>): Promise<void> {
  const { serverUrl, model, temperature } = config();

  const healthy = await checkHealth(serverUrl);
  if (!healthy) {
    const choice = await vscode.window.showErrorMessage(
      `Local Copilot server is not reachable at ${serverUrl}.`,
      "Copy start command",
      "Open settings"
    );
    if (choice === "Copy start command") {
      await vscode.env.clipboard.writeText("uvicorn app.api:app --reload");
      vscode.window.showInformationMessage("Copied. Run it from the LocalCopilot project root with its venv active.");
    } else if (choice === "Open settings") {
      await vscode.commands.executeCommand("workbench.action.openSettings", "localCopilot");
    }
    return;
  }

  let diff: string;
  try {
    diff = await getDiff();
  } catch (err) {
    const message = err instanceof GitError ? err.message : String(err);
    vscode.window.showErrorMessage(`Local Copilot: ${message}`);
    return;
  }

  if (!diff.trim()) {
    vscode.window.showInformationMessage(`Local Copilot: no changes found for "${title}".`);
    return;
  }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `Local Copilot: reviewing (${model})...` },
    async () => {
      try {
        const result = await reviewDiff(serverUrl, diff, model, temperature);
        showReview(title, result);
      } catch (err) {
        const message = err instanceof ReviewClientError ? err.message : String(err);
        vscode.window.showErrorMessage(`Local Copilot: ${message}`);
      }
    }
  );
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("localCopilot.reviewWorkingTree", () =>
      runReview("Review: Uncommitted Changes", getWorkingTreeDiff)
    ),
    vscode.commands.registerCommand("localCopilot.reviewStaged", () =>
      runReview("Review: Staged Changes", getStagedDiff)
    ),
    vscode.commands.registerCommand("localCopilot.reviewRef", async () => {
      const ref = await vscode.window.showInputBox({
        prompt: "Git ref to diff against (e.g. HEAD~1, main, a1b2c3d)",
        placeHolder: "HEAD~1",
      });
      if (!ref) {
        return;
      }
      await runReview(`Review: diff against ${ref}`, () => getRefDiff(ref));
    })
  );
}

export function deactivate(): void {}
