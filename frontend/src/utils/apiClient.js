import { API_BASE } from "./config";

function logoutAndRedirect() {
  try {
    sessionStorage.removeItem("sv_access_token");
    sessionStorage.removeItem("sv_refresh_token");
    sessionStorage.removeItem("sv_master_key");
  } catch (e) {}
  // Best-effort redirect to root/login
  try {
    window.location.href = "/";
  } catch (e) {}
}

export async function apiFetch(path, options = {}, retry = true) {
  const url = path.startsWith("/") ? `${API_BASE}${path}` : path;
  const access = sessionStorage.getItem("sv_access_token");
  const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  if (access) headers["Authorization"] = `Bearer ${access}`;

  let res = await fetch(url, Object.assign({}, options, { headers }));

  if (res.status !== 401) {
    return res;
  }

  if (!retry) return res;

  // Attempt refresh
  const refresh = sessionStorage.getItem("sv_refresh_token");
  if (!refresh) {
    logoutAndRedirect();
    throw new Error("No refresh token available");
  }

  try {
    const refreshRes = await fetch(`${API_BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });

    if (!refreshRes.ok) {
      logoutAndRedirect();
      throw new Error("Refresh failed");
    }

    const data = await refreshRes.json();
    const newAccess = data.access || data.token || data.access_token;
    if (!newAccess) {
      logoutAndRedirect();
      throw new Error("No access token returned from refresh");
    }

    sessionStorage.setItem("sv_access_token", newAccess);

    // retry original request once
    const retryHeaders = Object.assign({}, headers, { Authorization: `Bearer ${newAccess}` });
    res = await fetch(url, Object.assign({}, options, { headers: retryHeaders }));
    return res;
  } catch (err) {
    logoutAndRedirect();
    throw err;
  }
}
