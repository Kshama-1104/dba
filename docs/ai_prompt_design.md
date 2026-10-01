# DailyBlog AI - AI Prompt Design & RAG Architecture

## Core Philosophy: Deterministic Bounds on Non-Deterministic Systems

The greatest challenge with generative AI in an enterprise setting is non-determinism (hallucinations, off-brand tone, ignoring instructions). DailyBlog AI solves this by wrapping the LLM generation step in a strictly bounded Retrieval-Augmented Generation (RAG) architecture and enforcing deterministic validation.

## 1. Context Assembly (The Pre-Prompt)

Before any call is made to the LLM, the backend constructs a massive JSON-structured context object. The LLM never "guesses" facts; it is provided with them.

The `BlogGenerationContext` consists of:
1.  **Company AI Profile:** Brand voice, target audience, marketing goals, forbidden words.
2.  **Blog Format:** Structural requirements (e.g., must have 1 H1, 3 H2s, concluding paragraph with CTA).
3.  **Semantic Memory:** General company facts retrieved via pgvector cosine distance.
4.  **Episodic Memory:** Specific past campaigns or events.
5.  **Reference Data (RAG chunks):** Raw text chunks retrieved from uploaded Knowledge Documents matching the topic's primary keyword.

## 2. The System Prompt Boundary

We employ a strict separation between *Instructions* and *Data* to prevent prompt injection and hallucination.

**System Message:**
```text
You are a senior B2B content marketing writer. Your task is to generate a comprehensive, SEO-optimized blog post strictly adhering to the provided JSON constraints. 
You must ONLY use the information provided in the REFERENCE_DATA section. Do not invent facts, product names, or statistics.
Your output must be a valid JSON object matching the requested schema.
```

**User Message:**
```json
{
  "context": { ... },
  "instructions": { ... },
  "reference_data": [ ... ]
}
```

## 3. Structured Outputs (AST)

Instead of asking the LLM to output raw Markdown (which is notoriously difficult to validate), we force the LLM to output an Abstract Syntax Tree (AST) in JSON using OpenAI's Function Calling / Structured Outputs feature (or a JSON schema enforcement layer for other providers).

```json
{
  "title": "...",
  "meta_description": "...",
  "primary_keyword": "...",
  "sections": [
    {
      "heading_level": "h2",
      "heading_text": "...",
      "content": "..."
    }
  ]
}
```

This guarantees the structure. The backend then deterministically compiles this JSON into the final Markdown.

## 4. Editor Chat Prompts (Phase 8)

When an Editor requests changes via the chat interface, the system does not just send the raw text to the LLM. It sends the *entire current AST*, the *diff request*, and the *original RAG context*.

```text
The editor has requested the following changes to the current blog draft:
"{editor_feedback}"

Update the provided JSON AST to incorporate these changes while strictly maintaining the brand voice and avoiding hallucinations.
```

## 5. Security & Limitations

*   **Prompt Injection:** Addressed by strictly typing the inputs as JSON and using separate system/user roles.
*   **Token Limits:** The RAG retrieval limits chunks to the top-K matches to prevent exceeding context windows.
*   **Fallback Strategy:** A deterministic mock provider is included to allow the system to operate (and test) without external API costs or network dependency.
