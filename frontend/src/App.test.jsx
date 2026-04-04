import { render, screen } from '@testing-library/react';
import App from './App';
import { expect, test } from 'vitest';

test('renders Meeting Protocol Creator title', () => {
  render(<App />);
  const titleElement = screen.getByText(/Meeting Protocol Creator/i);
  expect(titleElement).toBeInTheDocument();
});
