import HttpService from "./htttp.service";
import { getAuthToken } from "./api-client";

export const setupAxiosInterceptors = () => {
  const onRequestSuccess = (config) => {
    const token = getAuthToken();
    config.headers = config.headers || {};

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      delete config.headers.Authorization;
    }

    // Keep the credential used by this request so a stale 401 cannot
    // terminate a newer session established in another tab.
    config.__meditrustAuthToken = token;
    return config;
  };
  const onRequestFail = (error) => Promise.reject(error);

  const requestId = HttpService.addRequestInterceptor(onRequestSuccess, onRequestFail);

  const onResponseSuccess = (response) => response;
  const onResponseFail = (error) => {
    const status = error?.response?.status ?? error?.status;
    const requestToken = error?.config?.__meditrustAuthToken;
    const currentToken = getAuthToken();

    // 403 means authenticated but forbidden; it must not log the user out.
    // A 401 only invalidates the session if it belongs to the current token.
    if (status === 401 && requestToken && requestToken === currentToken) {
      window.dispatchEvent(new Event("meditrust:session-invalid"));
    }

    return Promise.reject(error);
  };
  const responseId = HttpService.addResponseInterceptor(onResponseSuccess, onResponseFail);

  return () => {
    HttpService._axios.interceptors.request.eject(requestId);
    HttpService._axios.interceptors.response.eject(responseId);
  };
};
