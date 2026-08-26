import type { RagTrace } from '@/types/chat';

type SupervisorRoute = RagTrace['supervisor_route'];

export const shouldShowRetrievalDetails = (route?: SupervisorRoute): boolean => (
  route === 'knowledge_base' || route === 'knowledge_base_and_web_search'
);

const supervisorRouteLabels: Record<string, string> = {
  direct: '直接回答',
  knowledge_base: '知识库检索',
  web_search: '网页搜索',
  knowledge_base_and_web_search: '知识库 + 网页搜索',
};

const webSearchStatusLabels: Record<string, string> = {
  completed: '已完成',
  failed: '暂时不可用',
  not_requested: '未使用',
};

export const formatSupervisorRoute = (route?: SupervisorRoute): string => (
  supervisorRouteLabels[route || ''] || '未记录'
);

export const formatWebSearchStatus = (status?: RagTrace['web_search_status']): string => (
  webSearchStatusLabels[status || ''] || '未使用'
);
