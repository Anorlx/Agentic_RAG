import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from './api';

const unauthorizedAdapter = async (config: any) => Promise.reject({
  config,
  message: 'Request failed with status code 401',
  response: {
    status: 401,
    data: { detail: '用户名或密码错误' },
  },
});

describe('API unauthorized handling', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
    });
    vi.stubGlobal('window', {
      dispatchEvent: vi.fn(),
    });
    api.defaults.adapter = unauthorizedAdapter;
  });

  it('does not report session expiration when login credentials are wrong', async () => {
    await expect(api.post('/auth/login', {
      username: 'tester',
      password: 'wrong-password',
    })).rejects.toMatchObject({ response: { status: 401 } });

    expect(window.dispatchEvent).not.toHaveBeenCalled();
  });

  it('still reports session expiration for protected API requests', async () => {
    await expect(api.get('/sessions')).rejects.toMatchObject({ response: { status: 401 } });

    expect(window.dispatchEvent).toHaveBeenCalledTimes(1);
  });
});
