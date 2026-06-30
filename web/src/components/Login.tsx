import { useState } from 'react'
import estrella from '../assets/ulima-estrella.svg'
import { login, type Perfil } from '../lib'

export default function Login({ onAuthed }: { onAuthed: (p: Perfil) => void }) {
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setErr('')
    setBusy(true)
    try {
      const r = await login(u.trim(), p)
      if (r.ok && r.perfil) onAuthed(r.perfil)
      else setErr(r.error || 'No se pudo iniciar sesión.')
    } catch {
      setErr('No se pudo conectar con el servidor.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <div className="login-card">
        <img className="logo-big" src={estrella} alt="Universidad de Lima" />
        <h1>ULima360 · Analytics</h1>
        <p className="muted">Inicia sesión para hablar con tu data</p>
        <form onSubmit={submit}>
          <input placeholder="Usuario" value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" />
          <input placeholder="Contraseña" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
          {err && <div className="login-err">{err}</div>}
          <button type="submit" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
        </form>
        <div className="muted small">Acceso segmentado por rol · auditado (Ley 29733)</div>
      </div>
    </div>
  )
}
