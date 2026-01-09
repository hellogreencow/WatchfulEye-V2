import React from 'react';
import { render, screen } from '@testing-library/react';
import { V3ExaminePage } from './ExaminePage';

test('renders query input and examine button', () => {
  render(<V3ExaminePage />);
  expect(screen.getByLabelText(/query/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /examine/i })).toBeInTheDocument();
});


