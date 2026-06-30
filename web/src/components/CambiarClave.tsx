import { useState } from 'react'
import estrella from '../assets/ulima-estrella.svg'
import { cambiarClave, type Perfil } from '../lib'

export default function CambiarClave({ onDone }: { onDone: (p: Perfil) => void }) {
  const [actual, setActual] = useState('')
  const [n1, setN1] = useState('')
  const [n2, setN2] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setErr('')
    if (n1.length < 8) return setErr('La nueva clave debe tener al menos 8 caracteres.')
    if (n1 !== n2) return setErr('Las claves nuevas no coinciden.')
    setBusy(true)
    try {
      const r = await cambiarClave(actual, n1)
      if (r.ok && r.perfil) onDone(r.perfil)
      else setErr(r.error || 'No se pudo cambiar la clave.')
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
        <h1>Cambia tu contraseña</h1>
        <p className="muted">Tu clave es temporal. Defínela antes de continuar.</p>
        <form onSubmit={submit}>
          <input placeholder="Clave temporal actual" type="password" value={actual} onChange={(e) => setActual(e.target.value)} autoFocus autoComplete="current-password" />
          <input placeholder="Nueva contraseña (mín. 8)" type="password" value={n1} onChange={(e) => setN1(e.target.value)} autoComplete="new-password" />
          <input placeholder="Repite la nueva contraseña" type="password" value={n2} onChange={(e) => setN2(e.target.value)} autoComplete="new-password" />
          {err && <div className="login-err">{err}</div>}
          <button type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar y continuar'}</button>
        </form>
      </div>
    </div>
  )
}
