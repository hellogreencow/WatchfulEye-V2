import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders login shell', async () => {
  // Keep test deterministic: route directly to /login instead of rendering the full landing
  // experience (canvas + intersection observers + network calls).
  window.history.pushState({}, 'Login', '/login');
  render(<App />);
  const brand = await screen.findByText(/watchful/i);
  expect(brand).toBeInTheDocument();
});
