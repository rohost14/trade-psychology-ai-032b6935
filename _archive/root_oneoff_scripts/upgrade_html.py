import os
import re

directory = "d:\\trade-psychology-ai\\prototype_design"
files = ["dashboard.html", "analytics.html", "chat.html", "alerts.html", "blowup_shield.html"]

def update_file(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Enhance Spacing (Breathing Room)
    content = content.replace('p-5 sm:p-6', 'p-6 sm:p-8')
    content = content.replace('p-4 sm:p-5', 'p-5 sm:p-6')
    content = content.replace('gap-4 sm:gap-6', 'gap-6 sm:gap-8')
    content = content.replace('p-5', 'p-6')
    content = content.replace('mb-4 sm:mb-6', 'mb-6 sm:mb-8')
    content = content.replace('py-4 sm:py-6', 'py-6 sm:py-8')

    # Enhance Typography Tracking for modern feel
    content = content.replace('text-[28px] font-bold', 'text-[28px] font-bold tracking-tight')
    content = content.replace('text-2xl font-bold', 'text-2xl font-bold tracking-tight')
    content = content.replace('text-[14px] sm:text-[15px] font-bold', 'text-[14px] sm:text-[15px] font-semibold tracking-tight')
    content = content.replace('text-[15px] font-bold', 'text-[15px] font-semibold tracking-tight')
    
    # Avoid duplicate tracking-tight
    content = content.replace('tracking-tight tracking-tight', 'tracking-tight')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for fname in files:
    update_file(os.path.join(directory, fname))
    print(f"Updated {fname}")
