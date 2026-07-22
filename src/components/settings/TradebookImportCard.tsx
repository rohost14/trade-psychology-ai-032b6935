/**
 * Zerodha Console tradebook import.
 *
 * Kite Connect only returns the CURRENT day's trades, so without this a new
 * subscriber's Analytics, Edge/Leak, My Patterns and quality scores are all
 * empty until they have traded with us for weeks. Uploading the Console CSV
 * backfills their real history in one step.
 */
import { useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

interface ImportResult {
  imported: number;
  duplicates: number;
  rejected: number;
  errors?: { line: number; problems: string[] }[];
  date_range?: { from: string; to: string };
  pipeline_error?: string | null;
  message?: string;
}

function fmtDate(iso: string | undefined) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata',
  });
}

export function TradebookImportCard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  const upload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      toast.error('Please upload the CSV version', {
        description: 'In Console, use the dropdown beside Download and pick CSV.',
      });
      return;
    }
    setIsUploading(true);
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post<ImportResult>('/api/account/import-tradebook', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      if (res.data.imported > 0) {
        toast.success(`Imported ${res.data.imported} trades`, {
          description: 'Analytics, Edge and My Patterns will now reflect this history.',
        });
      } else if (res.data.duplicates > 0) {
        toast.info('Already up to date', {
          description: `All ${res.data.duplicates} trades in this file were already imported.`,
        });
      } else {
        toast.warning('Nothing imported', { description: res.data.message });
      }
    } catch (error) {
      const err = error as { response?: { status?: number; data?: { detail?: unknown } } };
      const detail = err.response?.data?.detail;
      toast.error(
        err.response?.status === 429
          ? 'Too many imports — try again in an hour'
          : typeof detail === 'string' ? detail : 'Import failed. Please try again.',
      );
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Upload className="h-4 w-4" />
          Import your trading history
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Bring in past trades from your Zerodha Console tradebook
        </p>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-[13px] text-muted-foreground leading-relaxed">
          Zerodha's live API only shares <span className="text-foreground font-medium">today's</span> trades,
          so we can't see anything you traded before connecting. Upload your Console tradebook once and your
          full history powers Analytics, Edge &amp; Leak, and My Patterns straight away.
        </p>

        <ol className="text-[13px] text-muted-foreground space-y-1.5 list-decimal pl-5">
          <li>
            Open{' '}
            <a
              href="https://console.zerodha.com/reports/tradebook"
              target="_blank"
              rel="noopener noreferrer"
              className="text-tm-brand hover:underline inline-flex items-center gap-1"
            >
              Console → Reports → Tradebook
              <ExternalLink className="h-3 w-3" />
            </a>
          </li>
          <li>Pick your segment and date range (the widest range you have)</li>
          <li>Download as <span className="text-foreground font-medium">CSV</span>, then drop it below</li>
        </ol>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) upload(f);
          }}
          className={cn(
            'rounded-xl border-2 border-dashed px-5 py-8 text-center transition-colors',
            dragOver ? 'border-tm-brand bg-tm-brand/5' : 'border-border',
            isUploading && 'opacity-60 pointer-events-none',
          )}
        >
          {isUploading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-tm-brand" />
              <p className="text-[13px] text-muted-foreground">Reading your tradebook…</p>
            </div>
          ) : (
            <>
              <Upload className="h-6 w-6 text-muted-foreground/50 mx-auto mb-2" />
              <p className="text-[13px] text-foreground mb-2">Drop your tradebook CSV here</p>
              <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
                Choose file
              </Button>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) upload(f);
            }}
          />
        </div>

        {/* Result */}
        {result && (
          <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 space-y-2">
            <div className="flex items-start gap-2">
              {result.imported > 0
                ? <CheckCircle2 className="h-4 w-4 text-tm-profit mt-0.5 shrink-0" />
                : <AlertTriangle className="h-4 w-4 text-tm-obs mt-0.5 shrink-0" />}
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">{result.message}</p>
                {result.date_range && result.imported > 0 && (
                  <p className="text-[12px] text-muted-foreground mt-0.5">
                    {fmtDate(result.date_range.from)} → {fmtDate(result.date_range.to)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] pl-6">
              <span className="text-tm-profit">{result.imported} imported</span>
              {result.duplicates > 0 && (
                <span className="text-muted-foreground">{result.duplicates} already present</span>
              )}
              {result.rejected > 0 && (
                <span className="text-tm-loss">{result.rejected} unreadable</span>
              )}
            </div>

            {result.pipeline_error && (
              <p className="text-[12px] text-tm-obs pl-6">
                Trades saved, but rebuilding analytics hit an error. They'll be picked up on your next sync.
              </p>
            )}

            {result.errors && result.errors.length > 0 && (
              <details className="pl-6">
                <summary className="text-[12px] text-muted-foreground cursor-pointer hover:text-foreground">
                  Show rejected rows
                </summary>
                <div className="mt-1.5 max-h-40 overflow-y-auto space-y-1">
                  {result.errors.map((e, i) => (
                    <p key={i} className="text-[11px] text-muted-foreground font-mono">
                      line {e.line}: {e.problems.join(', ')}
                    </p>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        <p className="text-[11px] text-muted-foreground">
          Safe to re-upload — trades already imported are skipped, never duplicated.
          Imported history feeds your analytics; it does not generate back-dated alerts.
        </p>
      </div>
    </div>
  );
}
