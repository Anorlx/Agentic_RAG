import type { DocumentChunk, DocumentChunkTreeNode } from '@/types/document';

const byPosition = (a: DocumentChunk, b: DocumentChunk) => (
  a.page_number - b.page_number
  || a.chunk_idx - b.chunk_idx
  || a.chunk_level - b.chunk_level
  || a.chunk_id.localeCompare(b.chunk_id)
);

export const buildDocumentChunkTree = (chunks: DocumentChunk[]): DocumentChunkTreeNode[] => {
  const nodes = new Map<string, DocumentChunkTreeNode>();
  (chunks || []).forEach((chunk) => {
    if (!chunk?.chunk_id) return;
    nodes.set(chunk.chunk_id, { ...chunk, children: [] });
  });

  const roots: DocumentChunkTreeNode[] = [];
  nodes.forEach((node) => {
    const parent = node.parent_chunk_id ? nodes.get(node.parent_chunk_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  });

  const sortNodes = (items: DocumentChunkTreeNode[]) => {
    items.sort(byPosition);
    items.forEach((item) => sortNodes(item.children));
  };
  sortNodes(roots);
  return roots;
};
