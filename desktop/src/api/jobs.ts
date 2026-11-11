import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { z } from "zod";

export const RenameFormatSchema = z.enum([
  "artist_title",
  "title",
  "track_artist_title",
]);
export type RenameFormat = z.infer<typeof RenameFormatSchema>;

export const OperationSchema = z.enum([
  "rename", "lyrics", "covers", "recognize", "albums", "revert",
]);
export type Operation = z.infer<typeof OperationSchema>;

const SessionIdSchema = z.string().uuid().brand<"SessionId">();
export type SessionId = z.infer<typeof SessionIdSchema>;

export function createSessionId(): SessionId {
  return SessionIdSchema.parse(crypto.randomUUID());
}

const PreviewFileSchema = z.object({
  path: z.string(),
  current_name: z.string(),
  target_path: z.string().nullable(),
  target_name: z.string().nullable(),
  action: z.string(),
  reason: z.string().nullable(),
  before: z.record(z.string(), z.unknown()).optional(),
  planned_after: z.record(z.string(), z.unknown()).optional(),
});

export type PreviewFile = z.infer<typeof PreviewFileSchema>;

const EventFields = {
  v: z.literal(1),
  job_id: z.string().min(1),
};

const WorkerEventSchema = z.union([
  z.object({ ...EventFields, type: z.literal("accepted"), operation: OperationSchema }),
  z.object({
    ...EventFields,
    type: z.literal("preview"),
    operation: OperationSchema,
    preview_token: z.string().regex(/^[0-9a-f]{64}$/),
    total_files: z.number().int().nonnegative(),
    planned_changes: z.number().int().nonnegative(),
    skipped_files: z.number().int().nonnegative(),
    unchanged_files: z.number().int().nonnegative(),
    files: z.array(PreviewFileSchema),
  }),
  z.object({
    ...EventFields,
    type: z.literal("progress"),
    phase: z.enum(["scan", "rename", "revert", "process", "move"]),
    path: z.string(),
    completed: z.number().int().nonnegative(),
    total: z.number().int().nonnegative(),
  }),
  z.object({
    ...EventFields,
    type: z.literal("file_result"),
    path: z.string(),
    result: z.record(z.string(), z.unknown()),
  }),
  z.object({
    ...EventFields,
    type: z.literal("confirmation_required"),
    confirmation_id: z.string().min(1),
    message: z.string(),
    renamed: z.number().int().nonnegative(),
  }),
  z.object({ ...EventFields, type: z.literal("warning"), message: z.string() }),
  z.object({ ...EventFields, type: z.literal("error"), message: z.string() }),
  z.object({
    ...EventFields,
    type: z.literal("completed"),
    outcome: z.enum(["success", "partial"]),
    total_files: z.number().int().nonnegative(),
    changed_files: z.number().int().nonnegative(),
    errors: z.number().int().nonnegative(),
  }),
  z.object({
    ...EventFields,
    type: z.literal("completed"),
    outcome: z.literal("cancelled"),
    changed_files: z.number().int().nonnegative(),
    retained_changes: z.boolean(),
  }),
  z.object({
    ...EventFields,
    type: z.literal("completed"),
    outcome: z.literal("failed"),
    total_files: z.number().int().nonnegative(),
    changed_files: z.number().int().nonnegative(),
    errors: z.number().int().nonnegative(),
  }),
  z.object({
    ...EventFields,
    type: z.literal("completed"),
    outcome: z.literal("reverted"),
    total_files: z.number().int().nonnegative(),
    changed_files: z.number().int().nonnegative(),
    errors: z.number().int().nonnegative(),
  }),
  z.object({ ...EventFields, type: z.literal("process_exit") }),
  z.object({ ...EventFields, type: z.literal("worker_protocol_error") }),
]);

export type WorkerEvent = z.infer<typeof WorkerEventSchema>;

type JobFields = {
  v: 1;
  job_id: string;
  session_id: SessionId;
  request: {
    operation: Operation;
    directory: string;
    recursive: boolean;
    options: Record<string, string | boolean>;
  };
};

