# ============================================================
# LogiTrack | 04_genai_rag_chatbot
# Purpose: A RAG (Retrieval-Augmented Generation) chatbot that
#          answers business questions grounded in:
#            (a) LogiTrack's policy documents (unstructured text)
#            (b) The governed Gold-layer regional performance data
#
# KEY DESIGN CHOICE: Uses Fabric's BUILT-IN AI functions
# (openaivec + setup_fabric()) instead of a separate Azure OpenAI
# resource. This is billed against your existing Fabric capacity,
# requires no extra provisioning, and sidesteps the Azure OpenAI
# regional restrictions some subscriptions run into.
# ============================================================

# ---- CELL 1: Install the library (Fabric-native AI access) ----
# %pip install openaivec --quiet

# ---- CELL 2: Setup ----
import pandas as pd
import numpy as np
import openaivec
from openaivec import pandas_ext

openaivec.setup_fabric()  # routes calls through Fabric capacity, no API key needed

spark.sql("CREATE SCHEMA IF NOT EXISTS rag")


# ---- CELL 3: Load and chunk the policy document ----
# Simple paragraph-based chunking: split on blank lines, keep
# chunks that are substantive (skip short headers/separators).
raw_lines = spark.read.text("Files/raw/policies/logitrack_policies.txt") \
    .rdd.map(lambda r: r.value).collect()
full_text = "\n".join(raw_lines)

# Split into chunks by double-newline (paragraph breaks), keep meaningful ones
raw_chunks = [c.strip() for c in full_text.split("\n\n")]
chunks = [c for c in raw_chunks if len(c) > 80]  # drop short headers/section breaks

print(f"[OK] Parsed {len(chunks)} policy chunks from the document")

chunks_df = pd.DataFrame({"chunk_id": range(len(chunks)), "chunk_text": chunks})


# ---- CELL 4: Generate embeddings for each chunk ----
chunks_df["embedding"] = chunks_df["chunk_text"].ai.embeddings()

print(f"[OK] Generated embeddings for {len(chunks_df)} chunks")
print(f"Embedding dimension: {len(chunks_df['embedding'].iloc[0])}")


# ---- CELL 5: Store chunks + embeddings in the Lakehouse (your vector store) ----
spark_chunks = spark.createDataFrame(
    chunks_df.assign(embedding=chunks_df["embedding"].apply(lambda x: x.tolist()
                      if hasattr(x, "tolist") else list(x)))
)
(spark_chunks.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("rag.policy_chunks"))

print("[OK] rag.policy_chunks saved \u2014 this is your in-Lakehouse vector store")


# ---- CELL 6: Retrieval function (cosine similarity search) ----
def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def retrieve_relevant_chunks(question: str, top_k: int = 3) -> pd.DataFrame:
    """Embeds the question, then returns the top_k most similar policy chunks."""
    q_df = pd.DataFrame({"q": [question]})
    q_embedding = q_df["q"].ai.embeddings().iloc[0]

    chunks_local = spark.table("rag.policy_chunks").toPandas()
    chunks_local["similarity"] = chunks_local["embedding"].apply(
        lambda emb: cosine_similarity(q_embedding, emb)
    )
    return chunks_local.sort_values("similarity", ascending=False).head(top_k)


# ---- CELL 7: Pull relevant Gold-layer facts for numeric grounding ----
def get_regional_facts() -> str:
    """
    Summarizes gold.agg_regional_performance as text the LLM can cite,
    so numeric answers come from real governed data, not guesses.
    """
    df = spark.table("gold.agg_regional_performance").toPandas()
    lines = []
    for _, row in df.iterrows():
        lines.append(
            f"- {row['region']}: {int(row['total_orders'])} orders, "
            f"${row['total_revenue']:,.2f} total revenue, "
            f"${row['avg_order_value']:,.2f} avg order value, "
            f"{row['avg_delivery_days']:.2f} avg delivery days"
        )
    return "Regional performance data (from gold.agg_regional_performance):\n" + "\n".join(lines)


# ---- CELL 8: The RAG chatbot function ----
def ask_logitrack(question: str) -> str:
    relevant = retrieve_relevant_chunks(question, top_k=3)
    policy_context = "\n\n".join(
        f"[Policy excerpt, relevance={row['similarity']:.2f}]\n{row['chunk_text']}"
        for _, row in relevant.iterrows()
    )
    data_context = get_regional_facts()

    instructions = f"""You are LogiTrack's internal support assistant. Answer the
user's question using ONLY the context provided below. If the context doesn't
contain the answer, say so clearly rather than guessing. Cite which context
(policy excerpt or regional data) you used.

=== POLICY CONTEXT ===
{policy_context}

=== BUSINESS DATA CONTEXT ===
{data_context}"""

    q_df = pd.DataFrame({"question": [question]})
    response = q_df["question"].ai.responses(instructions).iloc[0]
    return response


# ---- CELL 9: Test it with a few real questions ----
test_questions = [
    "What's our average delivery delay for the East region, and what's our policy on delayed shipment refunds?",
    "If a customer's order is lost, what are their options?",
    "Which region has the highest revenue, and what's the return window for office furniture?",
]

for q in test_questions:
    print(f"\n{'='*70}\nQ: {q}\n{'='*70}")
    print(ask_logitrack(q))
