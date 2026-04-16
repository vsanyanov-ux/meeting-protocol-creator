import { render, screen } from '@testing-library/react';
import App from './App';
import { expect, test } from 'vitest';

test('renders Протоколист title', () => {
  render(<App />);
  const titleElement = screen.getByText(/Протоколист/i);
  expect(titleElement).toBeInTheDocument();
});
