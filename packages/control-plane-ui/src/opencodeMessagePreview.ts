import type { SessionMessage, SessionMessagePart, SessionMessageUsage } from "./api"

export type MessagePreviewInfo = {
  body: string
  meta?: string
}

function compactText(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined
}

function readStringField(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }
  return undefined
}

function readNumberField(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "number" && Number.isFinite(value)) {
      return value
    }
  }
  return undefined
}

function extractStructuredText(value: unknown, depth = 0): string[] {
  if (depth > 3 || value == null) {
    return []
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed ? [trimmed] : []
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => extractStructuredText(item, depth + 1))
  }

  if (typeof value === "object") {
    const record = asRecord(value)
    if (!record) {
      return []
    }
    const directText = [
      readStringField(record, ["text", "content", "summary", "reasoning", "description", "title"]),
      readStringField(record, ["query", "result", "output"]),
    ].filter((item): item is string => Boolean(item))

    return [
      ...directText,
      ...extractStructuredText(record.parts, depth + 1),
      ...extractStructuredText(record.payload, depth + 1),
      ...extractStructuredText(record.arguments, depth + 1),
      ...extractStructuredText(record.input, depth + 1),
      ...extractStructuredText(record.result, depth + 1),
    ]
  }

  return []
}

function summarizeStructuredParts(parts: SessionMessagePart[] | unknown) {
  if (!Array.isArray(parts)) {
    return []
  }

  const labels = parts.flatMap((part): string[] => {
    const record = asRecord(part)
    if (!record) {
      return []
    }
    const partType = readStringField(record, ["type", "kind", "event_type", "eventType"])
    const toolName = readStringField(record, ["tool_name", "toolName", "name"])

    if (partType && toolName) {
      return [`${partType}:${toolName}`]
    }
    if (toolName) {
      return [`tool:${toolName}`]
    }
    if (partType) {
      return [partType]
    }
    if (readStringField(record, ["text", "content", "summary"])) {
      return ["text"]
    }
    return []
  })

  return Array.from(new Set(labels)).slice(0, 4)
}

function formatUsageSummary(usage: SessionMessageUsage | unknown) {
  const record = asRecord(usage)
  if (!record) {
    return undefined
  }
  const totalTokens = readNumberField(record, ["total_tokens", "totalTokens"])
  const inputTokens = readNumberField(record, ["input_tokens", "inputTokens", "prompt_tokens", "promptTokens"])
  const outputTokens = readNumberField(record, ["output_tokens", "outputTokens", "completion_tokens", "completionTokens"])
  const parts: string[] = []

  if (typeof totalTokens === "number" && totalTokens > 0) {
    parts.push(`tokens ${Math.trunc(totalTokens)}`)
  }
  if (typeof inputTokens === "number" || typeof outputTokens === "number") {
    parts.push(`in ${Math.trunc(inputTokens ?? 0)} / out ${Math.trunc(outputTokens ?? 0)}`)
  }

  return parts.length ? parts.join(" · ") : undefined
}

export function buildMessagePreview(message: SessionMessage): MessagePreviewInfo {
  const record = asRecord(message)
  if (!record) {
    return { body: "结构化消息：未发现可展示文本" }
  }

  const fragments = Array.from(new Set([
    ...extractStructuredText(record.content),
    ...extractStructuredText(record.text),
    ...extractStructuredText(record.parts),
  ]))
  const partSummary = summarizeStructuredParts(record.parts)
  const usageSummary = formatUsageSummary(record.usage)
  const body = fragments[0]
    ? compactText(fragments[0], 220)
    : partSummary.length
      ? `结构化消息：${compactText(partSummary.join(" · "), 220)}`
      : "结构化消息：未发现可展示文本"
  const meta = [
    partSummary.length ? `parts ${partSummary.join(" / ")}` : undefined,
    usageSummary,
  ].filter((item): item is string => Boolean(item)).join(" · ")

  return meta ? { body, meta } : { body }
}
