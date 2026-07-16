'use client';
import { useState } from 'react';

export default function AuthPage() {
  const [tab, setTab] = useState<'signin' | 'signup'>('signin');
  const [showPass, setShowPass] = useState(false);

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", background: '#FAFAFC', minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');
        .ms { font-family: 'Material Symbols Outlined'; font-weight: normal; font-style: normal; font-size: inherit; line-height: 1; letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; word-wrap: normal; direction: ltr; -webkit-font-smoothing: antialiased; }
        .glass-floating { background: rgba(255,255,255,0.9); backdrop-filter: blur(32px); -webkit-backdrop-filter: blur(32px); box-shadow: 0 10px 20px rgba(23,26,43,0.04); border: 1px solid rgba(236,234,245,0.5); }
        .glass-panel { background: rgba(255,255,255,0.7); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid #ECEAF5; }
        .fluid-shape { animation: morph 8s ease-in-out infinite; background: rgba(255,255,255,0.6); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); box-shadow: 0 20px 60px rgba(23,26,43,0.08); border: 1px solid rgba(255,255,255,0.5); }
        @keyframes morph { 0% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; } 50% { border-radius: 30% 70% 70% 30% / 30% 60% 40% 70%; } 100% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; } }
        .signup-field { overflow: hidden; transition: max-height 0.35s ease, opacity 0.3s ease, margin 0.3s ease; }
        .signup-field.visible { max-height: 120px; opacity: 1; }
        .signup-field.hidden { max-height: 0; opacity: 0; margin-top: 0 !important; margin-bottom: 0 !important; pointer-events: none; }
        .orb1 { background: radial-gradient(circle, rgba(167,139,250,0.4) 0%, rgba(167,139,250,0) 70%); }
        .orb2 { background: radial-gradient(circle, rgba(236,72,153,0.3) 0%, rgba(236,72,153,0) 70%); }
        .input-glow:focus { box-shadow: 0 0 0 2px rgba(167,139,250,0.3); border-color: #A78BFA; outline: none; }
        @keyframes bounceA { 0%,100%{transform:rotate(3deg) translateY(0)} 50%{transform:rotate(3deg) translateY(-10px)} }
        @keyframes bounceB { 0%,100%{transform:rotate(-2deg) translateY(0)} 50%{transform:rotate(-2deg) translateY(-10px)} }
        @keyframes pulse2 { 0%,100%{opacity:1} 50%{opacity:0.5} }
        .badge-a { animation: bounceA 5s ease-in-out infinite; }
        .badge-b { animation: bounceB 6s ease-in-out infinite reverse; }
        .pulse { animation: pulse2 2s ease-in-out infinite; }
        .card-hover { transition: transform 0.5s; }
        .card-hover:hover { transform: scale(1.02); }
        .btn-main { width:100%; background:#171A2B; color:#fff; border:none; border-radius:9999px; padding:14px 0; font-size:14px; font-weight:600; letter-spacing:0.02em; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px; transition:transform 0.3s, box-shadow 0.3s; margin-top:4px; font-family:'Geist',sans-serif; }
        .btn-main:hover { transform:scale(1.02); box-shadow:0 0 15px rgba(167,139,250,0.4); }
        .arrow-icon { display:inline-block; transition:transform 0.2s; }
        .btn-main:hover .arrow-icon { transform:translateX(4px); }
        .tab-btn { flex:1; padding:14px 0; background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; font-size:14px; font-family:'Geist',sans-serif; letter-spacing:0.02em; transition:all 0.2s; }
        .tab-active { border-bottom-color:#A78BFA; color:#171A2B; font-weight:700; }
        .tab-inactive { color:rgba(70,70,76,0.6); font-weight:500; }
        .input-wrap { position:relative; }
        .field-input { width:100%; box-sizing:border-box; padding:13px 16px 13px 44px; background:rgba(255,255,255,0.9); border:1px solid #ECEAF5; border-radius:12px; font-size:16px; color:#111; font-family:'Inter',sans-serif; transition:border-color 0.3s, box-shadow 0.3s; }
        .field-input::placeholder { color:rgba(70,70,76,0.4); }
        .field-input.has-right { padding-right:48px; }
        .field-icon-left { position:absolute; left:14px; top:50%; transform:translateY(-50%); color:rgba(70,70,76,0.5); font-size:20px; pointer-events:none; }
        .field-icon-right { position:absolute; right:14px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; color:rgba(70,70,76,0.5); font-size:20px; display:flex; align-items:center; transition:color 0.2s; }
        .field-icon-right:hover { color:#171A2B; }
        .link-style { background:none; border:none; cursor:pointer; font-weight:700; color:#171A2B; font-size:16px; font-family:'Inter',sans-serif; padding:0; transition:color 0.2s; }
        .link-style:hover { color:#A78BFA; }
        .forgot-link { font-size:12px; font-weight:600; color:#A78BFA; text-decoration:none; letter-spacing:0.05em; transition:color 0.2s; }
        .forgot-link:hover { color:#171A2B; }
        .vault-card { display:none; }
        @media(min-width:1024px) { .vault-card { display:block; } }
        @media(min-width:768px) { .badge-a-wrap { display:flex !important; } .badge-b-wrap { display:flex !important; } }
        @media(max-width:767px) { .badge-a-wrap { display:none !important; } .badge-b-wrap { display:none !important; } }
        .footer-link { font-size:12px; font-weight:600; color:rgba(70,70,76,0.6); text-decoration:none; letter-spacing:0.05em; transition:color 0.2s; }
        .footer-link:hover { color:#6b38d4; }
        .green-dot { width:8px; height:8px; border-radius:50%; background:#22c55e; }
      `}</style>

      {/* Top Left Badge */}
      <div className="glass-floating" style={{ position: 'absolute', top: 24, left: 24, zIndex: 50, padding: '8px 16px', borderRadius: 9999, display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="green-dot pulse" />
        <span style={{ fontFamily: "'Geist',sans-serif", fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', color: '#171A2B' }}>Neural Network: Active</span>
      </div>

      {/* Top Right Badge */}
      <div className="glass-floating" style={{ position: 'absolute', top: 24, right: 24, zIndex: 50, padding: '8px 16px', borderRadius: 9999, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="ms" style={{ color: '#A78BFA', fontSize: 18 }}>bolt</span>
        <span style={{ fontFamily: "'Geist',sans-serif", fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', color: '#171A2B' }}>Token Efficiency: 94%</span>
      </div>

      <main style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', zIndex: 10, padding: '48px 24px' }}>

        {/* Background */}
        <div style={{ position: 'absolute', inset: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' }}>
          <div className="orb1" style={{ position: 'absolute', top: '25%', left: -128, width: 384, height: 384, borderRadius: '50%', filter: 'blur(64px)', opacity: 0.5 }} />
          <div className="orb2" style={{ position: 'absolute', bottom: '25%', right: -128, width: 500, height: 500, borderRadius: '50%', filter: 'blur(64px)', opacity: 0.5 }} />
          <div style={{ position: 'absolute', top: 0, right: 0, width: '120vw', height: '120vh', background: 'rgba(255,255,255,0.4)', backdropFilter: 'blur(48px)', transform: 'rotate(12deg) translate(33%,-25%)', borderRadius: 100, border: '1px solid rgba(255,255,255,0.2)', boxShadow: '0 25px 50px rgba(0,0,0,0.08)' }} />
        </div>

        {/* Vault Preview (bg floating card) */}
        <div className="vault-card" style={{ position: 'absolute', top: '33%', right: '25%', zIndex: 10, opacity: 0.6, transform: 'translate(50%,-50%) rotate(6deg) scale(0.9)' }}>
          <div className="glass-floating" style={{ padding: 24, borderRadius: 16, width: 320, position: 'relative', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.6)', boxShadow: '0 25px 50px rgba(0,0,0,0.1)' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 4, background: 'linear-gradient(90deg,#60a5fa,#A78BFA)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <span style={{ padding: '4px 8px', background: '#eff6ff', color: '#2563eb', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>Vault</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#22c55e' }}>
                <span className="ms" style={{ fontSize: 16 }}>verified</span>
                <span style={{ fontSize: 12, fontWeight: 700 }}>99</span>
              </div>
            </div>
            <h3 style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 700, marginBottom: 8 }}>React Component Scaffold Generator</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
              <span style={{ padding: '4px 10px', background: '#f3f4f6', color: '#4b5563', borderRadius: 9999, fontSize: 11 }}>React</span>
              <span style={{ padding: '4px 10px', background: '#f3f4f6', color: '#4b5563', borderRadius: 9999, fontSize: 11 }}>TypeScript</span>
            </div>
            <div style={{ background: '#f9fafb', padding: 12, borderRadius: 8, border: '1px solid #f3f4f6', fontFamily: 'monospace', fontSize: 11, color: '#6b7280', height: 96, overflow: 'hidden', position: 'relative' }}>
              <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', height: 48, background: 'linear-gradient(to top,#f9fafb,transparent)' }} />
              You are an expert frontend engineer. Create a reusable React component for...
            </div>
          </div>
        </div>

        {/* Main Container */}
        <div style={{ position: 'relative', zIndex: 20, width: '100%', maxWidth: 1200, display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 48, flexWrap: 'wrap' }}>

          {/* LEFT */}
          <div style={{ flex: '1 1 400px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
            <div style={{ marginBottom: 24, textAlign: 'left' }}>
              <h1 style={{ fontFamily: "'Geist',sans-serif", fontSize: 'clamp(32px,4vw,48px)', lineHeight: 1.15, fontWeight: 700, letterSpacing: '-0.04em', color: '#111', marginBottom: 8 }}>
                Architect your <br />
                <span style={{ background: 'linear-gradient(90deg,#171A2B,#A78BFA)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>intelligence.</span>
              </h1>
            </div>

            <div style={{ position: 'relative', width: '100%', maxWidth: 448 }}>

              {/* PromptScore Badge */}
              <div className="badge-a-wrap glass-floating badge-a" style={{ position: 'absolute', top: -32, right: -64, zIndex: 40, padding: '14px 16px', borderRadius: 12, alignItems: 'center', gap: 14, border: '1px solid rgba(255,255,255,0.5)', backdropFilter: 'blur(48px)' }}>
                <div style={{ position: 'relative', width: 48, height: 48 }}>
                  <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#A78BFA" strokeWidth="3" strokeDasharray="98,100" />
                  </svg>
                  <span style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', fontFamily: "'Geist',sans-serif", fontWeight: 700, fontSize: 13, color: '#171A2B' }}>98</span>
                </div>
                <div>
                  <p style={{ fontFamily: "'Geist',sans-serif", fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', color: 'rgba(70,70,76,0.7)', textTransform: 'uppercase', marginBottom: 4 }}>PromptScore</p>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <span style={{ fontSize: 9, background: 'rgba(255,255,255,0.6)', padding: '2px 8px', borderRadius: 9999, color: '#4b5563', border: '1px solid #f3f4f6' }}>Clarity</span>
                    <span style={{ fontSize: 9, background: 'rgba(255,255,255,0.6)', padding: '2px 8px', borderRadius: 9999, color: '#4b5563', border: '1px solid #f3f4f6' }}>Context</span>
                  </div>
                </div>
              </div>

              {/* Main Dashboard Card */}
              <div className="glass-floating card-hover" style={{ borderRadius: 20, border: '1px solid rgba(255,255,255,0.6)', boxShadow: '0 25px 50px rgba(0,0,0,0.08)', padding: 24, position: 'relative', overflow: 'hidden', zIndex: 30, backdropFilter: 'blur(48px)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, paddingBottom: 16, borderBottom: '1px solid #f3f4f6' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f87171' }} />
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fbbf24' }} />
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#4ade80' }} />
                  </div>
                  <span style={{ fontFamily: "'Geist',sans-serif", fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Prompt Optimizer v2.4</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div style={{ background: 'rgba(249,250,251,0.5)', padding: 16, borderRadius: 12, border: '1px solid rgba(243,244,246,0.5)', position: 'relative' }}>
                    <span style={{ position: 'absolute', top: -10, left: 14, background: '#fff', padding: '0 8px', fontSize: 10, fontWeight: 700, color: '#9ca3af', borderRadius: 9999, border: '1px solid #f3f4f6' }}>Input Node</span>
                    <p style={{ fontFamily: 'monospace', fontSize: 13, color: '#6b7280', marginTop: 4 }}>&ldquo;Write a react component for a login page...&rdquo;</p>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center', margin: '-8px 0' }}>
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#A78BFA,#EC4899)', padding: 1, zIndex: 10 }}>
                      <div style={{ width: '100%', height: '100%', background: '#fff', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <span className="ms pulse" style={{ color: '#A78BFA', fontSize: 16 }}>magic_button</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ background: 'linear-gradient(135deg,rgba(167,139,250,0.1),rgba(236,72,153,0.05))', padding: 16, borderRadius: 12, border: '1px solid rgba(167,139,250,0.3)', position: 'relative' }}>
                    <span style={{ position: 'absolute', top: -10, left: 14, background: '#fff', padding: '0 8px', fontSize: 10, fontWeight: 700, color: '#A78BFA', borderRadius: 9999, border: '1px solid rgba(167,139,250,0.3)', boxShadow: '0 1px 4px rgba(167,139,250,0.2)' }}>Optimized Output</span>
                    <p style={{ fontFamily: 'monospace', fontSize: 13, color: '#171A2B', lineHeight: 1.6, marginTop: 4 }}>
                      <span style={{ color: '#A78BFA' }}>You are an expert Frontend Engineer.</span><br />
                      Create a highly accessible, responsive React login component using Tailwind CSS...
                    </p>
                  </div>
                </div>
              </div>

              {/* Model Badge */}
              <div className="badge-b-wrap glass-floating badge-b" style={{ position: 'absolute', bottom: -24, left: -48, zIndex: 40, padding: '10px 14px', borderRadius: 12, alignItems: 'center', gap: 10, border: '1px solid rgba(255,255,255,0.5)', backdropFilter: 'blur(48px)' }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#A78BFA,#EC4899)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="ms" style={{ color: '#fff', fontSize: 16 }}>auto_awesome</span>
                </div>
                <div>
                  <p style={{ fontFamily: "'Geist',sans-serif", fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', color: 'rgba(70,70,76,0.7)', textTransform: 'uppercase' }}>Target Model</p>
                  <p style={{ fontFamily: "'Geist',sans-serif", fontSize: 12, fontWeight: 700, color: '#171A2B' }}>Claude 3.5 Sonnet</p>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: Auth Card */}
          <div style={{ flex: '1 1 380px', position: 'relative', zIndex: 30, maxWidth: 480 }}>
            {/* Fluid morphing blob BEHIND the card — fixed 110% size so it visibly overflows */}
            <div className="fluid-shape" style={{
              position: 'absolute',
              top: '50%', left: '50%',
              width: '110%', height: '110%',
              transform: 'translate(-50%,-50%)',
              zIndex: 0,
              opacity: 0.85
            }} />

            {/* Card */}
            <div className="glass-floating" style={{ position: 'relative', borderRadius: 40, padding: '48px 40px', overflow: 'hidden', zIndex: 1, backdropFilter: 'blur(48px)' }}>
              {/* Top gradient bar */}
              <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 8, background: 'linear-gradient(90deg,#A78BFA,#EC4899,#A78BFA)', opacity: 0.5 }} />

              <div style={{ textAlign: 'center', marginBottom: 28 }}>
                <h2 style={{ fontFamily: "'Geist',sans-serif", fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em', color: '#111', marginBottom: 6 }}>Welcome back</h2>
                <p style={{ fontSize: 16, color: 'rgba(70,70,76,0.6)' }}>Sign in to continue to PromptIQ</p>
              </div>

              {/* Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid #f3f4f6', marginBottom: 28 }}>
                <button className={`tab-btn ${tab === 'signin' ? 'tab-active' : 'tab-inactive'}`} onClick={() => setTab('signin')}>Sign In</button>
                <button className={`tab-btn ${tab === 'signup' ? 'tab-active' : 'tab-inactive'}`} onClick={() => setTab('signup')}>Create Account</button>
              </div>

              {/* Form — all fields always rendered, extras hidden via CSS so card never resizes */}
              <form onSubmit={e => e.preventDefault()}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

                  {/* Full Name — signup only */}
                  <div className={`signup-field ${tab === 'signup' ? 'visible' : 'hidden'}`}>
                    <label style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 500, letterSpacing: '0.02em', color: '#111', display: 'block', marginBottom: 6, marginLeft: 4 }}>Full Name</label>
                    <div className="input-wrap">
                      <span className="ms field-icon-left">person</span>
                      <input className="field-input input-glow" type="text" placeholder="John Doe" tabIndex={tab === 'signup' ? 0 : -1} />
                    </div>
                  </div>

                  {/* Email */}
                  <div>
                    <label style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 500, letterSpacing: '0.02em', color: '#111', display: 'block', marginBottom: 6, marginLeft: 4 }}>Email address</label>
                    <div className="input-wrap">
                      <span className="ms field-icon-left">mail</span>
                      <input className="field-input input-glow" type="email" placeholder="name@company.com" />
                    </div>
                  </div>

                  {/* Password */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, marginLeft: 4 }}>
                      <label style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 500, letterSpacing: '0.02em', color: '#111' }}>Password</label>
                      <a href="#" className="forgot-link" style={{ visibility: tab === 'signin' ? 'visible' : 'hidden' }}>Forgot?</a>
                    </div>
                    <div className="input-wrap">
                      <span className="ms field-icon-left">lock</span>
                      <input className="field-input input-glow has-right" type={showPass ? 'text' : 'password'} placeholder="••••••••" />
                      <button type="button" className="field-icon-right ms" onClick={() => setShowPass(p => !p)}>
                        {showPass ? 'visibility_off' : 'visibility'}
                      </button>
                    </div>
                  </div>

                  {/* Confirm Password — signup only */}
                  <div className={`signup-field ${tab === 'signup' ? 'visible' : 'hidden'}`}>
                    <label style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 500, letterSpacing: '0.02em', color: '#111', display: 'block', marginBottom: 6, marginLeft: 4 }}>Confirm Password</label>
                    <div className="input-wrap">
                      <span className="ms field-icon-left">lock</span>
                      <input className="field-input input-glow has-right" type="password" placeholder="••••••••" tabIndex={tab === 'signup' ? 0 : -1} />
                    </div>
                  </div>

                  <button type="button" className="btn-main" style={{ marginTop: 6 }}>
                    {tab === 'signin' ? 'Sign In' : 'Create Account'}
                    <span className="ms arrow-icon" style={{ fontSize: 18 }}>arrow_forward</span>
                  </button>

                  <div style={{ marginTop: 8, paddingTop: 20, borderTop: '1px solid rgba(229,225,227,0.5)', textAlign: 'center' }}>
                    <p style={{ fontSize: 16, color: 'rgba(70,70,76,0.8)' }}>
                      {tab === 'signin' ? (
                        <>Don&apos;t have an account? <button type="button" className="link-style" onClick={() => setTab('signup')}>Get Started</button></>
                      ) : (
                        <>Already have an account? <button type="button" className="link-style" onClick={() => setTab('signin')}>Sign In</button></>
                      )}
                    </p>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer style={{ position: 'relative', zIndex: 20, width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 40px', flexWrap: 'wrap', gap: 16, maxWidth: 1440, margin: '0 auto' }}>
        <span style={{ fontFamily: "'Geist',sans-serif", fontSize: 14, fontWeight: 900, color: '#1c1b1d', opacity: 0.8 }}>© 2024 PromptIQ Intelligence Systems</span>
        <nav style={{ display: 'flex', gap: 24 }}>
          {['Privacy', 'Terms', 'Security', 'Docs'].map(l => (
            <a key={l} href="#" className="footer-link">{l}</a>
          ))}
        </nav>
      </footer>
    </div>
  );
}
