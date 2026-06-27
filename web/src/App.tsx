import { useState } from 'react'
import Login from './components/Login'
import Chat from './components/Chat'
import Dashboard from './components/Dashboard'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [tab, setTab] = useState<'chat' | 'tablero'>('chat')

  if (!authed) return <Login onLogin={() => setAuthed(true)} />

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="logo">UL</div>
          <div>
            <h1>ULima360 · Analytics</h1>
            <div className="sub">capa de consumo gobernada del Data Lake</div>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Chat</button>
          <button className={tab === 'tablero' ? 'active' : ''} onClick={() => setTab('tablero')}>Tablero</button>
        </nav>
        <div className="spacer" />
        <button className="ghost" onClick={() => setAuthed(false)}>Salir</button>
      </header>
      <main className="main">{tab === 'chat' ? <Chat /> : <Dashboard />}</main>
    </div>
  )
}
