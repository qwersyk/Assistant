import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MessageChunk:
    type: str  # "codeblock", "table", "latex", "latex_inline", "inline_chunks", "thinking", or "text"
    text: str
    lang: str = ''  # Only used for codeblocks
    subchunks: Optional[List['MessageChunk']] = None  # Only used for inline_chunks

    def __str__(self):
        if self.type == "codeblock":
            return f"<CodeBlock lang='{self.lang}'>\n{self.text}\n</CodeBlock>"
        elif self.type == "table":
            return f"<Table>\n{self.text}\n</Table>"
        elif self.type == "latex":
            return f"<LatexDisplay>\n{self.text}\n</LatexDisplay>"
        elif self.type == "latex_inline":
            return f"<LatexInline>{self.text}</LatexInline>"
        elif self.type == "inline_chunks":
            sub = "\n".join("  " + str(sc) for sc in self.subchunks) if self.subchunks else ""
            return f"<InlineChunks>\n{sub}\n</InlineChunks>"
        elif self.type == "thinking":
            return f"<Thinking>{self.text}</Thinking>"
        elif self.type == "text":
            return f"<Text>{self.text}</Text>"
        else:
            return f"<{self.type}>{self.text}</{self.type}>"

def append_chunk(chunks: List[MessageChunk], new_chunk: MessageChunk):
    """
    Append new_chunk to chunks. If the last chunk and new_chunk are both plain text,
    merge their text.
    """
    if chunks and chunks[-1].type == "text" and new_chunk.type == "text":
        chunks[-1].text += "\n" + new_chunk.text
    else:
        chunks.append(new_chunk)

def is_markdown_table(block: str) -> bool:
    """
    A simple heuristic for detecting markdown tables.
    The block must have at least two lines and the second line should look like a separator.
    """
    lines = block.splitlines()
    if len(lines) < 2:
        return False
    sep_line = lines[1].strip()
    if re.fullmatch(r'[\s\-\:\|]+', sep_line) and '|' in lines[0]:
        return True
    return False

# Regex for display LaTeX blocks (treated as "latex" chunks)
_display_latex_pattern = re.compile(r'(\$\$(.+?)\$\$)|(\\\[(.+?)\\\])', re.DOTALL)

def process_text_with_display_latex(text: str, allow_latex: bool) -> List[MessageChunk]:
    """
    Processes text by detecting display LaTeX blocks (using $$...$$ or \\[…\\]) anywhere in the text.
    Text outside these blocks is processed for inline LaTeX.
    """
    chunks = []
    last_index = 0
    for match in _display_latex_pattern.finditer(text):
        start, end = match.span()
        # Process text before the display LaTeX block.
        if start > last_index:
            intermediate = text[last_index:start]
            chunks.extend(process_inline_by_line(intermediate, allow_latex))
        # Extract the LaTeX content.
        content = None
        if match.group(2) is not None:
            content = match.group(2).strip()
        elif match.group(4) is not None:
            content = match.group(4).strip()
        if content is not None:
            chunks.append(MessageChunk(type="latex", text=content))
        last_index = end
    # Process any remaining text.
    if last_index < len(text):
        remaining = text[last_index:]
        chunks.extend(process_inline_by_line(remaining, allow_latex))
    return chunks

