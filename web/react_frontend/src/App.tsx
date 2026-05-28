import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import { AuthProvider } from './context/AuthContext'
import ChatPage from './pages/ChatPage'
import SkillsPage from './pages/SkillsPage'
import KnowledgePage from './pages/KnowledgePage'
import StatusPage from './pages/StatusPage'
import UsersPage from './pages/UsersPage'
import LoginPage from './pages/LoginPage'

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/chat" replace />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="skills" element={<SkillsPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="status" element={<StatusPage />} />
            <Route
              path="users"
              element={
                <AdminRoute>
                  <UsersPage />
                </AdminRoute>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
