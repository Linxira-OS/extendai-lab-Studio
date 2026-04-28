import { createOpencode, createOpencodeClient } from "@opencode-ai/sdk"

export type StructuredPromptSchema = {
  type: "json_schema"
  schema: Record<string, unknown>
  retryCount?: number
}

export type BridgeClientOptions = {
  baseUrl?: string
  hostname?: string
  port?: number
  startServer?: boolean
  config?: Record<string, unknown>
}

export type BridgeSessionOptions = {
  title: string
  directory?: string
  workspaceId?: string
}

export class OpencodeBridge {
  private constructor(private readonly client: any, private readonly server?: { close(): void }) {}

  private normalizeUsage(value: unknown) {
    const usage = value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {}
    return {
      input_tokens: this.readNumber(usage, ["input_tokens", "inputTokens", "prompt_tokens", "promptTokens"]),
      output_tokens: this.readNumber(usage, ["output_tokens", "outputTokens", "completion_tokens", "completionTokens"]),
      total_tokens: this.readNumber(usage, ["total_tokens", "totalTokens"]),
      cost: this.readFloat(usage, ["cost", "estimatedCost"]),
      message_count: this.readNumber(usage, ["message_count", "messageCount"]),
      prompt_count: this.readNumber(usage, ["prompt_count", "promptCount"]),
    }
  }

  private normalizeEvent(event: unknown) {
    const raw = event && typeof event === "object" && !Array.isArray(event)
      ? (event as Record<string, unknown>)
      : {}
    const payload = raw.payload && typeof raw.payload === "object" && !Array.isArray(raw.payload)
      ? (raw.payload as Record<string, unknown>)
      : raw
    return {
      id: raw.id ?? raw.event_id ?? undefined,
      session_id: raw.session_id ?? raw.sessionID ?? raw.sessionId ?? payload.session_id ?? payload.sessionID ?? payload.sessionId ?? undefined,
      type: raw.type ?? raw.event_type ?? raw.eventType ?? raw.name ?? "unknown",
      timestamp: raw.timestamp ?? raw.createdAt ?? raw.time ?? payload.timestamp ?? payload.createdAt ?? payload.time ?? "",
      payload,
    }
  }

  private readNumber(payload: Record<string, unknown>, keys: string[]) {
    for (const key of keys) {
      const value = payload[key]
      if (typeof value === "number" && Number.isFinite(value)) {
        return Math.trunc(value)
      }
    }
    return 0
  }

  private readFloat(payload: Record<string, unknown>, keys: string[]) {
    for (const key of keys) {
      const value = payload[key]
      if (typeof value === "number" && Number.isFinite(value)) {
        return value
      }
    }
    return 0
  }

  static async create(options: BridgeClientOptions = {}): Promise<OpencodeBridge> {
    if (options.startServer ?? !options.baseUrl) {
      const runtimeOptions: Record<string, unknown> = {}
      if (typeof options.hostname === "string") {
        runtimeOptions.hostname = options.hostname
      }
      if (typeof options.port === "number") {
        runtimeOptions.port = options.port
      }
      if (options.config) {
        runtimeOptions.config = options.config
      }

      const runtime = await createOpencode(runtimeOptions)
      return new OpencodeBridge(runtime.client, runtime.server)
    }

    const client = createOpencodeClient({
      baseUrl: options.baseUrl,
    })
    return new OpencodeBridge(client)
  }

  async health() {
    return this.client.global.health()
  }

  async listAgents() {
    return this.client.app.agents()
  }

  async createSession(options: BridgeSessionOptions) {
    const body: Record<string, unknown> = { title: options.title }
    if (options.directory) {
      body.directory = options.directory
    }
    if (options.workspaceId) {
      body.workspaceID = options.workspaceId
    }
    return this.client.session.create({ body })
  }

  async getSession(sessionId: string) {
    return this.client.session.get({ path: { id: sessionId } })
  }

  async getSessionStatus() {
    return this.client.session.status()
  }

  async listSessions() {
    const listMethod = this.client.session.list
    if (typeof listMethod === "function") {
      const result = await listMethod.call(this.client.session)
      const sessions = Array.isArray(result?.sessions)
        ? result.sessions
        : Array.isArray(result)
          ? result
          : []
      return { sessions }
    }

    const status = await this.getSessionStatus()
    if (Array.isArray(status?.sessions)) {
      return { sessions: status.sessions }
    }
    if (Array.isArray(status?.status)) {
      return { sessions: status.status }
    }
    if (status?.status && Array.isArray(status.status.sessions)) {
      return { sessions: status.status.sessions }
    }
    return { sessions: [] }
  }

  async getMessages(sessionId: string) {
    return this.client.session.messages({ path: { id: sessionId } })
  }

  async getSessionUsage(sessionId: string) {
    const response = await this.getMessages(sessionId)
    const messages = Array.isArray(response?.messages) ? response.messages : []
    const usage = {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost: 0,
      message_count: messages.length,
      prompt_count: 0,
    }

    for (const message of messages) {
      if (!message || typeof message !== "object") {
        continue
      }
      if ((message as Record<string, unknown>).role === "user") {
        usage.prompt_count += 1
      }
      const rawUsage = (message as Record<string, unknown>).usage
      const normalized = this.normalizeUsage(rawUsage)
      usage.input_tokens += normalized.input_tokens
      usage.output_tokens += normalized.output_tokens
      usage.total_tokens += normalized.total_tokens
      usage.cost += normalized.cost
    }

    if (usage.total_tokens === 0) {
      usage.total_tokens = usage.input_tokens + usage.output_tokens
    }

    return { usage }
  }

  async promptText(sessionId: string, text: string) {
    return this.client.session.prompt({
      path: { id: sessionId },
      body: {
        parts: [{ type: "text", text }],
      },
    })
  }

  async promptAsync(sessionId: string, text: string) {
    await this.client.session.promptAsync({
      path: { id: sessionId },
      body: {
        parts: [{ type: "text", text }],
      },
    })
    return { accepted: true }
  }

  async promptStructured(sessionId: string, text: string, format: StructuredPromptSchema) {
    return this.client.session.prompt({
      path: { id: sessionId },
      body: {
        parts: [{ type: "text", text }],
        format,
      },
    })
  }

  async subscribeEvents(options: { limit?: number; timeoutMs?: number } = {}) {
    const events = await this.client.event.subscribe()
    const stream = events.stream as AsyncIterable<{ type?: string; [key: string]: unknown }>
    const iterator = stream[Symbol.asyncIterator]()
    const limit = options.limit ?? 10
    const timeoutMs = options.timeoutMs ?? 1000
    const collected: Array<Record<string, unknown>> = []
    const deadline = Date.now() + timeoutMs

    while (collected.length < limit && Date.now() < deadline) {
      const remaining = deadline - Date.now()
      const nextEvent = await Promise.race([
        iterator.next(),
        new Promise<{ done: true; value?: undefined }>((resolve) => {
          setTimeout(() => resolve({ done: true }), Math.max(remaining, 0))
        }),
      ])

      if (nextEvent.done || !nextEvent.value) {
        break
      }

      collected.push(this.normalizeEvent(nextEvent.value))
    }

    return { events: collected, completed: collected.length >= limit }
  }

  async abortSession(sessionId: string) {
    return this.client.session.abort({ path: { id: sessionId } })
  }

  async deleteSession(sessionId: string) {
    return this.client.session.delete({ path: { id: sessionId } })
  }

  close() {
    this.server?.close()
  }
}