export type JobRequest =
  | (JobFields & { type: "preview" })
  | (JobFields & { type: "start"; preview_token: string });

export type JobControl =
  | ({ v: 1; job_id: string } & { type: "pause" })
  | ({ v: 1; job_id: string } & { type: "resume" })
  | ({ v: 1; job_id: string } & { type: "cancel" })
  | ({ v: 1; job_id: string } & {
      type: "confirmation_response";
      confirmation_id: string;
      value: boolean;
    });

const HistorySummarySchema = z.object({
  session_id: SessionIdSchema,
  operation: OperationSchema,
  directory: z.string(),
  started_at: z.string().datetime({ offset: true }),
  finished_at: z.string().datetime({ offset: true }).nullable(),
  outcome: z.enum(["running", "previewed", "success", "partial", "cancelled", "failed", "reverted"]),
  total_files: z.number().int().nonnegative(),
  changed_files: z.number().int().nonnegative(),
  errors: z.number().int().nonnegative(),
  related_session_id: SessionIdSchema.nullable(),
});
export type HistorySummary = z.infer<typeof HistorySummarySchema>;

const HistoryDetailSchema = HistorySummarySchema.extend({
  options: z.record(z.string(), z.unknown()),
  files: z.array(z.object({
    ordinal: z.number().int().nonnegative(),
    path: z.string(),
    before: z.record(z.string(), z.unknown()),
    planned_after: z.record(z.string(), z.unknown()).nullable(),
    after: z.record(z.string(), z.unknown()).nullable(),
    outcome: z.string(),
    reason: z.string().nullable(),
    error: z.string().nullable(),
  })),
});
export type HistoryDetail = z.infer<typeof HistoryDetailSchema>;

const UtilityResultSchema = z.object({
  sessions: z.array(HistorySummarySchema).optional(),
  session: HistoryDetailSchema.nullable().optional(),
  configured: z.boolean().optional(),
  cleared: z.boolean().optional(),
  history_location: z.string().optional(),
});

async function utility(request: {
  action: string;
  key?: string;
  value?: string;
  session_id?: string;
  filters?: Record<string, string>;
}): Promise<z.infer<typeof UtilityResultSchema>> {
  const result: unknown = await invoke("worker_utility", {
    request: { v: 1, type: "utility", ...request },
  });
  return UtilityResultSchema.parse(result);
}

export async function listHistory(filters: Record<string, string> = {}): Promise<HistorySummary[]> {
  return (await utility({ action: "history_list", filters })).sessions ?? [];
}

export async function getHistory(sessionId: SessionId): Promise<HistoryDetail | null> {
  return (await utility({ action: "history_detail", session_id: sessionId })).session ?? null;
}

export async function clearHistory(): Promise<void> {
  await utility({ action: "history_clear" });
}

export async function getHistoryLocation(): Promise<string> {
  return (await utility({ action: "history_location" })).history_location ?? "";
}

export async function getCredentialStatus(): Promise<boolean> {
  return (await utility({ action: "credential_status", key: "acoustid" })).configured ?? false;
}

export async function saveCredential(value: string): Promise<boolean> {
  return (await utility({ action: "credential_save", key: "acoustid", value })).configured ?? false;
}

export async function deleteCredential(): Promise<void> {
  await utility({ action: "credential_delete", key: "acoustid" });
}

export async function startJob(request: JobRequest): Promise<void> {
  await invoke("start_job", { request });
}

export async function sendJobControl(control: JobControl): Promise<void> {
  await invoke("send_control", { control });
}

export function listenForJobEvents(
  onEvent: (event: WorkerEvent) => void,
  onInvalidEvent: () => void,
): Promise<UnlistenFn> {
  return listen<unknown>("job-event", ({ payload }) => {
    const parsed = WorkerEventSchema.safeParse(payload);
    if (parsed.success) onEvent(parsed.data);
    else onInvalidEvent();
  });
}
