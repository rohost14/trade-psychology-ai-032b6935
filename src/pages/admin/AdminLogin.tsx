import { useState } from 'react';
import { Shield, Mail, Lock, KeyRound, Eye, EyeOff } from 'lucide-react';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

export default function AdminLogin() {
  const { step, login, verifyOtp } = useAdminAuth();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [otp,      setOtp]      = useState('');
  const [showPwd,  setShowPwd]  = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await login(email, password); }
    catch (err: any) { setError(err.message || 'Invalid credentials'); }
    finally { setLoading(false); }
  };

  const handleOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await verifyOtp(email, otp); }
    catch (err: any) { setError(err.message || 'Invalid code'); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#04040e' }}>
      <div style={{ width: '100%', maxWidth: 400, padding: '0 1.5rem' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem' }}>
            <Shield style={{ width: 24, height: 24, color: '#f59e0b' }} />
          </div>
          <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 700, fontSize: '1.4rem', color: '#fff', marginBottom: 4 }}>TradeMentor Admin</h1>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: '0.82rem', color: 'rgba(226,232,240,0.4)' }}>
            {step === 'otp_sent' ? `Code sent to ${email}` : 'Restricted access'}
          </p>
        </div>

        {/* Card */}
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: '2rem' }}>
          {step === 'idle' ? (
            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontFamily: "'DM Sans', sans-serif", fontSize: '0.78rem', color: 'rgba(226,232,240,0.5)', marginBottom: 6 }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 15, height: 15, color: 'rgba(226,232,240,0.3)' }} />
                  <input
                    type="email" value={email} onChange={e => setEmail(e.target.value)} required
                    placeholder="admin@tradementor.ai"
                    style={{ width: '100%', padding: '0.7rem 0.75rem 0.7rem 2.4rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', fontFamily: "'DM Sans', sans-serif", fontSize: '0.875rem', outline: 'none', boxSizing: 'border-box' }}
                  />
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontFamily: "'DM Sans', sans-serif", fontSize: '0.78rem', color: 'rgba(226,232,240,0.5)', marginBottom: 6 }}>Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 15, height: 15, color: 'rgba(226,232,240,0.3)' }} />
                  <input
                    type={showPwd ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} required
                    placeholder="••••••••"
                    style={{ width: '100%', padding: '0.7rem 2.4rem 0.7rem 2.4rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', fontFamily: "'DM Sans', sans-serif", fontSize: '0.875rem', outline: 'none', boxSizing: 'border-box' }}
                  />
                  <button type="button" onClick={() => setShowPwd(v => !v)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                    {showPwd ? <EyeOff style={{ width: 15, height: 15, color: 'rgba(226,232,240,0.3)' }} /> : <Eye style={{ width: 15, height: 15, color: 'rgba(226,232,240,0.3)' }} />}
                  </button>
                </div>
              </div>
              {error && <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: '0.8rem', color: '#ef4444', textAlign: 'center' }}>{error}</p>}
              <button type="submit" disabled={loading} style={{ marginTop: '0.5rem', padding: '0.8rem', borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: '0.875rem', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1, background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', border: 'none', transition: 'all 0.2s' }}>
                {loading ? 'Sending code…' : 'Continue'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleOtp} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: '0.84rem', color: 'rgba(226,232,240,0.55)', textAlign: 'center', lineHeight: 1.6 }}>
                Enter the 6-digit code sent to your email.
              </p>
              <div style={{ position: 'relative' }}>
                <KeyRound style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 15, height: 15, color: 'rgba(226,232,240,0.3)' }} />
                <input
                  type="text" value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} required
                  placeholder="000000" maxLength={6}
                  style={{ width: '100%', padding: '0.7rem 0.75rem 0.7rem 2.4rem', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', fontFamily: "'JetBrains Mono', monospace", fontSize: '1.4rem', textAlign: 'center', letterSpacing: '0.3em', outline: 'none', boxSizing: 'border-box' }}
                />
              </div>
              {error && <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: '0.8rem', color: '#ef4444', textAlign: 'center' }}>{error}</p>}
              <button type="submit" disabled={loading || otp.length !== 6} style={{ padding: '0.8rem', borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: '0.875rem', cursor: (loading || otp.length !== 6) ? 'not-allowed' : 'pointer', opacity: (loading || otp.length !== 6) ? 0.5 : 1, background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000', border: 'none', transition: 'all 0.2s' }}>
                {loading ? 'Verifying…' : 'Verify & Sign In'}
              </button>
              <button type="button" onClick={() => { setOtp(''); setError(''); }} style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", fontSize: '0.78rem', color: 'rgba(226,232,240,0.35)', textDecoration: 'underline' }}>
                Back
              </button>
            </form>
          )}
        </div>

        <p style={{ textAlign: 'center', marginTop: '1.5rem', fontFamily: "'DM Sans', sans-serif", fontSize: '0.72rem', color: 'rgba(226,232,240,0.2)' }}>
          This area is restricted. Unauthorised access is prohibited.
        </p>
      </div>
    </div>
  );
}
