import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "@/context/AuthContext";
import { TenantCarrierProvider } from "@/context/TenantCarrierContext";
import App from "./App";

import "@/styles/tokens.css";
import "@/styles/typography.css";
import "@/styles/layout.css";
import "@/styles/components.css";
import "@/styles/utilities.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TenantCarrierProvider>
            <App />
          </TenantCarrierProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);
