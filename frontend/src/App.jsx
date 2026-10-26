import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Login from './pages/Login'
import Projects from './pages/Projects'
import Editor from './pages/Editor'
import SharedView from './pages/SharedView'
import { api } from './services/api'

const PrivateRoute = () => {
  return api.isAuthenticated() ? <Outlet /> : <Navigate to="/" replace />;
};

function App() {
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

      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/share/:projectId" element={<SharedView />} />
        
        <Route element={<PrivateRoute />}>
          <Route path="/projects" element={<Projects />} />
          <Route path="/editor/:projectId" element={<Editor />} />
        </Route>
        
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App