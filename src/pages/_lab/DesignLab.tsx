/**
 * DesignLab — ground-up design exploration, lab only.
 *
 * Nothing here is imported by the real app. `src/pages/Dashboard.tsx` and
 * `src/components/dashboard/` are untouched; this file only adds a route.
 *
 * Three directions, derived from the references named on 2026-08-05 rather than
 * synthesised: Zerodha Kite, Dhan, Tickertape. What those three actually share —
 * and what four earlier attempts got wrong — is recorded in the notes below each
 * variant, and in the constants here:
 *
 *   - BLUE is the UI accent. Red and green are reserved for money. Earlier
 *     revisions used teal, which sits next to profit green and muddied both.
 *   - Radius stays under 8px. Zerodha's system is "consistently under 8px";
 *     10-12px reads consumer rather than professional.
 *   - Weights 400/500, 600 only for a figure or a section title.
 *   - Red means down. Indian convention, and Tickertape uses it at full strength.
 *   - Containment varies BY CONTENT TYPE, never by a single global rule. That is
 *     the whole point of the exercise.
 *
 * All styling is scoped under `.dl-root` in one <style> block so it cannot be
 * reached by — or reach into — the app's global CSS, which carries an
 * `h1-h5 { color: hsl(var(--foreground)) }` override that has bitten lab pages
 * before.
 */
import { useState } from 'react';

type Variant = 'terminal' | 'market' | 'focused';

const VARIANTS: { id: Variant; name: string; ref: string }[] = [
  { id: 'terminal', name: 'A · Terminal', ref: 'Kite — flat panels, dense, no ornament' },
  { id: 'market',   name: 'B · Market',   ref: 'Tickertape — dark chrome, mixed containment' },
  { id: 'focused',  name: 'C · Focused',  ref: 'Hybrid — one hero, selective panels' },
];

/* ── data (the demo session used throughout the design work) ───────────── */
// `Size Escalation` (retired 2026-08-27) and `Early Exit` (retired 2026-08-30)
// were the first two mocks here until 2026-09-03. A design lab is where the
// next screen gets copied from, so a retired detector sitting in it ships.
const ALERTS = [
  { t: 'Martingale / Averaging Down', sev: 'danger' as const, when: 'now',
    b: 'BANKNIFTY 45500 PE entry at 100 lots — 4× your average size — 8 min after ₹2,600 loss. Win rate on oversized entries: 28% vs 60% baseline.' },
  { t: 'Added to a Losing Position', sev: 'caution' as const, when: 'now',
    b: 'NIFTY CE averaged down twice while 18% under water. Position now 3× the size you opened it at.' },
  { t: 'No Stop-Loss', sev: 'danger' as const, when: 'now',
    b: 'FINNIFTY 19800 CE open 47 min with no stop-loss. Unrealised loss: ₹3,200. Positions without stop-loss average 3× larger final loss for you.' },
];

const POSITIONS = [
  { sym: 'FINNIFTY 19800 CE', prod: 'NRML', qty: 40,  entry: '172.40', ltp: '168.20', chg: -2.44, pnl: -3200 },
  { sym: 'BANKNIFTY 45500 PE', prod: 'MIS', qty: 100, entry: '214.80', ltp: '218.44', chg: +1.69, pnl: +3640 },
];

const METRICS = [
  { k: 'Trades',      v: '8',      u: '0.8× pace' },
  { k: 'Loss budget', v: '₹16.1k', u: 'of ₹25k' },
  { k: 'Win rate',    v: '50%',    u: '8 trades' },
  { k: 'Unrealized',  v: '+₹440',  u: '', up: true },
];

const inr = (n: number) => (n < 0 ? '−' : '+') + '₹' + Math.abs(n).toLocaleString('en-IN');

/* ── shared fragments ──────────────────────────────────────────────────── */
const NAV = [
  ['Dashboard', true], ['Analytics', false], ['Alerts', false], ['Chat', false],
  ['Reports', false], ['Journal', false], ['My Rules', false], ['My Record', false],
] as const;

