import os
import re

directory = "d:\\trade-psychology-ai\\prototype_design"
files = ["dashboard.html", "analytics.html", "chat.html", "alerts.html", "blowup_shield.html"]

def restore_file(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Strip the abusive tracking-tight
    content = content.replace('tracking-tight tracking-tight', '')
    content = content.replace('tracking-tight', '')

    # 2. Restore Confident Headings
    content = content.replace('text-[20px] sm:text-[24px] font-medium text-slate-900', 'text-2xl sm:text-[28px] font-semibold text-slate-900 tracking-tight')
    content = content.replace('text-2xl sm:text-[28px] font-medium', 'text-2xl sm:text-[32px] font-semibold tracking-tight')
    
    # Dashboard P&L sizes
    content = content.replace('text-[20px] sm:text-3xl font-bold text-slate-900', 'text-2xl sm:text-3xl font-bold text-slate-900')
    content = content.replace('text-3xl sm:text-3xl font-semibold text-slate-900', 'text-3xl sm:text-[40px] font-bold text-slate-900 tracking-tight')
    content = content.replace('text-[22px] font-medium text-slate-900', 'text-[28px] font-semibold text-slate-900')

    # Give UI elements room to breathe (padding expansions)
    content = content.replace('p-6 sm:p-8', 'p-8')
    content = content.replace('gap-6 lg:gap-8', 'gap-8')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for fname in files:
    restore_file(os.path.join(directory, fname))
    print(f"Restored scale in {fname}")
