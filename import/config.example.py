# Copy to config.py and fill in. config.py is git-ignored — never commit real credentials.

# Serverless project: Elasticsearch endpoint (Project settings -> Connection details) + an API key
ES_URL     = "https://<your-project>.es.<region>.azure.elastic.cloud:443"
ES_API_KEY = "<base64-encoded-api-key>"

# Embedding endpoint used by every semantic_text field.
# The import script checks it exists and lists the available ones if not
# (GET _inference/_all). Jina v5 small is the multilingual default on Elastic Inference Service.
TEXT_INFERENCE_ID = ".jina-embeddings-v5-text-small"

# Optional: only used with --with-multimodal. Leave None to reuse TEXT_INFERENCE_ID (text-only fallback).
MULTIMODAL_INFERENCE_ID = None
