import os

directory = r"d:\trade-psychology-ai\prototype_design"
files = ["analytics.html", "chat.html", "alerts.html", "blowup_shield.html", "dashboard.html"]

for fname in files:
    filepath = os.path.join(directory, fname)
    if not os.path.exists(filepath): continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Fix the missing layout wrapper class!
    content = content.replace('<main class="main-content">', '<main class="flex-1 w-full lg:ml-[260px] relative min-h-screen">')
    
    # Fix the rogue unclosed aria-live divs created in upgrade.py
    if "alerts.html" in fname:
        content = content.replace('<!-- Main Feed (70%) -->\n        <div aria-live="polite">', '<!-- Main Feed (70%) -->')
        content = content.replace('<!-- Card 1: NEW Observation -->\n          <div aria-live="polite" role="alert">', '<!-- Card 1: NEW Observation -->')
        
        # Now apply the live region safely to the parent container specifically, without breaking the grid
        content = content.replace('<div class="w-full lg:w-[65%] 2xl:w-[70%] space-y-5">', '<div class="w-full lg:w-[65%] 2xl:w-[70%] space-y-5" aria-live="polite">')

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Patch applied.")
