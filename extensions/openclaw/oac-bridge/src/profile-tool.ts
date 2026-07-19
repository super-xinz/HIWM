import fs from "node:fs";
import path from "node:path";
import { Type } from "@sinclair/typebox";

const GetAgentProfileSchema = Type.Object(
  {
    sections: Type.Optional(
      Type.Array(Type.String(), {
        description:
          '需要包含的部分："identity"、"soul"、"user"；默认包含全部。',
      }),
    ),
  },
  { additionalProperties: false },
);

const SECTION_FILES: Record<string, { file: string; heading: string }> = {
  identity: { file: "IDENTITY.md", heading: "## 身份" },
  soul: { file: "SOUL.md", heading: "## 性格" },
  user: { file: "USER.md", heading: "## 用户偏好" },
};

function readWorkspaceFile(workspaceDir: string, filename: string): string {
  const filePath = path.join(workspaceDir, filename);
  try {
    if (fs.existsSync(filePath)) {
      return fs.readFileSync(filePath, "utf-8").trim();
    }
  } catch {
    // File not readable — skip silently
  }
  return "";
}

export function createGetAgentProfileTool(options: { workspaceDir?: string }) {
  const { workspaceDir } = options;

  return {
    name: "get_agent_profile",
    label: "获取智能体资料",
    description:
      "从工作区文件（IDENTITY.md、SOUL.md、USER.md）读取智能体身份、性格和用户偏好，" +
      "并返回 Markdown。当不确定智能体的名字、角色、用户偏好的称呼或其他资料时使用。",
    parameters: GetAgentProfileSchema,
    execute: async (
      _toolCallId: string,
      rawParams: Record<string, unknown>,
    ) => {
      if (!workspaceDir) {
        return {
          content: [
            {
              type: "text" as const,
              text: "暂时无法获取智能体资料：尚未配置工作区目录。",
            },
          ],
        };
      }

      const requestedSections = Array.isArray(rawParams.sections)
        ? (rawParams.sections as string[])
        : Object.keys(SECTION_FILES);

      const parts: string[] = ["# 智能体资料\n"];

      for (const key of requestedSections) {
        const def = SECTION_FILES[key];
        if (!def) continue;
        const content = readWorkspaceFile(workspaceDir, def.file);
        if (content) {
          parts.push(`${def.heading}\n\n${content}\n`);
        }
      }

      const markdown =
        parts.length > 1 ? parts.join("\n") : "工作区中未找到资料文件。";

      return { content: [{ type: "text" as const, text: markdown }] };
    },
  };
}
