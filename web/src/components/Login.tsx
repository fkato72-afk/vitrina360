import { useState } from 'react'

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  return (
    <div className="login">
      <div className="login-card">
        <div className="logo-big">UL</div>
        <h1>ULima360 · Analytics</h1>
        <p className="muted">Inicia sesión para hablar con tu data</p>
        <form onSubmit={(e) => { e.preventDefault(); onLogin() }}>
          <input placeholder="Usuario" value={u} onChange={(e) => setU(e.target.value)} autoFocus />
          <input placeholder="Contraseña" type="password" value={p} onChange={(e) => setP(e.target.value)} />
          <button type="submit">Ingresar</button>
        </form>
        <div className="muted small">Autenticación MS1/MS2 (Ley 29733) — pendiente de integrar</div>
      </div>
    </div>
  )
}
