import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from './main';

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('Reminder demo authentication', () => {
  it('shows the isolated demo login and explains the production boundary', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Deadline reminders' })).toBeTruthy();
    expect(screen.getByText(/not connected to production BHASHALEARN login/i)).toBeTruthy();
    expect(screen.getByLabelText('Email')).toBeTruthy();
  });

  it('registers a demo student, stores the token, and loads owned data', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/auth/register')) return new Response(JSON.stringify({ access_token: 'demo-jwt' }), { status: 201 });
      if (url.endsWith('/deadlines') || url.endsWith('/reminders') || url.endsWith('/voice/sessions')) return new Response('[]', { status: 200 });
      return new Response('{}', { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /new here/i }));
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'demo@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'A-long-demo-password-2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await waitFor(() => expect(localStorage.getItem('accessToken')).toBe('demo-jwt'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/deadlines$/), expect.objectContaining({ headers: { Authorization: 'Bearer demo-jwt' } }));
  });
});
