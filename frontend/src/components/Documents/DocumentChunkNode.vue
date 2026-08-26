<template>
  <li class="document-chunk-node">
    <button type="button" class="document-chunk-button" @click="expanded = !expanded">
      <span :class="['chunk-level-badge', `level-${node.chunk_level}`]">L{{ node.chunk_level }}</span>
      <span class="chunk-node-label">第 {{ node.page_number + 1 }} 页 · 分块 {{ node.chunk_idx + 1 }}</span>
      <span class="chunk-node-length">{{ node.text.length }} 字</span>
      <i :class="expanded ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'"></i>
    </button>
    <div v-if="expanded" class="document-chunk-content">{{ node.text }}</div>
    <ul v-if="node.children.length" class="document-chunk-children">
      <DocumentChunkNode v-for="child in node.children" :key="child.chunk_id" :node="child" />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { DocumentChunkTreeNode } from '@/types/document';

defineProps<{ node: DocumentChunkTreeNode }>();
const expanded = ref(false);
</script>
