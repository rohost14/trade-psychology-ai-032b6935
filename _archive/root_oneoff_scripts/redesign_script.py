import os

directory = "d:\\trade-psychology-ai\\prototype_design"
files = ["dashboard.html", "analytics.html", "chat.html", "alerts.html", "blowup_shield.html"]

def redesign_file(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Kill the gradients & blobs
    content = content.replace('bg-gradient-to-br from-indigo-50/80 to-transparent rounded-bl-full opacity-60', 'hidden')
    content = content.replace('bg-gradient-to-br from-white to-red-50/30', 'bg-white border border-slate-200 shadow-sm ring-1 ring-slate-900/5')
    content = content.replace('bg-gradient-to-br from-white to-indigo-50/30', 'bg-white border border-slate-200 shadow-sm ring-1 ring-slate-900/5')
    content = content.replace('bg-gradient-to-r from-white to-amber-50/10', 'bg-white border-y border-slate-200')
    content = content.replace('bg-gradient-to-br from-white to-gray-50 border border-gray-200', 'bg-white border border-slate-200 shadow-sm ring-1 ring-slate-900/5')

    # 2. Kill the bouncy animations
    content = content.replace('animate-in-up', 'transition-opacity duration-300')
    content = content.replace('delay-100', '')
    content = content.replace('delay-200', '')
    content = content.replace('delay-300', '')

    # 3. Typography Flattening
    # Hero/Large
    content = content.replace('text-[40px] font-black', 'text-3xl font-semibold tracking-tight')
    content = content.replace('text-[28px] font-bold', 'text-[24px] font-medium tracking-tight')
    content = content.replace('text-2xl font-bold', 'text-[22px] font-medium tracking-tight')
    content = content.replace('text-3xl sm:text-[40px]', 'text-3xl')
    content = content.replace('text-[28px]', 'text-[24px]')
    content = content.replace('text-2xl', 'text-[20px]')
    
    # Text colors logic
    content = content.replace('text-gray-900', 'text-slate-900')
    content = content.replace('text-gray-800', 'text-slate-800')
    content = content.replace('text-gray-700', 'text-slate-700')
    content = content.replace('text-gray-600', 'text-slate-600')
    content = content.replace('text-gray-500', 'text-slate-500')
    content = content.replace('text-gray-400', 'text-slate-500')
    
    # Border & Bg logic
    content = content.replace('border-gray-50', 'border-slate-100')
    content = content.replace('border-gray-100', 'border-slate-100')
    content = content.replace('border-gray-200', 'border-slate-200')
    content = content.replace('bg-gray-100', 'bg-slate-100')
    content = content.replace('bg-gray-50', 'bg-slate-50')
    
    # Bold Labels fixed
    content = content.replace('font-bold tracking-tight text-slate-900', 'font-semibold tracking-tight text-slate-900')
    content = content.replace('font-bold text-slate-500 uppercase', 'font-medium text-slate-500 uppercase')
    content = content.replace('font-bold text-slate-400 uppercase', 'font-medium text-slate-400 uppercase')
    content = content.replace('font-bold text-profit', 'font-medium text-emerald-600')
    content = content.replace('font-bold text-loss', 'font-medium text-rose-600')
    
    # Table headers
    content = content.replace('<th>', '<th class="text-xs font-medium text-slate-500 uppercase tracking-wider">')

    # Remove massive left borders
    content = content.replace('border-l-4 border-l-brand', 'border border-slate-200 shadow-sm ring-1 ring-slate-900/5')
    content = content.replace('border-l-4 border-l-profit', 'border border-slate-200 shadow-sm ring-1 ring-slate-900/5')
    content = content.replace('border-l-4 border-l-loss', 'border border-slate-200 shadow-sm ring-1 ring-slate-900/5')

    # Fix chat bubbles
    content = content.replace('bubble-user', 'bg-slate-800 text-white rounded-2xl rounded-tr-sm')
    content = content.replace('bubble-ai', 'bg-slate-50 border border-slate-200 text-slate-900 rounded-2xl rounded-tl-sm')
    
    # Smaller label fixes
    content = content.replace('text-[11px]', 'text-[13px]')
    content = content.replace('text-[12px]', 'text-[13px]')
    content = content.replace('text-[10px]', 'text-[12px]')
    content = content.replace('text-[9px]', 'text-[11px]')

    # Change default background to bright slate-50
    content = content.replace('bg-[#F9FAFB]', 'bg-[#F8FAFC]')
    content = content.replace('bg-stripe-header', 'hidden') # Remove stripe completely

    # Change heavy black primary buttons to ghost
    content = content.replace('bg-gray-900 hover:bg-gray-800 text-white', 'bg-white border border-slate-200 hover:bg-slate-50 text-slate-800')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for fname in files:
    redesign_file(os.path.join(directory, fname))
    print(f"Redesigned {fname}")
