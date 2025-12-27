import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders app shell (login or dashboard)', async () => {
  render(<App />);
  // In this app the initial route renders the auth-gated dashboard.
  // When unauthenticated, we should land on the login screen.
  const brand = await screen.findByText(/watchfuleye/i);
  expect(brand).toBeInTheDocument();
});
