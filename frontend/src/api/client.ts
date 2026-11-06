import type { DashboardOverview, Dataset, Job } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE?.trim() || "/api/v1").replace(
    /\/+$/,
    "",
);

export function artifactUrl(jobId: string, filename: string): string {
    return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(filename)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const body = await response.json();
            message = body.detail ?? body.message ?? message;
        } catch {
            // Keep the HTTP status message when the server did not return JSON.
        }
        throw new Error(message);
    }
    return response.json() as Promise<T>;
}

export const api = {
    health: () =>
        request<{ status: string; service: string; version: string }>(
            "/health",
        ),
    overview: () => request<DashboardOverview>("/dashboard/overview"),
    datasets: () => request<Dataset[]>("/datasets"),
    dataset: (id: string) => request<Dataset>(`/datasets/${id}`),
    preview: (id: string) =>
        request<{
            columns: string[];
            rows: Record<string, unknown>[];
            total_rows: number;
        }>(`/datasets/${id}/preview?limit=18`),
    upload: async (file: File) => {
        const form = new FormData();
        form.append("file", file);
        return request<Dataset>("/datasets/upload", {
            method: "POST",
            body: form,
        });
    },
    demo: () => request<Dataset>("/datasets/demo", { method: "POST" }),
    removeDataset: (id: string) =>
        request<{ deleted: boolean }>(`/datasets/${id}`, { method: "DELETE" }),
    startForecast: (
        id: string,
        config: {
            target_column: string;
            date_column: string;
            group_columns: string[];
            horizon: number;
            lookback: number;
            epochs: number;
            batch_size: number;
            hidden_size: number;
        },
    ) =>
        request<Job>(`/datasets/${id}/forecast`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config),
        }),
    job: (id: string) => request<Job>(`/jobs/${id}`),
    jobs: () => request<Job[]>("/jobs"),
};
