# Document Chunk Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an administrator click a knowledge-base document and inspect its existing L1, L2, and L3 chunk hierarchy.

**Architecture:** Add a read-only document chunk endpoint that merges L1/L2 parent chunks from PostgreSQL with L3 leaf chunks from Milvus using the persisted parent IDs. The Vue document row fetches on demand and displays a nested, expandable tree; no indexing or stored data changes.

**Tech Stack:** FastAPI, SQLAlchemy, Milvus, Vue 3, Pinia, Vitest, unittest.

---

### Task 1: Read-only chunk API

**Files:**
- Modify: `backend/indexing/parent_chunk_store.py`
- Modify: `backend/indexing/milvus_client.py`
- Modify: `backend/schemas/documents.py`
- Modify: `backend/api/routes/documents.py`
- Test: `tests/test_document_chunk_tree.py`

- [ ] **Step 1: Write failing merger tests**

```python
def test_merge_document_chunks_returns_l1_l2_l3_in_parent_order(self):
    result = merge_document_chunks(parent_chunks, leaf_chunks)
    self.assertEqual([1, 2, 3], [item["chunk_level"] for item in result])
```

- [ ] **Step 2: Run the test and confirm it fails because the merger is absent.**

- [ ] **Step 3: Implement `list_by_filename()` for L1/L2 and `get_document_leaf_chunks()` for L3, then merge/sort their display fields in a read-only helper.**

- [ ] **Step 4: Add `GET /documents/{filename}/chunks`, protected by existing administrator authorization.**

- [ ] **Step 5: Run backend unit tests.**

### Task 2: On-demand L1/L2/L3 tree UI

**Files:**
- Modify: `frontend/src/types/document.ts`
- Modify: `frontend/src/stores/documents.ts`
- Modify: `frontend/src/components/Documents/DocumentItem.vue`
- Modify: `frontend/src/assets/styles/main.css`
- Test: `frontend/src/utils/documentChunkTree.spec.ts`

- [ ] **Step 1: Write a failing tree-builder test for L1 → L2 → L3 relationships.**
- [ ] **Step 2: Implement typed on-demand fetch and a pure hierarchy builder.**
- [ ] **Step 3: Render the tree only after clicking a document row; allow each node to expand its text preview.**
- [ ] **Step 4: Run frontend tests and production build.**
