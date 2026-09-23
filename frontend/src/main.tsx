import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { reloadForNewVersion } from "./lib/staleBuild";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

// Vite урьдчилан ачаалах файл олдоогүй (шинэ хувилбар гарсан) — дахин ачаална.
window.addEventListener("vite:preloadError", (event) => {
  if (reloadForNewVersion()) event.preventDefault();
});

const container = document.getElementById("root");
if (!container) {
  throw new Error("#root элемент олдсонгүй");
}

createRoot(container).render(
  <StrictMode>
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </AppErrorBoundary>
  </StrictMode>,
);
