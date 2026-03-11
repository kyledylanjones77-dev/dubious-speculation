"""
Cowen LLM — RAG-powered "Ben Cowen AI"
Turns 2,400 video transcripts into a conversational AI that answers
market questions using Ben's actual analysis, frameworks, and reasoning.

Architecture:
  1. Chunk transcripts into ~400-token segments with overlap
  2. Embed chunks via OpenAI text-embedding-3-small
  3. Store embeddings + metadata in a numpy-based vector store
  4. On query: embed question → cosine similarity → top-K chunks → GPT-4o-mini answer
"""
import json
import os
import time
import hashlib
import numpy as np
try:
    import tiktoken
except ImportError:
    tiktoken = None
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRANSCRIPT_DIR = "data/transcripts"
VECTOR_STORE_PATH = "data/vector_store.npz"
CHUNK_INDEX_PATH = "data/chunk_index.json"
CHAT_HISTORY_PATH = "data/chat_history.json"

CHUNK_SIZE = 400        # tokens per chunk
CHUNK_OVERLAP = 80      # token overlap between chunks
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 12              # chunks to retrieve per query
MAX_CONTEXT_TOKENS = 6000  # max tokens for context window

# System prompt that makes the LLM respond like Ben Cowen
SYSTEM_PROMPT = """You are an AI assistant that has deeply studied Benjamin Cowen's cryptocurrency and macro market analysis from his YouTube channel "Into The Cryptoverse."

You have access to his actual transcript excerpts provided as context. Use them to answer questions accurately in Ben's analytical style.

KEY RULES:
1. Base your answers on the transcript context provided. Cite specific frameworks and data points Ben uses.
2. Maintain Ben's measured, data-driven tone — he avoids hype and focuses on probabilities, historical patterns, and risk management.
3. Reference his specific frameworks when relevant:
   - Logarithmic regression bands (fair value model)
   - Risk metric (0-1 scale)
   - Bull Market Support Band (20W SMA + 21W EMA)
   - 4-year halving cycle
   - Bitcoin dominance analysis
   - Business cycle / macro framework (oil, DXY, yields, fed rates)
   - Midterm year patterns
4. If the context doesn't contain enough info to answer fully, say what you can based on what's available and note the limitation.
5. Use Ben's catchphrases naturally: "the beauty of mathematics", "dubious speculation", "into the cryptoverse"
6. Always frame things probabilistically — "historically", "tends to", "the base case is" — never make guarantees.
7. When discussing price targets, reference the regression bands, risk metric levels, or cycle timing rather than arbitrary numbers.

Remember: You're channeling Ben's analytical framework, not giving financial advice. Frame everything as educational analysis."""


