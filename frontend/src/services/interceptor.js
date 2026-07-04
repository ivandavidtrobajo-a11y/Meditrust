import HttpService from "./htttp.service";

export const setupAxiosInterceptors = (onUnauthenticated) => {
  const onRequestSuccess = async (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  };
  const onRequestFail = (error) => Promise.reject(error);

  HttpService.addRequestInterceptor(onRequestSuccess, onRequestFail);

  const onResponseSuccess = (response) => response;

  const onResponseFail = (error) => {
    // ✅ SOLUCIÓN: Usar optional chaining (?.) para acceso seguro
    // Antes: const status = error.status || error.response.status;
    // Problema: Si error.response es undefined, explota
    // Después: error?.response?.status solo devuelve undefined, no explota
    const status = error?.response?.status;
    
    if (status === 403 || status === 401) {
      onUnauthenticated();
    }

    // ✅ Logging mejorado para debugging
    console.error("HTTP Error Details:", {
      status: status || "Sin status",
      message: error?.message || "Sin mensaje",
      hasResponse: !!error?.response,
      hasRequest: !!error?.request,
      errorData: error?.data,
    });

    return Promise.reject(error);
  };
  HttpService.addResponseInterceptor(onResponseSuccess, onResponseFail);
};
