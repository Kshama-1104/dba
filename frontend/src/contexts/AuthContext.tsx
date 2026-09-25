import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { authApi } from "../api/auth";
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
  setUnauthorizedHandler,
} from "../api/client";
import { companyApi } from "../api/company";
import { CompanyInfo, User, UserRole } from "../types";

interface AuthContextType {
  user: User | null;
  company: CompanyInfo | null;
  role: UserRole | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setCompany(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const activeToken = getStoredToken();
    if (!activeToken) {
      setUser(null);
      setCompany(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await authApi.getMe();
      setUser(userData);

      // If user is company_admin, load full company dashboard info
      if (userData.role === "company_admin") {
        try {
          const dashData = await companyApi.getDashboard();
          setCompany(dashData.company);
        } catch {
          // If dashboard call fails, company info remains null
        }
      } else {
        // For editor / reviewer, establish base company entity
        setCompany({
          id: userData.company_id,
          name: `Company #${userData.company_id}`,
          description: null,
          logo_url: null,
          company_type: null,
          industry: null,
          country_region: null,
          company_email: null,
          notification_email: null,
        });
      }
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    refreshUser();
  }, [logout, refreshUser]);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const resp = await authApi.login({ email, password });
      setStoredToken(resp.access_token);
      setToken(resp.access_token);
      await refreshUser();
    } finally {
      setIsLoading(false);
    }
  };

  const value: AuthContextType = {
    user,
    company,
    role: user?.role ?? null,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