class CowenLLM:
    """RAG engine for Ben Cowen's market analysis."""

    def __init__(self, openai_api_key=None):
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None
        self.tokenizer = tiktoken.get_encoding("cl100k_base") if tiktoken else None

        # Vector store state
        self.embeddings = None       # numpy array (N, 1536)
        self.chunk_index = []        # list of {text, title, video_id, chunk_id}
        self.is_ready = False
        self.stats = {"chunks": 0, "transcripts": 0, "last_built": None}

        # Load existing vector store if available
        self._load_vector_store()

    @property
    def client(self):
        """Lazy-init OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.openai_api_key)
        return self._client

    # -----------------------------------------------------------------------
    # 1. CHUNKING
    # -----------------------------------------------------------------------

    def _chunk_text(self, text, title="", video_id=""):
        """Split text into overlapping token chunks with metadata."""
        tokens = self.tokenizer.encode(text)
        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + CHUNK_SIZE, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append({
                "text": chunk_text,
                "title": title,
                "video_id": video_id,
                "chunk_id": f"{video_id}_{start}",
                "token_count": len(chunk_tokens),
            })

            start += CHUNK_SIZE - CHUNK_OVERLAP
            if end >= len(tokens):
                break

        return chunks

    def _chunk_all_transcripts(self):
        """Chunk every transcript in the data directory."""
        all_chunks = []

        if not os.path.exists(TRANSCRIPT_DIR):
            print("No transcripts directory found")
            return all_chunks

        files = sorted(os.listdir(TRANSCRIPT_DIR))
        transcript_count = 0

        for fname in files:
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(TRANSCRIPT_DIR, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                text = data.get("full_text", "")
                title = data.get("title", "")
                video_id = data.get("video_id", fname.replace(".json", ""))

                if not text or len(text) < 50:
                    continue

                # Prepend title for context
                full_text = f"Video: {title}\n\n{text}"
                chunks = self._chunk_text(full_text, title, video_id)
                all_chunks.extend(chunks)
                transcript_count += 1

            except Exception as e:
                print(f"  Error chunking {fname}: {e}")

        print(f"Chunked {transcript_count} transcripts into {len(all_chunks)} chunks")
        return all_chunks

    # -----------------------------------------------------------------------
    # 2. EMBEDDINGS
    # -----------------------------------------------------------------------

    def _embed_batch(self, texts, batch_size=100):
        """Embed a batch of texts via OpenAI API."""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                if i > 0 and i % 500 == 0:
                    print(f"  Embedded {i}/{len(texts)} chunks...")

                # Rate limiting — be gentle
                if i + batch_size < len(texts):
                    time.sleep(0.1)

            except Exception as e:
                print(f"  Embedding error at batch {i}: {e}")
                # Fill with zeros for failed batches
                all_embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))
                time.sleep(2)

        return np.array(all_embeddings, dtype=np.float32)

    def _embed_query(self, query):
        """Embed a single query string."""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query],
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    # -----------------------------------------------------------------------
    # 3. VECTOR STORE
    # -----------------------------------------------------------------------

    def build_vector_store(self, force=False):
        """Build or rebuild the vector store from all transcripts."""
        # Check if we need to rebuild
        if not force and self.is_ready:
            transcript_count = len([f for f in os.listdir(TRANSCRIPT_DIR)
                                   if f.endswith(".json")]) if os.path.exists(TRANSCRIPT_DIR) else 0
            # Only rebuild if we have 20%+ more transcripts
            if transcript_count <= self.stats.get("transcripts", 0) * 1.2:
                print(f"Vector store is current ({self.stats['chunks']} chunks from {self.stats['transcripts']} transcripts)")
                return True

        print("Building vector store...")
        start_time = time.time()

        # Step 1: Chunk all transcripts
        chunks = self._chunk_all_transcripts()
        if not chunks:
            print("No chunks to embed!")
            return False

        # Step 2: Embed all chunks
        texts = [c["text"] for c in chunks]
        print(f"Embedding {len(texts)} chunks...")
        embeddings = self._embed_batch(texts)

        if embeddings.shape[0] != len(chunks):
            print(f"Embedding count mismatch: {embeddings.shape[0]} vs {len(chunks)}")
            return False

        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # avoid division by zero
        embeddings = embeddings / norms

        # Step 3: Save
        self.embeddings = embeddings
        self.chunk_index = [{
            "text": c["text"],
            "title": c["title"],
            "video_id": c["video_id"],
            "chunk_id": c["chunk_id"],
        } for c in chunks]

        self.stats = {
            "chunks": len(chunks),
            "transcripts": len(set(c["video_id"] for c in chunks)),
            "last_built": datetime.now().isoformat(),
            "build_time_sec": round(time.time() - start_time, 1),
        }
        self.is_ready = True

        self._save_vector_store()

        print(f"Vector store built: {self.stats['chunks']} chunks from {self.stats['transcripts']} transcripts in {self.stats['build_time_sec']}s")
        return True

    def _save_vector_store(self):
        """Persist vector store to disk."""
        os.makedirs(os.path.dirname(VECTOR_STORE_PATH), exist_ok=True)

        # Save embeddings as compressed numpy
        np.savez_compressed(VECTOR_STORE_PATH, embeddings=self.embeddings)

        # Save chunk index + stats
        with open(CHUNK_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "stats": self.stats,
                "chunks": self.chunk_index,
            }, f)

        print(f"Saved vector store: {VECTOR_STORE_PATH} ({os.path.getsize(VECTOR_STORE_PATH) / 1024 / 1024:.1f} MB)")

    def _load_vector_store(self):
        """Load vector store from disk if available."""
        if not os.path.exists(VECTOR_STORE_PATH) or not os.path.exists(CHUNK_INDEX_PATH):
            return False

        try:
            # Load embeddings
            data = np.load(VECTOR_STORE_PATH)
            self.embeddings = data["embeddings"]

            # Load chunk index
            with open(CHUNK_INDEX_PATH, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            self.chunk_index = index_data.get("chunks", [])
            self.stats = index_data.get("stats", {})

            if self.embeddings.shape[0] == len(self.chunk_index):
                self.is_ready = True
                print(f"Loaded vector store: {self.stats.get('chunks', 0)} chunks from {self.stats.get('transcripts', 0)} transcripts")
                return True
            else:
                print("Vector store size mismatch — needs rebuild")
                return False

        except Exception as e:
            print(f"Error loading vector store: {e}")
            return False

    # -----------------------------------------------------------------------
    # 4. RETRIEVAL
    # -----------------------------------------------------------------------

    def _retrieve(self, query, top_k=TOP_K):
        """Find the most relevant transcript chunks for a query."""
        if not self.is_ready or self.embeddings is None:
            return []

        # Embed query
        query_vec = self._embed_query(query)
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)

        # Cosine similarity (embeddings are already normalized)
        similarities = self.embeddings @ query_vec

        # Get top-K indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        seen_videos = set()
        total_tokens = 0

        for idx in top_indices:
            if idx >= len(self.chunk_index):
                continue

            chunk = self.chunk_index[idx]
            score = float(similarities[idx])

            # Skip very low relevance
            if score < 0.15:
                continue

            # Limit tokens in context
            chunk_tokens = len(self.tokenizer.encode(chunk["text"]))
            if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                break

            results.append({
                "text": chunk["text"],
                "title": chunk["title"],
                "video_id": chunk["video_id"],
                "score": round(score, 4),
            })
            total_tokens += chunk_tokens
            seen_videos.add(chunk["video_id"])

        return results

    # -----------------------------------------------------------------------
    # 5. CHAT (RAG)
    # -----------------------------------------------------------------------

    def chat(self, user_message, conversation_history=None):
        """
        Answer a question using RAG — retrieves relevant transcript chunks
        and generates a response in Ben Cowen's analytical style.
        """
        if not self.is_ready:
            return {
                "response": "The knowledge base is still being built. Please wait a moment and try again.",
                "sources": [],
                "ready": False,
            }

        # Retrieve relevant context
        retrieved = self._retrieve(user_message)

        if not retrieved:
            return {
                "response": "I couldn't find relevant content in the transcript database for that question. Try asking about Bitcoin cycles, risk metrics, macro analysis, or any specific cryptocurrency topic Ben covers.",
                "sources": [],
                "ready": True,
            }

        # Build context from retrieved chunks
        context_parts = []
        sources = []
        seen_titles = set()

        for i, chunk in enumerate(retrieved):
            context_parts.append(f"[Source {i+1}: \"{chunk['title']}\" (relevance: {chunk['score']:.2f})]\n{chunk['text']}")

            if chunk["title"] not in seen_titles:
                sources.append({
                    "title": chunk["title"],
                    "video_id": chunk["video_id"],
                    "relevance": chunk["score"],
                })
                seen_titles.add(chunk["title"])

        context = "\n\n---\n\n".join(context_parts)

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history (last 4 exchanges)
        if conversation_history:
            for msg in conversation_history[-8:]:
                messages.append(msg)

        # User message with context
        user_prompt = f"""Based on the following excerpts from Benjamin Cowen's video transcripts, answer the user's question.

