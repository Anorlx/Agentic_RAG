import { describe, expect, it } from 'vitest';
import { buildDocumentChunkTree } from './documentChunkTree';

describe('document chunk tree', () => {
  it('nests L2 under L1 and L3 under L2', () => {
    const tree = buildDocumentChunkTree([
      { chunk_id: 'l3', parent_chunk_id: 'l2', root_chunk_id: 'l1', chunk_level: 3, chunk_idx: 2, page_number: 0, text: 'leaf' },
      { chunk_id: 'l1', parent_chunk_id: '', root_chunk_id: 'l1', chunk_level: 1, chunk_idx: 0, page_number: 0, text: 'root' },
      { chunk_id: 'l2', parent_chunk_id: 'l1', root_chunk_id: 'l1', chunk_level: 2, chunk_idx: 1, page_number: 0, text: 'middle' },
    ]);

    expect(tree).toHaveLength(1);
    expect(tree[0].children[0].chunk_id).toBe('l2');
    expect(tree[0].children[0].children[0].chunk_id).toBe('l3');
  });
});
