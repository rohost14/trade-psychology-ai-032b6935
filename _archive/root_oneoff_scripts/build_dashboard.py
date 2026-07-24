import os

filepath = r"d:\trade-psychology-ai\prototype_design\dashboard.html"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = "".join(lines[:161]) # 0 through 160
footer = "".join(lines[498:]) # 498 to end (closing tags and toast script)

# Now we craft the massive middle block!
main_content = """
      <!-- ── NEW UNIFIED HIERARCHY ── -->
      <div class="flex flex-col xl:flex-row gap-6 lg:gap-8 items-start">
        
        <!-- ── Left Column (Main Context - 70%) ── -->
        <div class="w-full xl:w-[70%] space-y-6 lg:space-y-8 min-w-0">
          
          <!-- Unified Hero -->
          <div class="tm-card p-6 sm:p-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
            <div>
              <p class="text-[12px] sm:text-[13px] font-bold text-slate-500 uppercase tracking-widest mb-2 sm:mb-3">Net Realized P&L</p>
              <div class="flex items-center gap-3 sm:gap-4 flex-wrap">
                <span class="text-4xl sm:text-[56px] font-bold text-slate-900 tabular tracking-tighter leading-none">₹24,500.00</span>
                <span class="text-[13px] sm:text-[15px] font-black text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-md shadow-sm mt-1 sm:mt-0">+5.76%</span>
              </div>
            </div>
            
            <div class="flex flex-col md:items-end gap-2 sm:gap-3 w-full md:w-auto mt-2 md:mt-0 pt-4 md:pt-0 border-t md:border-0 border-slate-100">
              <span class="text-[11px] sm:text-[12px] font-bold text-slate-500 uppercase tracking-widest">System Risk State</span>
              <div class="flex items-center gap-2.5 bg-emerald-50/80 border border-emerald-200 px-4 py-2.5 sm:py-3 rounded-lg shadow-sm w-full md:w-auto justify-center">
                <span class="relative flex h-2.5 w-2.5">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
                <span class="text-[14px] sm:text-[15px] font-black text-emerald-700 uppercase tracking-widest">Safe Mode Active</span>
              </div>
            </div>
          </div>

          <!-- Behavioral Alerts Feed -->
          <div class="tm-card border border-amber-200/60 shadow-sm bg-white border-y border-slate-200">
            <div class="p-5 sm:p-6 flex items-center justify-between border-b border-slate-100">
              <h2 class="text-[14px] sm:text-[15px] font-bold text-slate-900 flex items-center gap-2">
                <svg aria-hidden="true" class="w-4 h-4 text-obs" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                Behavioral Alerts
              </h2>
              <span class="bg-amber-100 text-amber-800 text-[11px] sm:text-[12px] font-black px-2.5 py-0.5 rounded-md uppercase tracking-wider shrink-0">2 Action Req</span>
            </div>

            <div class="divide-y divide-slate-100">
              <div class="p-5 sm:p-6 hover:bg-slate-50 flex flex-col sm:flex-row items-start gap-4 transition-colors">
                <div class="hidden sm:block w-1.5 h-[50px] bg-red-500 rounded-full mt-1 shrink-0"></div>
                <div class="flex-1 w-full min-w-0">
                  <div class="flex justify-between items-center mb-2 gap-1 block sm:hidden">
                    <span class="w-1.5 h-4 bg-red-500 rounded-full shrink-0 block"></span>
                    <h4 class="font-bold text-[14px] text-slate-900 w-full truncate ml-1">Revenge Matrix Triggered</h4>
                    <span class="text-[12px] tabular text-slate-500 font-bold shrink-0 ml-auto">14m</span>
                  </div>
                  <div class="hidden sm:flex justify-between items-center mb-2">
                    <h4 class="font-bold text-[15px] text-slate-900 truncate">Revenge Matrix Triggered</h4>
                    <span class="text-[13px] tabular text-slate-500 font-bold">14 mins ago</span>
                  </div>
                  <p class="text-[13px] sm:text-[14px] text-slate-600 leading-relaxed mb-4">Re-entered BANKNIFTY 48000 PE immediately after a stop-out loss. Acknowledge this pattern before taking the next trade.</p>
                  <div class="flex gap-2 sm:gap-3">
                    <button class="px-4 py-2 bg-red-50 text-red-700 font-bold text-[13px] rounded-lg border border-red-100 shadow-sm transition hover:bg-red-100">Review & Halt</button>
                    <button class="px-4 py-2 bg-white border border-slate-200 text-slate-700 font-bold text-[13px] rounded-lg shadow-sm transition hover:bg-slate-50">Dismiss</button>
                  </div>
                </div>
              </div>

              <div class="p-5 sm:p-6 hover:bg-slate-50 flex items-start gap-3 sm:gap-4 transition-colors bg-amber-50/20">
                <div class="w-1.5 h-[40px] bg-amber-400 rounded-full mt-1 shrink-0 hidden sm:block"></div>
                <div class="flex-1 w-full min-w-0">
                  <div class="flex justify-between items-center mb-1 sm:mb-2 gap-1">
                    <h4 class="font-bold text-[14px] sm:text-[15px] text-slate-900 truncate flex items-center gap-2">
                      <div class="sm:hidden w-1.5 h-4 bg-amber-400 rounded-full"></div>Volume Surge Warning
                    </h4>
                    <span class="text-[12px] sm:text-[13px] tabular text-slate-500 font-bold shrink-0">42 mins ago</span>
                  </div>
                  <p class="text-[13px] sm:text-[14px] text-slate-600 leading-relaxed">Position sizing on your last 2 trades exceeds daily psychological boundary by 15.4%.</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Active Positions -->
          <div class="tm-card">
            <div class="flex justify-between items-center p-5 sm:p-6 border-b border-slate-100">
              <h2 class="text-[14px] sm:text-[15px] font-bold text-slate-900">Active Positions <span class="text-slate-400 font-medium ml-1 tabular">(3)</span></h2>
              <button class="text-[13px] font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded border border-emerald-100 transition hover:bg-emerald-100">Exit All</button>
            </div>
            <div class="overflow-x-auto table-scroll-wrap">
              <table class="w-full text-left whitespace-nowrap min-w-[600px] mb-2 border-collapse">
                <thead>
                  <tr class="bg-slate-50/50">
                    <th class="w-2/5 px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Instrument</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Qty</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Avg Entry</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">LTP</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Floating P&L</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr class="hover:bg-slate-50/80 transition cursor-pointer">
                    <td class="px-6 py-4">
                      <div class="flex items-center gap-3">
                        <span class="px-2 py-1 bg-blue-50 border border-blue-100 text-blue-700 font-bold text-[11px] rounded uppercase shrink-0 shadow-sm">CE</span>
                        <div class="flex flex-col">
                          <span class="font-bold text-slate-900 text-[13px]">NIFTY 24000 CE</span>
                          <span class="text-[12px] text-slate-500 font-medium">24 Oct Expiry</span>
                        </div>
                      </div>
                    </td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-900">1,200</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-medium text-slate-500">145.20</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-700">165.40</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-black text-emerald-600">+₹24,240.00</td>
                  </tr>
                  <!-- New Extra position -->
                  <tr class="hover:bg-slate-50/80 transition cursor-pointer">
                    <td class="px-6 py-4">
                      <div class="flex items-center gap-3">
                        <span class="px-2 py-1 bg-stone-100 border border-stone-200 text-slate-600 font-bold text-[11px] rounded uppercase shrink-0 shadow-sm">EQ</span>
                        <div class="flex flex-col">
                          <span class="font-bold text-slate-900 text-[13px]">HDFCBANK</span>
                          <span class="text-[12px] text-slate-500 font-medium">CNC</span>
                        </div>
                      </div>
                    </td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-900">500</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-medium text-slate-500">1,540.00</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-700">1,542.50</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-black text-emerald-600">+₹1,250.00</td>
                  </tr>
                  <!-- New Extra position Negative -->
                  <tr class="hover:bg-slate-50/80 transition cursor-pointer">
                    <td class="px-6 py-4">
                      <div class="flex items-center gap-3">
                        <span class="px-2 py-1 bg-red-50 border border-red-100 text-red-700 font-bold text-[11px] rounded uppercase shrink-0 shadow-sm">PE</span>
                        <div class="flex flex-col">
                          <span class="font-bold text-slate-900 text-[13px]">BANKNIFTY 48500 PE</span>
                          <span class="text-[12px] text-slate-500 font-medium">24 Oct Expiry</span>
                        </div>
                      </div>
                    </td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-900">150</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-medium text-slate-500">210.50</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-700">203.90</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-black text-rose-600">-₹990.00</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Closed Positions -->
          <div class="tm-card mt-8">
            <div class="flex justify-between items-center p-5 sm:p-6 border-b border-slate-100">
              <h2 class="text-[14px] sm:text-[15px] font-bold text-slate-900">Recently Closed <span class="text-slate-400 font-medium ml-1 tabular">(5)</span></h2>
            </div>
            <div class="overflow-x-auto table-scroll-wrap">
              <table class="w-full text-left whitespace-nowrap min-w-[600px] mb-2 border-collapse">
                <thead>
                  <tr class="bg-slate-50/50">
                    <th class="w-2/5 px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Instrument</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Status</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Exit Price</th>
                    <th class="text-right px-6 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-100">Realized P&L</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr class="hover:bg-slate-50/80 transition">
                    <td class="px-6 py-4">
                      <div class="flex items-center gap-3">
                        <span class="px-2 py-1 bg-blue-50 border border-blue-100 text-blue-700 font-bold text-[11px] rounded uppercase shrink-0 shadow-sm">CE</span>
                        <div class="flex flex-col">
                          <span class="font-bold text-slate-900 text-[13px] line-through decoration-slate-300">NIFTY 23900 CE</span>
                          <span class="text-[12px] text-slate-500 font-medium">Auto-squared</span>
                        </div>
                      </div>
                    </td>
                    <td class="px-6 py-4 text-right">
                      <span class="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-1 border border-emerald-100 rounded shadow-sm">TP HIT</span>
                    </td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-700">188.00</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-black text-emerald-600">+₹8,400.00</td>
                  </tr>
                  <tr class="hover:bg-slate-50/80 transition">
                    <td class="px-6 py-4">
                      <div class="flex items-center gap-3">
                        <span class="px-2 py-1 bg-stone-100 border border-stone-200 text-slate-600 font-bold text-[11px] rounded uppercase shrink-0 shadow-sm">EQ</span>
                        <div class="flex flex-col">
                          <span class="font-bold text-slate-900 text-[13px] line-through decoration-slate-300">RELIANCE</span>
                          <span class="text-[12px] text-slate-500 font-medium">Manual Exit</span>
                        </div>
                      </div>
                    </td>
                    <td class="px-6 py-4 text-right">
                      <span class="text-[11px] font-bold text-slate-600 bg-slate-100 px-2 py-1 border border-slate-200 rounded shadow-sm">CLOSED</span>
                    </td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-bold text-slate-700">2,940.50</td>
                    <td class="px-6 py-4 text-right tabular text-[14px] font-black text-rose-600">-₹2,100.00</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- ── Right Column (Statistics Rail - 30%) ── -->
        <div class="w-full xl:w-[30%] space-y-6 lg:space-y-8 xl:sticky xl:top-[40px] min-w-0">
          
          <!-- Trading Context Grid -->
          <div class="tm-card p-6 sm:p-7 shadow-sm">
            <h3 class="text-[13px] font-bold text-slate-500 uppercase tracking-widest mb-6 border-b border-slate-100 pb-4">Trading Context</h3>
            
            <div class="space-y-5">
              <div class="flex justify-between items-center group">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-medium group-hover:text-slate-900 transition">Win Rate</span>
                <span class="text-[14px] sm:text-[15px] font-black text-slate-900 tabular">62.5%</span>
              </div>
              
              <div class="flex justify-between items-center group">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-medium group-hover:text-slate-900 transition flex items-center gap-1.5">
                  Emotional Tax
                  <div class="w-3 h-3 rounded bg-red-100 flex items-center justify-center"><div class="w-1.5 h-1.5 bg-red-500 rounded-sm"></div></div>
                </span>
                <span class="text-[14px] sm:text-[15px] font-black text-rose-600 tabular">-₹380 <span class="text-[11px] font-bold text-rose-400 bg-rose-50 px-1 py-0.5 rounded ml-1">18%</span></span>
              </div>
              
              <div class="flex justify-between items-center group">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-medium group-hover:text-slate-900 transition">Trades Executed</span>
                <span class="text-[14px] sm:text-[15px] font-black text-slate-900 tabular">8 <span class="text-[12px] text-slate-400 font-bold ml-1">/ 10</span></span>
              </div>
              
              <div class="flex justify-between items-center group">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-medium group-hover:text-slate-900 transition">Avg Win</span>
                <span class="text-[14px] sm:text-[15px] font-black text-emerald-600 tabular">+₹6,400</span>
              </div>
              
              <div class="flex justify-between items-center group border-b border-slate-50 pb-5">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-medium group-hover:text-slate-900 transition">Avg Loss</span>
                <span class="text-[14px] sm:text-[15px] font-black text-rose-600 tabular">-₹2,500</span>
              </div>
              
              <div class="flex justify-between items-center pt-1">
                <span class="text-[13px] sm:text-[14px] text-slate-600 font-bold">Reward to Risk</span>
                <span class="text-[15px] sm:text-[16px] font-black text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded shadow-sm tabular">2.56</span>
              </div>
            </div>
          </div>

          <!-- BLOWUP SHIELD Card (Retained) -->
          <div class="tm-card p-6 sm:p-7 shadow-sm border border-slate-200">
            <div class="flex items-center justify-between mb-6 sm:mb-8">
              <h3 class="font-bold text-slate-900 text-[14px] sm:text-[15px] flex items-center gap-1.5 sm:gap-2">
                <svg aria-hidden="true" class="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                </svg>
                Blowup Shield
              </h3>
              <span class="text-[11px] sm:text-[11px] font-black uppercase tracking-wider text-slate-500 bg-slate-100 px-2 py-1 rounded">Active</span>
            </div>

            <div class="flex items-end gap-2 mb-1.5">
              <span class="text-[40px] sm:text-[48px] font-black tracking-tighter leading-none text-obs tabular">40%</span>
            </div>
            <p class="text-[13px] text-slate-500 mb-5 font-medium leading-relaxed">Alerts heeded &middot; <strong class="text-slate-700">2/5</strong> total response rate</p>

            <div class="h-2 rounded-full overflow-hidden bg-slate-100 mb-2 shadow-inner">
              <div class="h-full rounded-full bg-amber-500 w-[40%] transition-all"></div>
            </div>
            <div class="flex items-center justify-between mb-6 sm:mb-8">
              <span class="text-[11px] text-slate-500 font-bold uppercase tracking-wider">0%</span>
              <span class="text-[11px] text-slate-500 font-bold uppercase tracking-wider">100% Guard</span>
            </div>

            <div class="flex items-center justify-between rounded-lg px-3 sm:px-4 py-3 bg-red-50 border border-red-100 shadow-sm mb-5 sm:mb-6">
              <span class="text-[13px] font-bold text-red-900 leading-tight">Follow-on Loss</span>
              <span class="text-[14px] font-black text-rose-600 tabular bg-white px-2 py-0.5 rounded shadow-sm border border-red-50">-₹4,500</span>
            </div>

            <button class="w-full py-2.5 bg-white border border-slate-200 shadow-sm text-slate-700 text-[13px] font-bold rounded-lg hover:bg-slate-50 transition active:scale-95">View Shield Log &rarr;</button>
          </div>

        </div>
      </div>
"""

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(header + main_content + footer)

print("Dashboard successfully refactored!")