TRANSCRIPT CONTEXT:
{context}

USER QUESTION: {user_message}

Provide a thorough, analytical answer in Ben's style. Reference specific data points and frameworks from the transcripts when possible."""

        messages.append({"role": "user", "content": user_prompt})

        # Generate response
        try:
            response = self.client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
            )
            answer = response.choices[0].message.content

            # Save to history
            self._save_chat_message(user_message, answer, sources)

            return {
                "response": answer,
                "sources": sources[:6],
                "ready": True,
                "chunks_used": len(retrieved),
                "model": CHAT_MODEL,
            }

        except Exception as e:
            return {
                "response": f"Error generating response: {str(e)}",
                "sources": [],
                "ready": True,
                "error": True,
            }

    def _save_chat_message(self, question, answer, sources):
        """Save chat history for reference."""
        history = []
        if os.path.exists(CHAT_HISTORY_PATH):
            try:
                with open(CHAT_HISTORY_PATH, "r") as f:
                    history = json.load(f)
            except Exception:
                pass

        history.append({
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer[:500],  # Truncate for storage
            "source_count": len(sources),
        })

        # Keep last 100 conversations
        history = history[-100:]

        with open(CHAT_HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    # -----------------------------------------------------------------------
    # 6. STATUS
    # -----------------------------------------------------------------------

    def get_status(self):
        """Get current LLM status."""
        transcript_count = 0
        if os.path.exists(TRANSCRIPT_DIR):
            transcript_count = len([f for f in os.listdir(TRANSCRIPT_DIR) if f.endswith(".json")])

        return {
            "ready": self.is_ready,
            "vector_store": {
                "chunks": self.stats.get("chunks", 0),
                "transcripts_embedded": self.stats.get("transcripts", 0),
                "last_built": self.stats.get("last_built"),
                "build_time": self.stats.get("build_time_sec"),
            },
            "transcripts_available": transcript_count,
            "needs_rebuild": transcript_count > self.stats.get("transcripts", 0) * 1.2,
            "model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL,
        }


# ---------------------------------------------------------------------------
# CLI entry point for building the vector store
# ---------------------------------------------------------------------------
def main():
    """Build vector store from command line."""
    import sys

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Try loading from api-keys location
        key_file = os.path.expanduser("~/.claude/projects/C--Users-15404/memory/api-keys.md")
        if os.path.exists(key_file):
            with open(key_file) as f:
                for line in f:
                    if "OPENAI_API_KEY" in line and "sk-" in line:
                        api_key = line.split("`")[3] if "`" in line else ""
                        break

    if not api_key:
        print("No OpenAI API key found!")
        sys.exit(1)

    llm = CowenLLM(openai_api_key=api_key)
    force = "--force" in sys.argv
    llm.build_vector_store(force=force)

    # Quick test
    if "--test" in sys.argv:
        print("\n=== Test Query ===")
        result = llm.chat("What is Bitcoin's risk metric and how should I use it?")
        print(f"\nAnswer:\n{result['response']}")
        print(f"\nSources: {[s['title'] for s in result['sources']]}")


if __name__ == "__main__":
    main()
