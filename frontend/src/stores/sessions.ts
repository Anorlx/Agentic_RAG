import { defineStore } from 'pinia';
import api from '@/utils/api';
import type { ChatSession } from '@/types/chat';

export const useSessionStore = defineStore('sessions', {
  state: () => ({
    sessions: [] as ChatSession[],
    showHistorySidebar: false,
  }),

  actions: {
    async fetchSessions() {
      try {
        const response = await api.get('/sessions');
        this.sessions = response.data.sessions || [];
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '加载历史记录失败';
        throw new Error(errMsg);
      }
    },

    async deleteSession(sessionId: string) {
      try {
        const response = await api.delete(`/sessions/${encodeURIComponent(sessionId)}`);
        this.sessions = this.sessions.filter((s) => s.session_id !== sessionId);
        return response.data.message || '会话已删除';
      } catch (error: any) {
        const errMsg = error.response?.data?.detail || error.message || '删除会话失败';
        throw new Error(errMsg);
      }
    },
  },
});
