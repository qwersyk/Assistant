import re 
import html
import xml 
import xml.dom.minidom
import json


def quote_string(s):
    if "'" in s:
        return "'" + s.replace("'", "'\\''") + "'"
    else:
        return "'" + s + "'"

def markwon_to_pango(markdown_text):
    markdown_text = html.escape(markdown_text)
    initial_string = markdown_text
    # Convert bold text
    markdown_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', markdown_text)
    
    # Convert italic text
    markdown_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', markdown_text)

    # Convert monospace text
    markdown_text = re.sub(r'`(.*?)`', r'<tt>\1</tt>', markdown_text)

    # Convert strikethrough text
    markdown_text = re.sub(r'~(.*?)~', r'<span strikethrough="true">\1</span>', markdown_text)
    
    # Convert links
    markdown_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', markdown_text)
    
    # Convert headers
    absolute_sizes = ['xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large']
    markdown_text = re.sub(r'^(#+) (.*)$', lambda match: f'<span font_weight="bold" font_size="{absolute_sizes[6 - len(match.group(1))]}">{match.group(2)}</span>', markdown_text, flags=re.MULTILINE)
    
    # Check if the generated text is valid. If not just print it unformatted
    try:
        xml.dom.minidom.parseString("<html>" + markdown_text + "</html>")
    except Exception as e:
        print(markdown_text)
        print(e)
        return initial_string
    return markdown_text

def human_readable_size(size: float, decimal_places:int =2) -> str:
    size = int(size)
    unit = ''
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if size < 1024.0 or unit == 'PiB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def extract_json(input_string: str) -> str:
    """Extract JSON string from input string

    Args:
        input_string (): The input string 

    Returns:
        str: The JSON string 
    """
    # Regular expression to find JSON objects or arrays
    json_pattern = re.compile(r'\{.*?\}|\[.*?\]', re.DOTALL)
    
    # Find all JSON-like substrings
    matches = json_pattern.findall(input_string) 
    # Parse each match and return the first valid JSON
    for match in matches:
        try:
            json_data = json.loads(match)
            return match
        except json.JSONDecodeError:
            continue
    print("Wrong JSON", input_string)
    return "{}"


def remove_markdown(text: str) -> str:
    """
    Remove markdown from text

    Args:
        text: The text to remove markdown from 

    Returns:
        str: The text without markdown 
    """
    # Remove headers
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    
    # Remove emphasis (bold and italic)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'__(.*?)__', r'\1', text)          # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)        # Italic
    text = re.sub(r'_(.*?)_', r'\1', text)            # Italic
    
    # Remove inline code
    text = re.sub(r'`([^`]*)`', r'\1', text)
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove links, keep the link text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove images, keep the alt text
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Remove strikethrough
    text = re.sub(r'~~(.*?)~~', r'\1', text)

    # Remove blockquotes
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # Remove unordered list markers
    text = re.sub(r'^\s*[-+*]\s+', '', text, flags=re.MULTILINE)

    # Remove ordered list markers
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove extra newlines
    text = re.sub(r'\n{2,}', '\n', text)

    return text.strip()

def convert_think_codeblocks(text: str) -> str:
    """Convert think codeblocks to markdown

    Args:
        text (str): The text to convert 

    Returns:
        str: The converted text 
    """
    return text.replace("<think>", "```think").replace("</think>", "```")
