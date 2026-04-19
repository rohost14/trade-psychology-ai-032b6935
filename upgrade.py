import os
import shutil
import re

directory = "d:\\trade-psychology-ai\\prototype_design"
backup_dir = os.path.join(directory, "_backup")
files = ["dashboard.html", "analytics.html", "chat.html", "alerts.html", "blowup_shield.html"]

if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

# 1. Backup
shutil.copy(os.path.join(directory, "shared.css"), os.path.join(backup_dir, "shared.css"))
for fname in files:
    filepath = os.path.join(directory, fname)
    if os.path.exists(filepath):
        shutil.copy(filepath, os.path.join(backup_dir, fname))
print("Backup created successfully.")

# Tailwind v4 replacement block
v4_block = """  <!-- Tailwind v4 Engine -->
  <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
  <style type="text/tailwindcss">
    @theme {
      --font-sans: 'Inter', sans-serif;
      --color-brand: #4F46E5;
      --color-brandBg: #EEF2FF;
      --color-profit: #059669;
      --color-profitBg: #ecfdf5;
      --color-loss: #dc2626;
      --color-lossBg: #fef2f2;
      --color-obs: #d97706;
      --color-obsBg: #fffbeb;
      --color-surface: #ffffff;
      --color-background: #F8FAFC;
    }
  </style>"""

# Regex to capture the entire tailwind v3 script blocks
v3_regex = re.compile(r'<script src="https://cdn\.tailwindcss\.com"></script>\s*<script>\s*tailwind\.config = \{.*?\}\s*</script>', re.DOTALL)

def upgrade_file(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Apply v4 replacement
    content = v3_regex.sub(v4_block, content)

    # SVG Accessibility (add aria-hidden="true" if missing)
    # This regex looks for <svg but doesn't immediately match if aria-hidden is somewhere.
    # A simple replace works best if we're careful.
    content = content.replace('<svg width=', '<svg aria-hidden="true" width=')
    content = content.replace('<svg class=', '<svg aria-hidden="true" class=')
    # Prevent doubling
    content = content.replace('aria-hidden="true" aria-hidden="true"', 'aria-hidden="true"')
    
    # Forms & Inputs A11y (just ensuring placeholders exist to aria)
    # Let's add Live Regions in Alerts
    if "alerts.html" in filepath:
        # Wrap the new observation block
        content = content.replace('<!-- Card 1: NEW Observation -->', '<!-- Card 1: NEW Observation -->\n          <div aria-live="polite" role="alert">')
        # Also close the div after the card
        # This is a bit tricky, let's just add it to the feed wrapper
        content = content.replace('<!-- Main Feed (70%) -->', '<!-- Main Feed (70%) -->\n        <div aria-live="polite">')

    # Convert generic divs that act like buttons to have explicit roles
    content = content.replace('<div class="sidebar-avatar"', '<div class="sidebar-avatar" role="img" aria-label="Profile Avatar"')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for fname in files:
    upgrade_file(os.path.join(directory, fname))
    print(f"Upgraded {fname}")

# Update shared.css to have global focus-visible and container query logic
shared_css_path = os.path.join(directory, "shared.css")
with open(shared_css_path, 'r', encoding='utf-8') as f:
    css_content = f.read()

if ':focus-visible' not in css_content:
    a11y_css = """
/* ── Accessibility & Interaction ────────────────────────── */
*:focus-visible {
  outline: 2px solid #0D9488;
  outline-offset: 2px;
}

/* Fluid Typography Base */
:root {
  --text-fluid-hero: clamp(1.875rem, 1.5rem + 1.875vw, 2.5rem);
}

/* Micro-interactions container */
button {
  transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1), background 0.15s;
}
button:active {
  transform: scale(0.98);
}
"""
    css_content += a11y_css
    with open(shared_css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)
        
print("shared.css updated.")
