import React, { createContext, useContext, useEffect, useState } from "react"
import { ConfigProvider, theme } from "antd"

export type ThemeMode = "system" | "time" | "light" | "dark"

interface ThemeContextType {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  isDark: boolean
}

export const ThemeContext = createContext<ThemeContextType>({
  mode: "system",
  setMode: () => {},
  isDark: true,
})

export function useTheme() {
  return useContext(ThemeContext)
}

function getSystemIsDark() {
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  }
  return true
}

function getTimeIsDark() {
  const hour = new Date().getHours()
  return hour < 7 || hour >= 19
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem("abris_theme_mode")
    if (saved && ["system", "time", "light", "dark"].includes(saved)) {
      return saved as ThemeMode
    }
    return "system"
  })

  const [isDark, setIsDark] = useState(true)

  useEffect(() => {
    localStorage.setItem("abris_theme_mode", mode)

    function updateTheme() {
      let dark = true
      if (mode === "light") {
        dark = false
      } else if (mode === "dark") {
        dark = true
      } else if (mode === "time") {
        dark = getTimeIsDark()
      } else if (mode === "system") {
        dark = getSystemIsDark()
      }

      setIsDark(dark)
      document.documentElement.setAttribute("data-theme", dark ? "dark" : "light")
    }

    updateTheme()

    if (mode === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
      const handler = () => updateTheme()
      mediaQuery.addEventListener("change", handler)
      return () => mediaQuery.removeEventListener("change", handler)
    }

    if (mode === "time") {
      const timer = setInterval(() => {
        updateTheme()
      }, 60000)
      return () => clearInterval(timer)
    }
  }, [mode])

  return (
    <ThemeContext.Provider value={{ mode, setMode, isDark }}>
      <ConfigProvider
        theme={{
          algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: {
            colorPrimary: "#3b82f6",
            colorInfo: "#3b82f6",
            borderRadius: 14,
            ...(isDark ? {
              colorBgBase: "#0f172a",
              colorBgContainer: "#1e293b",
              colorBorder: "rgba(148, 163, 184, 0.16)",
            } : {
              colorBgBase: "#f8fafc",
              colorBgContainer: "#ffffff",
              colorBorder: "rgba(0, 0, 0, 0.08)",
            }),
          },
        }}
      >
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}
