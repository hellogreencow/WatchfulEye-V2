# voyage-3-large RAG Enhancement Setup

## Quick Setup for Enhanced Chat RAG

### 1. Install voyageai
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable
```bash
export VOYAGE_API_KEY=your_voyage_api_key_here
export EMBEDDINGS_PROVIDER=voyage
export PG_DSN="dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432"
```

### 3. Run Enhancement Script
No manual script needed. The backend auto-selects voyage if `VOYAGE_API_KEY` is set, with OpenAI fallback.

## How It Works
- **voyage-3-large**: 2048 dimensions, 9.74% better retrieval
- **Automatic**: Enhances existing RAG system in chat
- **Fallback**: Uses OpenAI if voyage unavailable
- **No Changes**: Works with existing database

## Benefits
- ✅ **Better Retrieval**: 9.74% improvement over OpenAI
- ✅ **Longer Context**: 32K tokens vs 8K
- ✅ **Multi-domain**: Superior in finance, law, code
- ✅ **Consistent**: Same chat interface, better results

## Usage
Just use the chat normally - voyage-3-large will automatically enhance article retrieval when RAG is enabled.
