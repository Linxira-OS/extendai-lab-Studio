import React from "react"
import ReactDOM from "react-dom/client"
import { App as AntApp } from "antd"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import App from "./App"
import { ThemeProvider } from "./components/ThemeProvider"
import "antd/dist/reset.css"
import "./styles.css"

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AntApp>
    </ThemeProvider>
  </React.StrictMode>,
)
