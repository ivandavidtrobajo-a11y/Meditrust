// Authentication helpers shared by Axios and direct Fetch requests.
// sessionStorage keeps each browser tab's session independent.
export const getAuthToken = () => {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem("token");
};

export const authenticatedFetch = async (input, options = {}) => {
  const requestToken = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (requestToken) headers.set("Authorization", `Bearer ${requestToken}`);
  else headers.delete("Authorization");

  const response = await fetch(input, { ...options, headers });
  const currentToken = getAuthToken();

  // Match Axios behavior: forbidden requests do not invalidate a session.
  // A stale 401 must not terminate a newer login in the same tab.
  if (response.status === 401 && requestToken && requestToken === currentToken) {
    window.dispatchEvent(new Event("meditrust:session-invalid"));
  }

  return response;
};
