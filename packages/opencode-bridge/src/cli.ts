import { OpencodeBridge } from "./client.js"

type CommandName =
  | "health"
  | "create_session"
  | "list_sessions"
  | "get_session"
  | "get_session_status"
  | "get_messages"
  | "get_session_usage"
  | "prompt_text"
  | "prompt_async"
  | "prompt_structured"
  | "subscribe_events"
  | "abort_session"
  | "delete_session"

type JsonObject = Record<string, unknown>

function asObject(value: unknown): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {}
  }
  return value as JsonObject
}

async function run(): Promise<void> {
  const command = process.argv[2] as CommandName | undefined
  const rawPayload = process.argv[3] ?? "{}"
  const payload = asObject(JSON.parse(rawPayload))

  if (!command) {
    throw new Error("Missing bridge command.")
  }

  const bridge = await OpencodeBridge.create({
    baseUrl: typeof payload.baseUrl === "string" ? payload.baseUrl : undefined,
    config: payload.config && typeof payload.config === "object" ? asObject(payload.config) : undefined,
    hostname: typeof payload.hostname === "string" ? payload.hostname : undefined,
    port: typeof payload.port === "number" ? payload.port : undefined,
    startServer:
      typeof payload.startServer === "boolean" ? payload.startServer : undefined,
  })

  try {
    let result: unknown
    switch (command) {
      case "health":
        result = await bridge.health()
        break
      case "create_session":
        result = await bridge.createSession({
          title: String(payload.title ?? "ABRIS Session"),
          directory:
            typeof payload.directory === "string" ? payload.directory : undefined,
          workspaceId:
            typeof payload.workspaceId === "string" ? payload.workspaceId : undefined,
        })
        break
      case "list_sessions":
        result = await bridge.listSessions()
        break
      case "get_session":
        result = await bridge.getSession(String(payload.session_id ?? ""))
        break
      case "get_session_status":
        result = await bridge.getSessionStatus()
        break
      case "get_messages":
        result = await bridge.getMessages(String(payload.session_id ?? ""))
        break
      case "get_session_usage":
        result = await bridge.getSessionUsage(String(payload.session_id ?? ""))
        break
      case "prompt_text":
        result = await bridge.promptText(
          String(payload.session_id ?? ""),
          String(payload.text ?? "")
        )
        break
      case "prompt_async":
        result = await bridge.promptAsync(
          String(payload.session_id ?? ""),
          String(payload.text ?? "")
        )
        break
      case "prompt_structured":
        result = await bridge.promptStructured(
          String(payload.session_id ?? ""),
          String(payload.text ?? ""),
          asObject(payload.format) as {
            type: "json_schema"
            schema: Record<string, unknown>
            retryCount?: number
          }
        )
        break
      case "subscribe_events":
        result = await bridge.subscribeEvents({
          limit: typeof payload.limit === "number" ? payload.limit : undefined,
          timeoutMs:
            typeof payload.timeout_ms === "number" ? payload.timeout_ms : undefined,
        })
        break
      case "abort_session":
        result = await bridge.abortSession(String(payload.session_id ?? ""))
        break
      case "delete_session":
        result = await bridge.deleteSession(String(payload.session_id ?? ""))
        break
      default:
        throw new Error(`Unsupported bridge command: ${command}`)
    }

    process.stdout.write(`${JSON.stringify(result)}\n`)
  } finally {
    bridge.close()
  }
}

run().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error)
  process.stderr.write(`${message}\n`)
  process.exitCode = 1
})