def process_inline_by_line(text: str, allow_latex: bool) -> List[MessageChunk]:
    """
    Processes each line for inline LaTeX.
    When allow_latex is True, each line is scanned for inline LaTeX using:
      - Single-dollar delimiters (avoiding $$),
      - \\( ... \\), and
      - \\[ ... \\] as inline delimiters.
    Pieces on the same line are grouped into an "inline_chunks" chunk.
    When allow_latex is False, each line is returned as a plain text chunk.
    """
    chunks = []
    lines = text.splitlines()
    inline_latex_pattern = re.compile(
        r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)|\\\((.+?)\\\)|\\\[(.+?)\\\]',
        re.DOTALL
    )
    for line in lines:
        if not line:
            continue
        if not allow_latex:
            chunks.append(MessageChunk(type="text", text=line))
            continue

        subchunks = []
        last_index = 0
        for m in inline_latex_pattern.finditer(line):
            start, end = m.span()
            if start > last_index:
                plain = line[last_index:start]
                if plain:
                    subchunks.append(MessageChunk(type="text", text=plain))
            latex_str = m.group(0)
            if latex_str.startswith("$"):
                content = latex_str[1:-1].strip()
            elif latex_str.startswith(r"\("):
                content = latex_str[2:-2].strip()
            elif latex_str.startswith(r"\["):
                content = latex_str[2:-2].strip()
            else:
                content = latex_str
            subchunks.append(MessageChunk(type="latex_inline", text=content))
            last_index = end
        if last_index < len(line):
            remaining = line[last_index:]
            if remaining:
                subchunks.append(MessageChunk(type="text", text=remaining))
        if len(subchunks) == 1 and subchunks[0].type == "text":
            chunks.append(MessageChunk(type="text", text=subchunks[0].text))
        else:
            chunks.append(MessageChunk(type="inline_chunks", text="", subchunks=subchunks))
    return chunks

def process_text_segment_no_think(text: str, allow_latex: bool) -> List[MessageChunk]:
    """
    Processes a segment of text that does not contain any <think> blocks.
    It checks for markdown tables, display LaTeX (if allowed), and then processes
    the text for inline LaTeX.
    """
    text = text.strip()
    if not text:
        return []
    if is_markdown_table(text):
        return [MessageChunk(type="table", text=text)]
    if allow_latex:
        return process_text_with_display_latex(text, allow_latex)
    else:
        return process_inline_by_line(text, allow_latex)

def process_text_segment(text: str, allow_latex: bool) -> List[MessageChunk]:
    """
    Processes a segment of text (outside of codeblocks) and splits it into chunks.
    First it checks for <think> blocks. Any text outside these tags is processed normally.
    """
    chunks = []
    think_pattern = re.compile(r'<think>(.*?)</think>', re.DOTALL)
    last_index = 0
    for m in think_pattern.finditer(text):
        start, end = m.span()
        # Process any text before the <think> block.
        if start > last_index:
            pre_text = text[last_index:start]
            chunks.extend(process_text_segment_no_think(pre_text, allow_latex))
        # Create a thinking chunk.
        think_content = m.group(1).strip()
        chunks.append(MessageChunk(type="thinking", text=think_content))
        last_index = end
    # Process any remaining text after the last <think> block.
    if last_index < len(text):
        remainder = text[last_index:]
        chunks.extend(process_text_segment_no_think(remainder, allow_latex))
    return chunks

def get_message_chunks(message: str, allow_latex: bool = True) -> List[MessageChunk]:
    """
    Splits the input message into a list of MessageChunk objects.
    Processing order:
      1. Extract codeblocks (fenced with ``` ... ```).
      2. Process the remaining text for markdown tables, display LaTeX (if allowed),
         inline LaTeX, and <think> blocks.
    When allow_latex is False, all content that might otherwise be processed as LaTeX
    is treated as plain text.
    Consecutive text chunks are merged.
    """
    chunks = []
    codeblock_pattern = re.compile(r'```(\w+)?\n(.*?)\n```', re.DOTALL)
    last_end = 0
    for match in codeblock_pattern.finditer(message):
        start, end = match.span()
        if start > last_end:
            pre_text = message[last_end:start]
            for chunk in process_text_segment(pre_text, allow_latex):
                append_chunk(chunks, chunk)
        lang = match.group(1) if match.group(1) else ""
        code = match.group(2)
        append_chunk(chunks, MessageChunk(type="codeblock", text=code, lang=lang))
        last_end = end
    if last_end < len(message):
        post_text = message[last_end:]
        for chunk in process_text_segment(post_text, allow_latex):
            append_chunk(chunks, chunk)
    return chunks
