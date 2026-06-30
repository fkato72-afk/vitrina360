import { useEffect, useState } from 'react'
import estrella from './assets/ulima-estrella.svg'
import Login from './components/Login'
import CambiarClave from './components/CambiarClave'
import Chat from './components/Chat'
import Dashboard from './components/Dashboard'
import { DASHBOARDS } from './dashboards'
import { me, logout, scopeLabel, rolLabel, type Perfil } from './lib'

export default function App() {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [cargando, setCargando] = useState(true)
  const [tab, setTab] = useState<'chat' | 'tablero'>('chat')
  const [dashId, setDashId] = useState(DASHBOARDS[0].id)

  useEffect(() => {
    me().then((r) => setPerfil(r.ok && r.perfil ? r.perfil : null)).finally(() => setCargando(false))
  }, [])

  async function salir() {
    await logout().catch(() => {})
    setPerfil(null)
  }

  if (cargando) return <div className="login"><div className="login-card"><img className="logo-big" src={estrella} alt="" /><p className="muted">Cargando…</p></div></div>
  if (!perfil) return <Login onAuthed={setPerfil} />
  if (perfil.must_change) return <CambiarClave onDone={setPerfil} />

  const dash = DASHBOARDS.find((d) => d.id === dashId) || DASHBOARDS[0]

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img className="logo" src={estrella} alt="Universidad de Lima" />
          <div>
            <h1>ULima360 · Analytics</h1>
            <div className="sub">capa de consumo gobernada del Data Lake</div>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Chat</button>
          <button className={tab === 'tablero' ? 'active' : ''} onClick={() => setTab('tablero')}>Tableros</button>
        </nav>
        <div className="spacer" />
        <div className="userbox" title={`${rolLabel(perfil)} — ${scopeLabel(perfil)}`}>
          <span className="uname">{perfil.nombre}</span>
          <span className="ubadge">{rolLabel(perfil)}<span className="udot">·</span>{scopeLabel(perfil)}</span>
        </div>
        <button className="ghost" onClick={salir}>Salir</button>
      </header>
      <main className="main">
        {tab === 'chat' ? <Chat /> : (
          <div className="tablero-wrap">
            <nav className="tabs subtabs">
              {DASHBOARDS.map((d) => (
                <button key={d.id} className={d.id === dashId ? 'active' : ''} onClick={() => setDashId(d.id)}>{d.nombre}</button>
              ))}
            </nav>
            <Dashboard cfg={dash} />
          </div>
        )}
      </main>
    </div>
  )
}
