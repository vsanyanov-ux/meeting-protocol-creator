import { render, screen } from '@testing-library/react';
import App from './App';
import { expect, test } from 'vitest';

test('renders PRO-Толк title', () => {
  render(<App />);
  const titleElement = screen.getByText(/PRO-Толк/i);
  expect(titleElement).toBeInTheDocument();
});
