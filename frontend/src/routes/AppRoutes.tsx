import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { ProtectedRoute, PublicRoute } from "./ProtectedRoute";

import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReviewerRegisterPage } from "../pages/ReviewerRegisterPage";
import { EditorRegisterPage } from "../pages/EditorRegisterPage";
import { DashboardPage } from "../pages/DashboardPage";
import { CompanyAIContextPage } from "../pages/CompanyAIContextPage";
import { BlogFormatPage } from "../pages/BlogFormatPage";
import { KnowledgePage } from "../pages/KnowledgePage";
import { MemoryPage } from "../pages/MemoryPage";
import { TopicsPage } from "../pages/TopicsPage";
import { BlogsPage } from "../pages/BlogsPage";
import { BlogDetailPage } from "../pages/BlogDetailPage";
import { BlogEditorPage } from "../pages/BlogEditorPage";
import { BlogRevisionsPage } from "../pages/BlogRevisionsPage";
import { ReviewsPage } from "../pages/ReviewsPage";
import { SchedulePage } from "../pages/SchedulePage";
import { WordPressPage } from "../pages/WordPressPage";
import { SettingsPage } from "../pages/SettingsPage";
import { NotFoundPage } from "../pages/NotFoundPage";

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/"
        element={
          <PublicRoute>
            <LandingPage />
          </PublicRoute>
        }
      />
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register/reviewer"
        element={
          <PublicRoute>
            <ReviewerRegisterPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register/editor"
        element={
          <PublicRoute>
            <EditorRegisterPage />
          </PublicRoute>
        }
      />

      {/* Protected routes wrapped in AppLayout */}
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Company AI Context & Format */}
        <Route path="/company/ai-context" element={<ProtectedRoute allowedRoles={["company_admin"]}><CompanyAIContextPage /></ProtectedRoute>} />
        <Route path="/company/blog-format" element={<ProtectedRoute allowedRoles={["company_admin", "editor"]}><BlogFormatPage /></ProtectedRoute>} />
        
        {/* Knowledge & Memory */}
        <Route path="/knowledge" element={<ProtectedRoute allowedRoles={["company_admin", "editor"]}><KnowledgePage /></ProtectedRoute>} />
        <Route path="/memory" element={<ProtectedRoute allowedRoles={["company_admin", "editor"]}><MemoryPage /></ProtectedRoute>} />
        
        {/* Topic Intelligence */}
        <Route path="/topics" element={<ProtectedRoute allowedRoles={["company_admin", "editor"]}><TopicsPage /></ProtectedRoute>} />
        
        {/* Blog Lifecycle */}
        <Route path="/blogs" element={<BlogsPage />} />
        <Route path="/blogs/:id" element={<BlogDetailPage />} />
        <Route
          path="/blogs/:id/editor"
          element={
            <ProtectedRoute allowedRoles={["editor"]}>
              <BlogEditorPage />
            </ProtectedRoute>
          }
        />
        <Route path="/blogs/:id/revisions" element={<BlogRevisionsPage />} />
        
        {/* Editorial Reviews */}
        <Route path="/reviews" element={<ReviewsPage />} />
        
        {/* Scheduling & Publishing */}
        <Route path="/schedule" element={<ProtectedRoute allowedRoles={["company_admin", "editor"]}><SchedulePage /></ProtectedRoute>} />
        <Route path="/wordpress" element={<ProtectedRoute allowedRoles={["company_admin"]}><WordPressPage /></ProtectedRoute>} />
        
        {/* Admin Settings */}
        <Route
          path="/settings"
          element={
            <ProtectedRoute allowedRoles={["company_admin"]}>
              <SettingsPage />
            </ProtectedRoute>
          }
        />

        {/* Catch-all 404 within layout */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};
