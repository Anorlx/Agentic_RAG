<template>
  <div
    v-if="!msg.isHitlRequest && !msg.isHitlAnswer"
    :class="['message', msg.isUser ? 'user-message' : 'bot-message']"
  >
    <div v-if="!msg.isUser" class="message-avatar" aria-hidden="true">
      <i class="fa-solid fa-cubes-stacked"></i>
    </div>

    <div class="message-column">
      <div v-if="!msg.isUser" class="message-author">
        <span>SuperAgenticRAG</span>
        <small v-if="routeLabel" class="route-badge">{{ routeLabel }}</small>
        <small v-if="msg.ragTrace?.retrieved_chunks?.length">
          已引用 {{ msg.ragTrace.retrieved_chunks.length }} 个来源
        </small>
        <small v-if="msg.ragTrace?.web_sources?.length">
          已检索 {{ msg.ragTrace.web_sources.length }} 个网页来源
        </small>
      </div>

      <template v-if="msg.isUser">
        <MessageContent :text="msg.text" :is-user="true" :msg-index="msgIndex" />
      </template>

      <template v-else>
        <div v-if="msg.hitlResumeText" class="hitl-resume-note">
          <i class="fa-solid fa-rotate-right"></i>
          <span>已补充：{{ msg.hitlResumeText }}，正在继续原流程</span>
        </div>

        <ThinkingTrace
          v-if="msg.isThinking && !msg.text"
          :msg="msg"
          :msg-index="msgIndex"
        />

        <template v-else>
          <MessageContent
            :text="msg.text"
            :is-user="false"
            :msg-index="msgIndex"
            @cite-click="onCiteClick"
          />
          <References
            ref="referencesRef"
            :msg="msg"
            :msg-index="msgIndex"
            @cite-click="onCiteClick"
          />
          <RetrievalTraceDetails :msg="msg" />
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import MessageContent from './MessageContent.vue';
import ThinkingTrace from './ThinkingTrace.vue';
import References from './References.vue';
import RetrievalTraceDetails from './RetrievalTraceDetails.vue';
import type { Message } from '@/types/chat';

const props = defineProps<{
  msg: Message;
  msgIndex: number;
}>();

const routeLabels: Record<string, string> = {
  direct: '直接回答',
  knowledge_base: '知识库检索',
  web_search: '网页搜索',
  knowledge_base_and_web_search: '知识库 + 网页搜索',
};

const routeLabel = computed(() => routeLabels[props.msg.ragTrace?.supervisor_route || '']);

const emit = defineEmits<{
  (e: 'cite-click', msgIndex: number, chunkIndex: number): void;
}>();

const referencesRef = ref<InstanceType<typeof References> | null>(null);

const openReferences = () => {
  referencesRef.value?.openDetails();
};

defineExpose({ openReferences });

const onCiteClick = (msgIndex: number, chunkIndex: number) => {
  emit('cite-click', msgIndex, chunkIndex);
};
</script>
