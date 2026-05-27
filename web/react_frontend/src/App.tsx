import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import ChatPage from './pages/ChatPage'
import SkillsPage from './pages/SkillsPage'
import KnowledgePage from './pages/KnowledgePage'
import StatusPage from './pages/StatusPage'

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="status" element={<StatusPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
