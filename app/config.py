from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek LLM
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"

    # OpenAI Embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ragforge_docs"
    qdrant_api_key: str = ""

    # Chunking / Retrieval
    chunk_size: int = 1024
    chunk_overlap: int = 20
    similarity_top_k: int = 4

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
