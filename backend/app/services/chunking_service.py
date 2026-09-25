from dataclasses import dataclass
from typing import List


@dataclass
class DocumentChunk:
    chunk_index: int
    content: str
    token_count: int


class ChunkingService:
    """
    Deterministic recursive text chunker adhering to the system blueprint.
    Splits text along logical boundaries (paragraphs, lines, sentences, spaces)
    while maintaining overlap for contextual continuity.
    """

    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[DocumentChunk]:
        """
        Deterministically split normalized text into ordered chunks.
        """
        if not text or not text.strip():
            return []

        cleaned_text = text.strip()
        raw_chunks = self._recursive_split(cleaned_text, self.chunk_size, self.chunk_overlap)

        chunks: List[DocumentChunk] = []
        for idx, chunk_text in enumerate(raw_chunks):
            chunk_content = chunk_text.strip()
            if not chunk_content:
                continue
            token_est = self._estimate_tokens(chunk_content)
            chunks.append(
                DocumentChunk(
                    chunk_index=idx,
                    content=chunk_content,
                    token_count=token_est,
                )
            )

        return chunks

    @classmethod
    def _estimate_tokens(cls, text: str) -> int:
        """
        Estimate token count conservatively (approximately 4 characters per token in English).
        """
        return max(1, len(text) // 4)

    def _recursive_split(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """
        Splits text recursively using delimiters in order of priority:
        paragraphs ('\\n\\n'), lines ('\\n'), sentences ('. '), spaces (' '), characters.
        """
        if len(text) <= chunk_size:
            return [text]

        separators = ["\n\n", "\n", ". ", " ", ""]
        return self._split_with_separators(text, separators, chunk_size, chunk_overlap)

    def _split_with_separators(
        self, text: str, separators: List[str], chunk_size: int, chunk_overlap: int
    ) -> List[str]:
        if not separators:
            # Fallback: slice by characters
            return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            return [text[i : i + chunk_size] for i in range(0, len(text), max(1, chunk_size - chunk_overlap))]

        parts = text.split(separator)
        chunks: List[str] = []
        current_chunk = ""

        for part in parts:
            candidate = f"{current_chunk}{separator}{part}" if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Handle overlap from end of current_chunk
                    overlap_seed = current_chunk[-chunk_overlap:] if chunk_overlap > 0 else ""
                    current_chunk = f"{overlap_seed}{separator}{part}" if overlap_seed else part
                else:
                    # Part itself is longer than chunk_size, recursively split using next separator
                    sub_chunks = self._split_with_separators(part, remaining_separators, chunk_size, chunk_overlap)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
