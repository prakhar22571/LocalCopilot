import { execFile } from "child_process";
import * as vscode from "vscode";

const MAX_BUFFER = 20 * 1024 * 1024; // 20MB, generous for even large diffs

export class GitError extends Error {}

function runGitDiff(cwd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      "git",
      ["diff", ...args],
      { cwd, maxBuffer: MAX_BUFFER, encoding: "utf-8" },
      (error, stdout, stderr) => {
        if (error) {
          reject(new GitError(stderr || error.message));
          return;
        }
        resolve(stdout);
      }
    );
  });
}

async function resolveWorkspaceRoot(): Promise<string> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    throw new GitError("No folder is open in this workspace.");
  }
  if (folders.length === 1) {
    return folders[0].uri.fsPath;
  }
  const pick = await vscode.window.showWorkspaceFolderPick({
    placeHolder: "Select the repository to review",
  });
  if (!pick) {
    throw new GitError("No repository selected.");
  }
  return pick.uri.fsPath;
}

export async function getWorkingTreeDiff(): Promise<string> {
  const root = await resolveWorkspaceRoot();
  return runGitDiff(root, ["HEAD"]);
}

export async function getStagedDiff(): Promise<string> {
  const root = await resolveWorkspaceRoot();
  return runGitDiff(root, ["--staged"]);
}

export async function getRefDiff(ref: string): Promise<string> {
  const root = await resolveWorkspaceRoot();
  return runGitDiff(root, [ref]);
}
