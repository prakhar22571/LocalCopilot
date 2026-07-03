import * as http from "http";
import * as https from "https";
import { URL } from "url";

export interface CodeReview {
  change_type: string;
  summary: string;
  risk_level: "low" | "medium" | "high";
  suggested_tests: string[];
}

export interface ReviewMetrics {
  model: string;
  wall_clock_seconds: number;
  tokens_per_second: number;
  retries: number;
  [key: string]: unknown;
}

export interface ReviewResponse {
  review: CodeReview;
  metrics: ReviewMetrics;
}

export class ReviewClientError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
  }
}

function request(url: URL, body: string, timeoutMs: number): Promise<{ status: number; body: string }> {
  const transport = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = transport.request(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Content-Length": Buffer.byteLength(body, "utf-8"),
        },
        timeout: timeoutMs,
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          resolve({ status: res.statusCode ?? 0, body: Buffer.concat(chunks).toString("utf-8") });
        });
      }
    );
    req.on("timeout", () => req.destroy(new Error("Request timed out")));
    req.on("error", reject);
    req.write(body, "utf-8");
    req.end();
  });
}

export async function checkHealth(serverUrl: string): Promise<boolean> {
  return new Promise((resolve) => {
    const url = new URL("/health", serverUrl);
    const transport = url.protocol === "https:" ? https : http;
    const req = transport.get(url, { timeout: 3000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

export async function reviewDiff(
  serverUrl: string,
  diff: string,
  model: string,
  temperature: number
): Promise<ReviewResponse> {
  const url = new URL("/review", serverUrl);
  const payload = JSON.stringify({ diff, model, temperature });

  let response: { status: number; body: string };
  try {
    response = await request(url, payload, 300_000);
  } catch (err) {
    throw new ReviewClientError(
      `Could not reach Local Copilot server at ${serverUrl}. Is it running? Start it with: uvicorn app.api:app`,
      err
    );
  }

  if (response.status === 422) {
    const detail = safeJsonDetail(response.body);
    throw new ReviewClientError(`Model could not produce a valid review after retries: ${detail}`);
  }
  if (response.status !== 200) {
    throw new ReviewClientError(`Server returned ${response.status}: ${response.body.slice(0, 500)}`);
  }

  try {
    return JSON.parse(response.body) as ReviewResponse;
  } catch (err) {
    throw new ReviewClientError("Server response was not valid JSON.", err);
  }
}

function safeJsonDetail(body: string): string {
  try {
    const parsed = JSON.parse(body);
    return typeof parsed.detail === "string" ? parsed.detail : body;
  } catch {
    return body;
  }
}
