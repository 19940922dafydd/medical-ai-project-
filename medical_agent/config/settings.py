import os
from dotenv import load_dotenv

# Load `.env` file if it exists
load_dotenv()

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")

# ChromaDB Configuration
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "medical_knowledge")

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# Logging Configuration
LOG_DIR = os.getenv("LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Cache Configuration
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 300))   # 缓存过期时间 (默认 5 分钟)
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", 256))         # LRU 最大条目数

# MySQL Connection Pool Configuration
MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", 5))         # 连接池大小
MYSQL_MAX_CONNECTIONS = int(os.getenv("MYSQL_MAX_CONNECTIONS", 10))  # 最大连接数
