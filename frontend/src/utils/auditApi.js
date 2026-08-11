/**
 * auditApi.js — Ephemeral Secret Audit Client
 *
 * Sends a secret to POST /api/audit/ for heuristic analysis.
 * The server never saves the string — analysis is in-memory only.
 */

import { API_BASE } from "./config";
import { apiFetch } from "./apiClient";

/**
 * Audit a secret string via the Django heuristic engine.
 * Requires JWT authentication.
 *
 * @param {string} secret - The raw string to audit
 * @returns {Promise<Object>} Risk profile { identified_type, risk_level, risk_score, recommendations, details }
 */
export async function auditSecret(secret) {
  const res = await apiFetch(`/audit/`, {
    method: "POST",
    body: JSON.stringify({ secret }),
  });

  if (!res.ok) {
    throw new Error("Audit failed");
  }

  return res.json();
}
