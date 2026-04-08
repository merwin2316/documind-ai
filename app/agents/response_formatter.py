"""
Response formatting utilities for Answer Agent.
Post-processes LLM responses to ensure consistent ChatGPT-style formatting.
"""


def format_list_response(text: str, expected_format: str) -> str:
    """
    Post-process response to ensure proper ChatGPT-style list formatting.
    Converts various formats to: - **Item** - Explanation
    
    Handles:
    - Item names on separate lines
    - Missing hyphens
    - Inconsistent formatting
    """
    if expected_format != "list":
        return text
    
    lines = text.split('\n')
    formatted_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines at start, keep them after content
        if not line:
            if formatted_lines:
                formatted_lines.append('')
            i += 1
            continue
        
        # Keep category headings as-is
        if line.startswith('**') and (':' in line or line.endswith(':')):
            formatted_lines.append(line)
            i += 1
            continue
        
        # Detect item name on separate line (various formats)
        is_item_name = False
        item_name = None
        
        # Format 1: "### Item" or "**Item**"
        if line.startswith('###') or (line.startswith('**') and line.endswith('**') and ':' not in line):
            item_name = line.replace('###', '').replace('**', '').strip()
            is_item_name = True
        
        # Format 2: "• Item" or "- Item" (without explanation on same line)
        elif (line.startswith('•') or line.startswith('-')) and '-' not in line[2:]:
            potential_name = line.lstrip('•-').strip()
            # Check if it's just a name (short, no sentence structure)
            if len(potential_name.split()) <= 4 and not potential_name.endswith('.'):
                item_name = potential_name
                is_item_name = True
        
        # If we found an item name, look for explanation on next line
        if is_item_name and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Check if next line is explanation (not another item)
            if next_line and not next_line.startswith('###') and not next_line.startswith('**') and not next_line.startswith('•'):
                formatted_lines.append(f"- **{item_name}** - {next_line}")
                i += 2
                continue
        
        # Already formatted correctly: "- **Item** - Explanation"
        if line.startswith('-') and '**' in line and ' - ' in line:
            formatted_lines.append(line)
            i += 1
            continue
        
        # Default: keep line as-is (intro, conclusions, etc.)
        formatted_lines.append(line)
        i += 1
    
    return '\n'.join(formatted_lines)
