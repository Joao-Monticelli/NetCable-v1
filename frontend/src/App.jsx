import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Login from './pages/Login'
import { api } from './services/api'
import { lazy, Suspense, useEffect } from 'react'
import { useI18n, t } from './i18n'

// Pages load on demand: the login and the public status page don't download the map editor.
const Projects = lazy(() => import('./pages/Projects'))
const Editor = lazy(() => import('./pages/Editor'))
const SharedView = lazy(() => import('./pages/SharedView'))
const StatusPage = lazy(() => import('./pages/StatusPage'))
const Carregando = () => <div style={{ minHeight: '100vh', background: '#0f172a' }} />

const PrivateRoute = () => {
  return api.isAuthenticated() ? <Outlet /> : <Navigate to="/" replace />;
};

function App() {
  const { idioma } = useI18n()
  useEffect(() => { document.title = t('NetCable - Mapeador de Rede') }, [idioma])
  return (
    <BrowserRouter>
      {/* COMPONENTE DE NOTIFICAÇÃO GLOBAL */}
      <Toaster 
        position="top-right" 
        toastOptions={{
          style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' },
          success: { iconTheme: { primary: '#10b981', secondary: '#1e293b' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#1e293b' } }
        }} 
      />

      <Suspense fallback={<Carregando />}>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/share/:token" element={<SharedView />} />
        <Route path="/status/:token" element={<StatusPage />} />
        
        <Route element={<PrivateRoute />}>
          <Route path="/projects" element={<Projects />} />
          <Route path="/editor/:projectId" element={<Editor />} />
        </Route>
        
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App