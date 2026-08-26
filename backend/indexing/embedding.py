"""文本向量化服务 - 只支持密集向量（由 Milvus 2.5+ 原生支持中文分词与 BM25 全文检索）"""
import os
from langchain_huggingface import HuggingFaceEmbeddings


def _create_dense_embedder() -> HuggingFaceEmbeddings:
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


class EmbeddingService:
    """文本向量化服务 - 密集向量本地模型"""

    def __init__(self, state_path=None):
        # Do not download or load the Hugging Face model while the web service
        # is starting. It is only needed when a document is indexed or queried.
        self._embedder = None

    def _get_embedder(self) -> HuggingFaceEmbeddings:
        if self._embedder is None:
            self._embedder = _create_dense_embedder()
        return self._embedder

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._get_embedder().embed_documents(texts)
        except Exception as e:
            raise Exception(f"本地密集嵌入模型调用失败: {str(e)}") from e


# 全进程唯一实例
embedding_service = EmbeddingService()
