import { Type } from "@sinclair/typebox";

const ListScheduledTasksSchema = Type.Object(
  {
    include_disabled: Type.Optional(
      Type.Boolean({
        description: "是否包含已禁用的任务（默认：false）。",
      }),
    ),
  },
  { additionalProperties: false },
);

export function createListScheduledTasksTool() {
  return {
    name: "list_scheduled_tasks",
    label: "查看定时任务",
    description:
      "列出当前有效的定时任务和计划任务，并返回 Markdown。" +
      "当用户询问已布置的任务、提醒或周期性日程时使用。",
    parameters: ListScheduledTasksSchema,
    execute: async (
      _toolCallId: string,
      rawParams: Record<string, unknown>,
    ) => {
      const includeDisabled = rawParams.include_disabled === true;

      let store: { jobs?: unknown[] } | null = null;
      try {
        const { loadCronStore, resolveCronStorePath } = await import(
          "openclaw/plugin-sdk/config-runtime"
        );
        const storePath = resolveCronStorePath();
        store = await loadCronStore(storePath);
      } catch {
        return {
          content: [
            {
              type: "text" as const,
              text: "暂时无法获取定时任务：无法加载计划任务存储。",
            },
          ],
        };
      }

      if (!store || !Array.isArray(store.jobs) || store.jobs.length === 0) {
        return {
          content: [{ type: "text" as const, text: "未找到定时任务。" }],
        };
      }

      const lines: string[] = ["# 定时任务\n"];

      for (const job of store.jobs as Record<string, unknown>[]) {
        const enabled = job.enabled !== false;
        if (!includeDisabled && !enabled) continue;

        const name = (job.name as string) || "未命名任务";
        const schedule = (job.schedule as Record<string, unknown>) || {};
        const expr = (schedule.expr as string) || "";
        const tz = (schedule.tz as string) || "";
        const payload = (job.payload as Record<string, unknown>) || {};
        const message =
          (payload.message as string) || (payload.text as string) || "";
        const state = (job.state as Record<string, unknown>) || {};
        const lastStatus = (state.lastRunStatus as string) || "unknown";
        const lastError = (state.lastError as string) || "";

        const statusIcon = enabled ? "✅" : "⏸️";
        lines.push(`${statusIcon} **${name}**`);
        lines.push(`- 执行计划：\`${expr}\`（${tz || "系统时区"}）`);
        if (message) {
          lines.push(`- 消息：${message}`);
        }
        lines.push(
          `- 上次运行：${lastStatus}${lastError ? ` — ${lastError}` : ""}`,
        );
        lines.push("");
      }

      const markdown = lines.length > 1 ? lines.join("\n") : "未找到定时任务。";

      return { content: [{ type: "text" as const, text: markdown }] };
    },
  };
}
