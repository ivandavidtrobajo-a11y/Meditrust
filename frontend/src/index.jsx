
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import { AuthContextProvider, MaterialUIControllerProvider } from "@/context";
import { setupAxiosInterceptors } from "./services/interceptor";

// Register authentication interceptors before AuthContext performs its initial /me request.
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