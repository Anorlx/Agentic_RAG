import unittest

from backend.indexing.document_chunk_tree import merge_document_chunks


class DocumentChunkTreeTests(unittest.TestCase):
    def test_merge_document_chunks_returns_l1_l2_l3_in_parent_order(self):
        parents = [
            {
                "chunk_id": "doc::p0::l2::0",
                "parent_chunk_id": "doc::p0::l1::0",
                "root_chunk_id": "doc::p0::l1::0",
                "chunk_level": 2,
                "chunk_idx": 1,
                "page_number": 0,
                "text": "L2",
            },
            {
                "chunk_id": "doc::p0::l1::0",
                "parent_chunk_id": "",
                "root_chunk_id": "doc::p0::l1::0",
                "chunk_level": 1,
                "chunk_idx": 0,
                "page_number": 0,
                "text": "L1",
            },
        ]
        leaves = [{
            "chunk_id": "doc::p0::l3::0",
            "parent_chunk_id": "doc::p0::l2::0",
            "root_chunk_id": "doc::p0::l1::0",
            "chunk_level": 3,
            "chunk_idx": 2,
            "page_number": 0,
            "text": "L3",
        }]

        result = merge_document_chunks(parents, leaves)

        self.assertEqual([1, 2, 3], [item["chunk_level"] for item in result])
        self.assertEqual("doc::p0::l1::0", result[1]["parent_chunk_id"])
        self.assertEqual("doc::p0::l2::0", result[2]["parent_chunk_id"])


if __name__ == "__main__":
    unittest.main()
