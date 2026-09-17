/**
 * tests/frontend/CopilotChat.test.jsx
 * ------------------------------------
 * Basic render tests for CopilotChat component.
 *
 * Requires: pnpm add -D vitest @testing-library/react @testing-library/jest-dom
 * Run: cd frontend && pnpm vitest run ../tests/frontend/CopilotChat.test.jsx
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// Mock wouter
vi.mock('wouter', () => ({
  useLocation: () => ['/copilot', vi.fn()],
  Link: ({ children, ...props }) => <a {...props}>{children}</a>,
}));

// Mock the copilot API
vi.mock('@/api/copilot', () => ({
  askCopilot: vi.fn(),
  getDemoQueries: vi.fn().mockResolvedValue([
    { query: 'Find all entities connected to Person-001', description: 'Explore connections' },
    { query: 'What financial flows exist?', description: 'Financial analysis' },
    { query: 'Show communication patterns', description: 'Comms overview' },
    { query: 'Identify ghost nodes', description: 'Anomaly detection' },
  ]),
  getTools: vi.fn().mockResolvedValue([]),
}));

import CopilotChat from '@/components/CopilotChat';
import ToolCallTrace from '@/components/ToolCallTrace';
import { getDemoQueries, askCopilot } from '@/api/copilot';

describe('CopilotChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<CopilotChat />);
    expect(screen.getByPlaceholderText(/Ask about the network/)).toBeTruthy();
  });

  it('shows demo query cards when message history is empty', async () => {
    render(<CopilotChat />);
    await waitFor(() => {
      expect(screen.getByText(/Ask a question/)).toBeTruthy();
    });
    // Should show demo queries
    const demoCards = screen.getAllByText(/Find all entities|What financial|Show communication|Identify ghost/);
    expect(demoCards.length).toBeGreaterThanOrEqual(1);
  });

  it('shows ToolCallTrace collapsed after mocked copilot response', async () => {
    askCopilot.mockResolvedValue({
      answer: 'Found 3 paths.',
      tools_used: [{ name: 'find_paths', input: { from: 'E-aaa', to: 'E-bbb' }, output: { paths: 3 } }],
      confidence: 0.85,
      warnings: [],
    });

    render(<CopilotChat />);

    // Type and send
    const input = screen.getByPlaceholderText(/Ask about the network/);
    fireEvent.change(input, { target: { value: 'Find paths between A and B' } });
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByText('Found 3 paths.')).toBeTruthy();
    });

    // ToolCallTrace should show tool count
    expect(screen.getByText(/Tool calls \(1\)/)).toBeTruthy();
  });
});

describe('ToolCallTrace', () => {
  it('renders nothing when no tool calls', () => {
    const { container } = render(<ToolCallTrace toolCalls={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders tool call names', () => {
    render(
      <ToolCallTrace
        toolCalls={[
          { name: 'find_paths', input: { from: 'E-abc' }, output: { count: 3 } },
          { name: 'centrality', input: { node: 'E-abc' }, output: { score: 0.5 } },
        ]}
      />,
    );
    expect(screen.getByText('find_paths')).toBeTruthy();
    expect(screen.getByText('centrality')).toBeTruthy();
  });
});
