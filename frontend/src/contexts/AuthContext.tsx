import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import axios from 'axios';
import type { User } from '../types';
import { authApi } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, username: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          const userData = await authApi.getMe();
          setUser(userData);
          setToken(storedToken);
        } catch (error) {
          // Only clear token on authentication errors (401)
          // Keep token for network errors so user can retry
          if (axios.isAxiosError(error) && error.response?.status === 401) {
            localStorage.removeItem('token');
            setToken(null);
          }
          // For other errors (network, 500, etc.), keep the token
          // User can retry or the token might still be valid
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    localStorage.setItem('token', response.access_token);
    setToken(response.access_token);

    const userData = await authApi.getMe();
    setUser(userData);
  };

  const register = async (email: string, password: string, username: string) => {
    await authApi.register({ email, password, username });
    // Auto login after registration
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!token && !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
