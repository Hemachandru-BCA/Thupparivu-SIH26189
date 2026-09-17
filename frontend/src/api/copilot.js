/**
 * api/copilot.js
 * ---------------
 * Investigation Copilot API client.
 */

import { requestJson } from '@/api/client';

/**
 * Ask the copilot a natural-language investigation question.
 * @param {string} query - The natural-language query
 * @param {string} sessionId - UUID session identifier
 * @returns {Promise<{answer, tools_used, tool_results, confidence, warnings}>}
 */
export async function askCopilot(query, sessionId) {
  return requestJson('/api/copilot/ask', {
    method: 'POST',
    body: { query, session_id: sessionId },
  });
}

/**
 * List all available copilot tools.
 * @returns {Promise<Array<{name, description, category, example_query}>>}
 */
export async function getTools() {
  return requestJson('/api/copilot/tools');
}

/**
 * Get demo query suggestions for the empty-chat state.
 * @returns {Promise<Array<{query, description, category}>>}
 */
export async function getDemoQueries() {
  return requestJson('/api/copilot/demo-queries');
}

/**
 * Get copilot status (for polling during tool execution).
 * @returns {Promise<{status, tools_available, provider}>}
 */
export async function getCopilotStatus() {
  return requestJson('/api/copilot/status');
}
