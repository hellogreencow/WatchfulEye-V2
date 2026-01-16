import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CommandCenterPage } from './CommandCenterPage';

// Ensure Command Center is enabled in test environment (no window.location localhost reliance).
beforeEach(() => {
  process.env.REACT_APP_V3_COMMAND_CENTER = 'true';
});

afterEach(() => {
  delete process.env.REACT_APP_V3_COMMAND_CENTER;
});

test('renders command center shell and layer toggles', () => {
  render(<CommandCenterPage />);
  expect(screen.getByText('Command Center')).toBeInTheDocument();
  expect(screen.getByText('Global Activity Monitor (map) + operator actions')).toBeInTheDocument();

  expect(screen.getByText('Conflict')).toBeInTheDocument();
  expect(screen.getByText('Quakes')).toBeInTheDocument();
  expect(screen.getByText('Shipping')).toBeInTheDocument();
  expect(screen.getByText('Cyber')).toBeInTheDocument();
  expect(screen.getByText('Markets')).toBeInTheDocument();
});

test('toggling a layer changes event count', () => {
  render(<CommandCenterPage />);

  const countBefore = screen.getByText(/Events:/i).textContent || '';

  // Conflict starts enabled; turning it off should reduce total visible events.
  fireEvent.click(screen.getByText('Conflict'));

  const countAfter = screen.getByText(/Events:/i).textContent || '';
  expect(countAfter).not.toEqual(countBefore);
});