function SessionFigures() {
  return (
    <>
      <div className="dl-lbl">Day P&amp;L</div>
      <div className="dl-pnl">−₹8,455</div>
      <div className="dl-pnlsub">
        Booked <b className="dl-dn">−₹8,895</b> · Unrealized <b className="dl-up">+₹440</b>
      </div>
    </>
  );
}

function Metrics({ bare = false }: { bare?: boolean }) {
  return (
    <div className={bare ? 'dl-mets dl-mets-bare' : 'dl-mets'}>
      {METRICS.map(m => (
        <div className="dl-met" key={m.k}>
          <div className="dl-lbl">{m.k}</div>
          <div className={'dl-metv' + (m.up ? ' dl-up' : '')}>
            {m.v}{m.u && <span className="dl-metu">{m.u}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function AlertRows() {
  return (
    <>
      {ALERTS.map(a => (
        <div className={'dl-arow dl-' + a.sev} key={a.t}>
          <div>
            <div className="dl-ahead">
              <span className="dl-at">{a.t}</span>
              <span className={'dl-bd dl-bd-' + a.sev}>{a.sev === 'danger' ? 'DANGER' : 'CAUTION'}</span>
            </div>
            <p className="dl-ab">{a.b}</p>
          </div>
          <span className="dl-when">{a.when}</span>
        </div>
      ))}
    </>
  );
}

function PositionsTable() {
  return (
    <table className="dl-tbl">
      <thead>
        <tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>LTP</th><th>Chg %</th><th>P&amp;L</th></tr>
      </thead>
      <tbody>
        {POSITIONS.map(p => (
          <tr key={p.sym}>
            <td><span className="dl-sym">{p.sym}</span><span className="dl-prod">{p.prod}</span></td>
            <td>{p.qty}</td><td>{p.entry}</td><td>{p.ltp}</td>
            <td className={p.chg < 0 ? 'dl-dn' : 'dl-up'}>{p.chg < 0 ? '−' : '+'}{Math.abs(p.chg)}%</td>
            <td className={p.pnl < 0 ? 'dl-dn' : 'dl-up'}>{inr(p.pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ── A · Terminal ──────────────────────────────────────────────────────── */
function Terminal() {
  return (
    <div className="dl-app">
      <aside className="dl-side">
        <div className="dl-brand"><span className="dl-mark" />TradeMentor</div>
        {NAV.map(([n, on]) => (
          <div className={'dl-nav' + (on ? ' on' : '')} key={n}>{n}</div>
        ))}
      </aside>
      <main className="dl-main">
        <div className="dl-topbar">
          <span className="dl-crumb">Dashboard</span>
          <span className="dl-status"><i />CLOSED · 13:43</span>
          <span className="dl-spacer" />
          <span className="dl-chip">Today</span>
        </div>

        <div className="dl-grid2">
          <section className="dl-panel">
            <div className="dl-ph">Session</div>
            <div className="dl-pb"><SessionFigures /></div>
          </section>
          <section className="dl-panel">
            <div className="dl-ph">Limits &amp; pace</div>
            <div className="dl-pb"><Metrics /></div>
          </section>
        </div>

        <section className="dl-panel">
          <div className="dl-ph">What we caught today <span className="dl-ct">3</span>
            <span className="dl-spacer" /><a className="dl-lnk">View all</a></div>
          <div className="dl-pb dl-pb-flush"><AlertRows /></div>
        </section>

        <section className="dl-panel">
          <div className="dl-ph">Open positions <span className="dl-ct dl-ct-q">2</span>
            <span className="dl-spacer" /><span className="dl-lbl">Unrealized</span>
            <span className="dl-up dl-mono">+₹440.00</span></div>
          <div className="dl-pb dl-pb-flush"><PositionsTable /></div>
        </section>
      </main>
    </div>
  );
}

/* ── B · Market ────────────────────────────────────────────────────────── */
function Market() {
  return (
    <div className="dl-app dl-app-chrome">
      {/* dark chrome stays dark in BOTH themes — Tickertape's signature move */}
      <div className="dl-tape">
        <span className="dl-tape-i">NIFTY 50 <b>24,584.40</b> <em className="dl-dn">▾ 0.12%</em></span>
        <span className="dl-tape-i">BANKNIFTY <b>57,679.25</b> <em className="dl-dn">▾ 0.39%</em></span>
        <span className="dl-tape-i">FINNIFTY <b>23,110.05</b> <em className="dl-up">▴ 0.21%</em></span>
        <span className="dl-tape-i">SENSEX <b>80,604.65</b> <em className="dl-dn">▾ 0.18%</em></span>
      </div>
      <div className="dl-topnav">
        <span className="dl-brand2"><span className="dl-mark" />TradeMentor</span>
        {NAV.slice(0, 4).map(([n, on]) => (
          <span className={'dl-tn' + (on ? ' on' : '')} key={n}>{n}</span>
        ))}
        <span className="dl-spacer" />
        <span className="dl-tn">More ⌄</span>
        <span className="dl-acct">ZA1234</span>
      </div>

      <div className="dl-body">
        {/* LEFT: reference material — this IS a card */}
        <aside className="dl-col">
          <div className="dl-card">
            <div className="dl-cardh">Session scorecard</div>
            <div className="dl-scorerow">
              <span className="dl-sk">Pace</span>
              <span className="dl-pill dl-pill-ok">Normal</span>
              <span className="dl-sd">8 trades, 0.8× your median</span>
            </div>
            <div className="dl-scorerow">
              <span className="dl-sk">Sizing</span>
              <span className="dl-pill dl-pill-bad">High</span>
              <span className="dl-sd">One entry at 4× average size</span>
            </div>
            <div className="dl-scorerow">
              <span className="dl-sk">Stops</span>
              <span className="dl-pill dl-pill-bad">Missing</span>
              <span className="dl-sd">1 of 2 open positions unprotected</span>
            </div>
            <div className="dl-scorerow">
              <span className="dl-sk">Cooldown</span>
              <span className="dl-pill dl-pill-ok">Honoured</span>
              <span className="dl-sd">No re-entry inside 15 min</span>
            </div>
          </div>

          <div className="dl-card">
            <div className="dl-cardh">Loss budget</div>
            <div className="dl-budget">
              <div className="dl-track"><i style={{ width: '64%' }} /></div>
              <div className="dl-bmeta"><b>₹16.1k</b> of ₹25,000 used</div>
            </div>
          </div>
        </aside>

        {/* RIGHT: the primary object — NOT a card, bare on the page */}
        <main className="dl-col dl-col-main">
          <div className="dl-hero">
            <div><SessionFigures /></div>
            <Metrics bare />
          </div>

          <div className="dl-sech">
            <h3>What we caught today</h3><span className="dl-ct">3</span>
            <span className="dl-spacer" /><a className="dl-lnk">View all →</a>
          </div>
          <AlertRows />

          <div className="dl-sech">
            <h3>Open positions</h3><span className="dl-ct dl-ct-q">2</span>
            <span className="dl-spacer" /><span className="dl-lbl">Unrealized</span>
            <span className="dl-up dl-mono">+₹440.00</span>
          </div>
          <PositionsTable />
        </main>
      </div>
    </div>
  );
}

/* ── C · Focused ───────────────────────────────────────────────────────── */
function Focused() {
  return (
    <div className="dl-app">
      <aside className="dl-side dl-side-f">
        <div className="dl-brand"><span className="dl-mark" />TradeMentor</div>
        {NAV.map(([n, on]) => (
          <div className={'dl-nav' + (on ? ' on' : '')} key={n}>{n}</div>
        ))}
      </aside>
      <main className="dl-main dl-main-f">
        {/* one hero, bare, generous */}
        <div className="dl-fhero">
          <div><SessionFigures /></div>
          <div className="dl-fstatus">
            <span className="dl-status"><i />CLOSED · 13:43</span>
            <Metrics bare />
          </div>
        </div>

        {/* alerts bare — they are the point of the page */}
        <div className="dl-sech">
          <h3>What we caught today</h3><span className="dl-ct">3</span>
          <span className="dl-spacer" /><a className="dl-lnk">View all →</a>
        </div>
        <AlertRows />

        {/* positions in a panel — reference data, not the point */}
        <section className="dl-panel dl-panel-f">
          <div className="dl-ph">Open positions <span className="dl-ct dl-ct-q">2</span>
            <span className="dl-spacer" /><span className="dl-lbl">Unrealized</span>
            <span className="dl-up dl-mono">+₹440.00</span></div>
          <div className="dl-pb dl-pb-flush"><PositionsTable /></div>
        </section>
      </main>
    </div>
  );
}

/* ── page ──────────────────────────────────────────────────────────────── */
export default function DesignLab() {
  const [variant, setVariant] = useState<Variant>('terminal');
  const [dark, setDark] = useState(true);
  const active = VARIANTS.find(v => v.id === variant)!;

  return (
    <div className={`dl-root dl-${variant} ${dark ? 'dl-dark' : 'dl-light'}`}>
      <style>{CSS}</style>

      <div className="dl-bar">
        <span className="dl-barlabel">Design lab</span>
        <div className="dl-seg">
          {VARIANTS.map(v => (
            <button key={v.id} className={variant === v.id ? 'sel' : ''}
                    onClick={() => setVariant(v.id)}>{v.name}</button>
          ))}
        </div>
        <span className="dl-barref">{active.ref}</span>
        <span className="dl-spacer" />
        <button className="dl-toggle" onClick={() => setDark(d => !d)}>
          {dark ? '☾ Dark' : '☀ Light'}
        </button>
      </div>

      <div className="dl-stage">
        {variant === 'terminal' && <Terminal />}
        {variant === 'market' && <Market />}
        {variant === 'focused' && <Focused />}
      </div>
    </div>
  );
}

/* ── styles ────────────────────────────────────────────────────────────── */
const CSS = `
.dl-root{
  --blue:#2A6FC9; --blue-bg:#EAF2FC;
  --up:#14804A; --up-bg:#E8F5EE;
  --dn:#C1291F; --dn-bg:#FCECEA;
  --wn:#9A6208; --wn-bg:#FBF1DF;
  --r:6px;
  font-family:Inter,system-ui,-apple-system,sans-serif;
  min-height:100vh;
}
.dl-light{
  --bg:#F4F6F8; --panel:#FFFFFF; --panel2:#F7F9FB;
  --line:#DFE5EB; --linesoft:#EDF1F5;
  --tx:#16202B; --tx2:#556475; --tx3:#6E7C8A;
}
.dl-dark{
  --bg:#0E1116; --panel:#161A21; --panel2:#1B212A;
  --line:#272F3A; --linesoft:#1F252E;
  --tx:#E6EBF1; --tx2:#9FADBB; --tx3:#7E8B99;
  --blue:#4E9BF0; --blue-bg:#152238;
  --up:#2FBF71; --up-bg:#0F2C1D;
  --dn:#F2564C; --dn-bg:#33150F;
  --wn:#E0A93C; --wn-bg:#2E2312;
}
.dl-root *{box-sizing:border-box}
/* index.css sets a global h1-h5 colour that resolves against the APP's theme,
   not this one, so section headings rendered near-black on the dark stage.
   Documented gotcha; neutralised here rather than by touching global CSS. */
.dl-root h1,.dl-root h2,.dl-root h3,.dl-root h4,.dl-root h5{color:inherit;margin:0}
.dl-stage{background:var(--bg);color:var(--tx);min-height:calc(100vh - 44px)}
.dl-mono{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}
.dl-up{color:var(--up)} .dl-dn{color:var(--dn)}
.dl-spacer{flex:1}

/* toolbar (lab chrome, not part of any design) */
.dl-bar{display:flex;align-items:center;gap:14px;height:44px;padding:0 14px;
  background:#0B0E12;color:#C6D0DA;font-size:12.5px;position:sticky;top:0;z-index:20}
.dl-barlabel{font-weight:600;letter-spacing:.08em;text-transform:uppercase;font-size:10px;color:#6E7C8A}
.dl-barref{color:#6E7C8A;font-size:12px}
.dl-seg{display:flex;background:#171C23;border-radius:6px;padding:2px}
.dl-seg button{border:0;background:transparent;color:#9FADBB;font:500 12.5px/1 Inter,sans-serif;
  padding:7px 12px;border-radius:4px;cursor:pointer}
.dl-seg button.sel{background:#2A3340;color:#fff}
.dl-toggle{border:1px solid #2A3340;background:transparent;color:#C6D0DA;border-radius:6px;
  padding:6px 12px;font:500 12.5px/1 Inter,sans-serif;cursor:pointer}

/* shared atoms */
.dl-lbl{font:500 10.5px/1.4 Inter,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--tx3)}
.dl-pnl{font:600 38px/1.1 Inter,sans-serif;letter-spacing:-.025em;color:var(--dn);
  margin-top:6px;font-variant-numeric:tabular-nums}
.dl-pnlsub{font-size:12.5px;color:var(--tx3);margin-top:6px}
.dl-pnlsub b{font-weight:500}
.dl-mets{display:flex;gap:8px;flex-wrap:wrap}
.dl-met{background:var(--panel2);border:1px solid var(--linesoft);border-radius:var(--r);
  padding:8px 12px;min-width:112px}
.dl-mets-bare .dl-met{background:transparent;border:0;border-left:1px solid var(--line);
  border-radius:0;padding:2px 0 2px 14px;margin-left:6px}
.dl-metv{font:500 19px/1.3 Inter,sans-serif;margin-top:3px;font-variant-numeric:tabular-nums}
.dl-metu{font-size:11.5px;color:var(--tx3);margin-left:6px;font-weight:400}
.dl-mark{width:14px;height:14px;border-radius:3px;background:var(--blue);display:inline-block}
.dl-status{display:inline-flex;align-items:center;gap:6px;font:500 11px/1 Inter,sans-serif;
  letter-spacing:.06em;color:var(--tx3)}
.dl-status i{width:6px;height:6px;border-radius:50%;background:var(--tx3)}
.dl-chip{font:500 11.5px/1 Inter,sans-serif;color:var(--tx2);background:var(--panel2);
  border:1px solid var(--line);border-radius:4px;padding:5px 9px}
.dl-lnk{color:var(--blue);font:500 12px/1 Inter,sans-serif;cursor:pointer}
.dl-ct{font:500 10.5px/1 Inter,sans-serif;background:var(--dn-bg);color:var(--dn);
  border-radius:3px;padding:3px 6px}
.dl-ct-q{background:var(--panel2);color:var(--tx2)}

/* alerts */
.dl-arow{display:grid;grid-template-columns:1fr 46px;gap:12px;padding:11px 14px 11px 12px;
  border-bottom:1px solid var(--linesoft);border-left:2px solid transparent}
.dl-arow:last-child{border-bottom:0}
.dl-arow.dl-danger{border-left-color:var(--dn)}
.dl-arow.dl-caution{border-left-color:var(--wn)}
.dl-ahead{display:flex;align-items:center;gap:8px}
.dl-at{font:500 13.5px/1.4 Inter,sans-serif}
.dl-bd{font:500 9.5px/1 Inter,sans-serif;letter-spacing:.07em;padding:3px 5px;border-radius:3px}
.dl-bd-danger{background:var(--dn-bg);color:var(--dn)}
.dl-bd-caution{background:var(--wn-bg);color:var(--wn)}
.dl-ab{font-size:12.5px;line-height:1.55;color:var(--tx2);margin:4px 0 0}
.dl-when{font:400 11px/1 Inter,sans-serif;color:var(--tx3);text-align:right;padding-top:3px}

/* table */
.dl-tbl{width:100%;border-collapse:collapse}
.dl-tbl th{font:500 10px/1 Inter,sans-serif;letter-spacing:.07em;text-transform:uppercase;
  color:var(--tx3);text-align:right;padding:8px 12px;background:var(--panel2);
  border-bottom:1px solid var(--line)}
.dl-tbl th:first-child{text-align:left}
.dl-tbl td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--linesoft);
  font:500 13px/1.4 Inter,sans-serif;font-variant-numeric:tabular-nums}
.dl-tbl td:first-child{text-align:left}
.dl-tbl tbody tr:last-child td{border-bottom:0}
.dl-sym{font-weight:500}
.dl-prod{font:500 9.5px/1 Inter,sans-serif;letter-spacing:.06em;color:var(--tx3);
  background:var(--panel2);border-radius:3px;padding:3px 5px;margin-left:7px}

/* ══ A · Terminal ══ flat panels, everything contained, very tight ══ */
.dl-terminal .dl-app{display:flex;min-height:calc(100vh - 44px)}
.dl-terminal .dl-side{width:186px;flex-shrink:0;background:var(--panel);
  border-right:1px solid var(--line);padding:10px 8px}
.dl-terminal .dl-brand{display:flex;align-items:center;gap:8px;font:600 14px/1 Inter,sans-serif;
  padding:6px 8px 14px}
.dl-terminal .dl-nav{font:400 13px/1 Inter,sans-serif;color:var(--tx2);padding:8px 8px;
  border-radius:4px;cursor:pointer}
.dl-terminal .dl-nav.on{background:var(--blue-bg);color:var(--blue);font-weight:500}
.dl-terminal .dl-main{flex:1;min-width:0;padding:10px 12px 24px;display:flex;
  flex-direction:column;gap:10px}
.dl-terminal .dl-topbar{display:flex;align-items:center;gap:12px;padding:0 2px 2px}
.dl-terminal .dl-crumb{font:500 13px/1 Inter,sans-serif}
.dl-terminal .dl-grid2{display:grid;grid-template-columns:1fr 1.35fr;gap:10px}
.dl-terminal .dl-panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--r)}
.dl-terminal .dl-ph{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-bottom:1px solid var(--line);font:500 12px/1.4 Inter,sans-serif;color:var(--tx2);
  background:var(--panel2);border-radius:var(--r) var(--r) 0 0}
.dl-terminal .dl-pb{padding:12px}
.dl-terminal .dl-pb-flush{padding:0}
.dl-terminal .dl-pnl{font-size:32px}

/* ══ B · Market ══ dark chrome + mixed containment ══ */
.dl-market .dl-tape{display:flex;gap:22px;align-items:center;height:30px;padding:0 16px;
  background:#0B0E12;color:#C6D0DA;font:400 11.5px/1 Inter,sans-serif;overflow:hidden}
.dl-market .dl-tape-i b{font-weight:500;margin-left:5px;font-variant-numeric:tabular-nums}
.dl-market .dl-tape-i em{font-style:normal;margin-left:5px}
.dl-market .dl-tape .dl-up{color:#2FBF71} .dl-market .dl-tape .dl-dn{color:#F2564C}
.dl-market .dl-topnav{display:flex;align-items:center;gap:20px;height:50px;padding:0 16px;
  background:#12161C;color:#C6D0DA}
.dl-market .dl-brand2{display:flex;align-items:center;gap:8px;font:600 15px/1 Inter,sans-serif;
  color:#fff;margin-right:8px}
.dl-market .dl-tn{font:400 13px/1 Inter,sans-serif;color:#9FADBB;cursor:pointer;
  padding:16px 0;border-bottom:2px solid transparent}
.dl-market .dl-tn.on{color:#fff;font-weight:500;border-bottom-color:var(--blue)}
.dl-market .dl-acct{font:500 11.5px/1 Inter,sans-serif;color:#C6D0DA;border:1px solid #2A3340;
  border-radius:999px;padding:6px 12px}
.dl-market .dl-body{display:grid;grid-template-columns:300px 1fr;gap:18px;
  padding:18px 16px 32px;max-width:1400px;margin:0 auto}
.dl-market .dl-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  margin-bottom:14px;overflow:hidden}
.dl-market .dl-cardh{font:500 13px/1.4 Inter,sans-serif;padding:11px 14px;
  border-bottom:1px solid var(--linesoft)}
.dl-market .dl-scorerow{display:grid;grid-template-columns:64px auto;gap:8px 10px;
  padding:10px 14px;border-bottom:1px solid var(--linesoft)}
.dl-market .dl-scorerow:last-child{border-bottom:0}
.dl-market .dl-sk{font:400 12px/1.5 Inter,sans-serif;color:var(--tx3)}
.dl-market .dl-pill{font:500 10.5px/1 Inter,sans-serif;padding:4px 8px;border-radius:999px;
  justify-self:start}
.dl-market .dl-pill-ok{background:var(--up-bg);color:var(--up)}
.dl-market .dl-pill-bad{background:var(--dn-bg);color:var(--dn)}
.dl-market .dl-sd{grid-column:1/3;font-size:12px;color:var(--tx2);line-height:1.5}
.dl-market .dl-budget{padding:14px}
.dl-market .dl-track{height:6px;background:var(--panel2);border-radius:3px;overflow:hidden}
.dl-market .dl-track i{display:block;height:100%;background:var(--wn)}
.dl-market .dl-bmeta{font-size:12px;color:var(--tx3);margin-top:8px}
.dl-market .dl-bmeta b{color:var(--tx);font-weight:500}
.dl-market .dl-hero{display:flex;align-items:flex-start;justify-content:space-between;
  gap:28px;padding:2px 2px 20px;border-bottom:1px solid var(--line)}
.dl-market .dl-sech{display:flex;align-items:center;gap:9px;padding:20px 2px 10px}
.dl-market .dl-sech h3{font:500 14px/1.4 Inter,sans-serif;margin:0}
.dl-market .dl-arow{padding-left:10px}
.dl-market .dl-tbl th{background:transparent;border-bottom:1px solid var(--line)}

/* ══ C · Focused ══ one hero, alerts bare, only reference data panelled ══ */
.dl-focused .dl-app{display:flex;min-height:calc(100vh - 44px)}
.dl-focused .dl-side-f{width:210px;flex-shrink:0;border-right:1px solid var(--line);padding:14px 10px}
.dl-focused .dl-brand{display:flex;align-items:center;gap:9px;font:600 15px/1 Inter,sans-serif;
  padding:6px 8px 18px}
.dl-focused .dl-nav{font:400 13.5px/1 Inter,sans-serif;color:var(--tx2);padding:9px 10px;
  border-radius:4px;cursor:pointer;margin-bottom:1px}
.dl-focused .dl-nav.on{background:var(--blue-bg);color:var(--blue);font-weight:500}
.dl-focused .dl-main-f{flex:1;min-width:0;padding:26px 30px 40px;max-width:1180px}
.dl-focused .dl-fhero{display:flex;align-items:flex-end;justify-content:space-between;
  gap:32px;padding-bottom:24px;border-bottom:1px solid var(--line)}
.dl-focused .dl-pnl{font-size:46px}
.dl-focused .dl-fstatus{text-align:right}
.dl-focused .dl-fstatus .dl-mets{margin-top:14px;justify-content:flex-end}
.dl-focused .dl-sech{display:flex;align-items:center;gap:9px;padding:26px 0 8px}
.dl-focused .dl-sech h3{font:500 15px/1.4 Inter,sans-serif;margin:0}
.dl-focused .dl-arow{padding:13px 8px 13px 12px}
.dl-focused .dl-panel-f{background:var(--panel);border:1px solid var(--line);
  border-radius:8px;margin-top:26px;overflow:hidden}
.dl-focused .dl-ph{display:flex;align-items:center;gap:8px;padding:10px 14px;
  border-bottom:1px solid var(--line);font:500 12.5px/1.4 Inter,sans-serif;color:var(--tx2)}
.dl-focused .dl-pb-flush{padding:0}
`;
