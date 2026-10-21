import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Projects from './pages/Projects'
import Editor from './pages/Editor'
import SharedView from './pages/SharedView' // NOVA PÁGINA

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/editor/:projectId" element={<Editor />} />
        <Route path="/share/:projectId" element={<SharedView />} /> {/* ROTA PÚBLICA */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App