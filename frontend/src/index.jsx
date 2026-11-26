
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import { AuthContextProvider, MaterialUIControllerProvider } from "@/context";
import { setupAxiosInterceptors } from "./services/interceptor";

// Each tab owns an independent authentication session through sessionStorage.
// Register authentication interceptors before any authenticated request can run.
setupAxiosInterceptors();

const rootElement = document.getElementById("root");
const root = createRoot(rootElement);

root.render(
  <BrowserRouter>
    <AuthContextProvider>
      <MaterialUIControllerProvider>
        <App />
      </MaterialUIControllerProvider>
    </AuthContextProvider>
  </BrowserRouter>
);