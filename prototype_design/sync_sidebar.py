import os
import re

directory = r"d:\trade-psychology-ai\prototype_design"
dashboard_path = os.path.join(directory, "dashboard.html")

# 1. Read dashboard.html
with open(dashboard_path, "r", encoding="utf-8") as f:
    dashboard_content = f.read()

# 2. Extract the perfect sidebar
sidebar_match = re.search(r'(<!-- Mobile Backdrop -->.*?)(<main\s)', dashboard_content, re.DOTALL)
if not sidebar_match:
    print("Could not find sidebar block in dashboard.html.")
    exit(1)

base_sidebar_block = sidebar_match.group(1)

# Files to sync
files = ["analytics.html", "chat.html", "alerts.html", "blowup_shield.html"]

def sync_file(fname):
    filepath = os.path.join(directory, fname)
    if not os.path.exists(filepath):
        print(f"Skipping {fname}, does not exist.")
        return
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract where to replace
    file_match = re.search(r'(<!-- Mobile Backdrop -->.*?)(<main\s)', content, re.DOTALL)
    if not file_match:
        print(f"Could not find sidebar block in {fname}.")
        return
        
    # Customize the sidebar block for the specific file
    # First, strip active from dashboard
    current_sidebar = base_sidebar_block.replace('class="sidebar-link active" aria-current="page"', 'class="sidebar-link"')
    
    # Then add active to the correct target
    # Looking for: <a href="analytics.html" class="sidebar-link">
    target_link = f'<a href="{fname}" class="sidebar-link">'
    replacement_link = f'<a href="{fname}" class="sidebar-link active" aria-current="page">'
    
    if target_link in current_sidebar:
        current_sidebar = current_sidebar.replace(target_link, replacement_link)
    else:
        # Sometimes chat.html is not exactly like that?
        print(f"Warning: Could not set active state for {fname}")
        
    # Replace in file content
    new_content = content[:file_match.start(1)] + current_sidebar + content[file_match.start(2):]
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Synchronized sidebar for {fname}")

for f in files:
    sync_file(f)

print("Sidebar sync complete.")
