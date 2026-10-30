import { render, screen } from '@testing-library/react';
import App from './App';

test('대시보드 제목이 렌더링된다', () => {
  render(<App />);
  const heading = screen.getByText(/건강 대시보드/i);
  expect(heading).toBeInTheDocument();
});
