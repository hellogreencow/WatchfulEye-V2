import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders app shell (login or dashboard)', async () => {
  // Route directly to /login in tests to avoid mounting landing-page panels that
  // depend on canvas/network in a JSDOM environment.
  window.history.pushState({}, 'Login', '/login');
  render(<App />);
  // Login UI should render a stable control/label.
  expect(await screen.findByText(/sign in/i)).toBeInTheDocument();
});
