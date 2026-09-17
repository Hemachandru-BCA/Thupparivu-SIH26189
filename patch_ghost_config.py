import re

with open('src/graph/ghost_nodes.py', 'r') as f:
    text = f.read()

# Add new fields to GhostConfig
fields = """    # ghost detection mode
    mode: str = "high_precision"  # "high_precision" or "high_recall"
    resolution: float = 0.35
    require_shared_anchor: bool = True
    top_k: int = 0
"""

text = re.sub(
    r'(class GhostConfig:\n.*?# relation taxonomies)',
    fields + r'\1',
    text,
    flags=re.DOTALL
)

print('Success')
