import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, AlertCircle, CheckCircle } from 'lucide-react';

interface LoginProps {
  onLogin: (email: string) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const navigate = useNavigate();
  
  // Form states
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [createEmail, setCreateEmail] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createPasswordConfirm, setCreatePasswordConfirm] = useState('');
  const [forgotEmail, setForgotEmail] = useState('');
  
  // UI states
  const [currentView, setCurrentView] = useState<'login' | 'create' | 'forgot'>('login');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleLogin = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!loginEmail || !loginPassword) {
      setStatus('error');
      setMessage('Please fill in all fields.');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(loginEmail)) {
      setStatus('error');
      setMessage('Please enter a valid email address.');
      return;
    }

    if (loginPassword.length < 6) {
      setStatus('error');
      setMessage('Password must be at least 6 characters.');
      return;
    }

    setStatus('loading');
    setTimeout(() => {
      setStatus('success');
      setMessage(`Welcome back, ${loginEmail}!`);
      localStorage.setItem('userEmail', loginEmail);
      onLogin(loginEmail);
      setTimeout(() => {
        navigate('/devices');
      }, 1000);
    }, 800);
  };

  const handleCreateAccount = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!createEmail || !createPassword || !createPasswordConfirm) {
      setStatus('error');
      setMessage('Please fill in all fields.');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(createEmail)) {
      setStatus('error');
      setMessage('Please enter a valid email address.');
      return;
    }

    if (createPassword.length < 6) {
      setStatus('error');
      setMessage('Password must be at least 6 characters.');
      return;
    }

    if (createPassword !== createPasswordConfirm) {
      setStatus('error');
      setMessage('Passwords do not match.');
      return;
    }

    setStatus('loading');
    setTimeout(() => {
      setStatus('success');
      setMessage(`Account created successfully! Welcome, ${createEmail}!`);
      localStorage.setItem('userEmail', createEmail);
      onLogin(createEmail);
      setTimeout(() => {
        navigate('/devices');
      }, 1000);
    }, 800);
  };

  const handleForgotPassword = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!forgotEmail) {
      setStatus('error');
      setMessage('Please enter your email address.');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(forgotEmail)) {
      setStatus('error');
      setMessage('Please enter a valid email address.');
      return;
    }

    setStatus('loading');
    setTimeout(() => {
      setStatus('success');
      setMessage(`Password reset link sent to ${forgotEmail}. Check your email!`);
      setTimeout(() => {
        setCurrentView('login');
        setStatus('idle');
        setMessage('');
        setForgotEmail('');
      }, 2000);
    }, 800);
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-gray-50 to-gray-200 flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-3xl shadow-2xl p-10 border border-gray-100">
          <h1 className="text-4xl font-black text-gray-900 mb-2 text-center">EtherGuard</h1>
          <p className="text-center text-gray-500 mb-8 font-medium">Care that Never Sleeps</p>

          {/* Tabs */}
          <div className="flex gap-2 mb-8">
            <button
              onClick={() => {
                setCurrentView('login');
                setStatus('idle');
                setMessage('');
              }}
              className={`flex-1 py-2 px-4 rounded-xl font-bold transition ${
                currentView === 'login'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Login
            </button>
            <button
              onClick={() => {
                setCurrentView('create');
                setStatus('idle');
                setMessage('');
              }}
              className={`flex-1 py-2 px-4 rounded-xl font-bold transition ${
                currentView === 'create'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Sign Up
            </button>
            <button
              onClick={() => {
                setCurrentView('forgot');
                setStatus('idle');
                setMessage('');
              }}
              className={`flex-1 py-2 px-4 rounded-xl font-bold transition text-sm ${
                currentView === 'forgot'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Reset
            </button>
          </div>

          {/* Status Message */}
          {status !== 'idle' && (
            <div
              className={`mb-6 p-4 rounded-2xl flex items-center gap-3 ${
                status === 'success'
                  ? 'bg-green-50 border-2 border-green-200'
                  : status === 'error'
                  ? 'bg-red-50 border-2 border-red-200'
                  : 'bg-blue-50 border-2 border-blue-200'
              }`}
            >
              {status === 'success' ? (
                <CheckCircle size={20} className="text-green-600 shrink-0" />
              ) : status === 'error' ? (
                <AlertCircle size={20} className="text-red-600 shrink-0" />
              ) : (
                <div className="w-5 h-5 border-2 border-blue-400 border-t-blue-600 rounded-full animate-spin shrink-0" />
              )}
              <p
                className={`font-semibold text-sm ${
                  status === 'success'
                    ? 'text-green-700'
                    : status === 'error'
                    ? 'text-red-700'
                    : 'text-blue-700'
                }`}
              >
                {message}
              </p>
            </div>
          )}

          {/* Login Tab */}
          {currentView === 'login' && (
            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="email"
                    value={loginEmail}
                    onChange={(e) => {
                      setLoginEmail(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="you@example.com"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => {
                      setLoginPassword(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="Minimum 6 characters"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={status !== 'idle'}
                className="w-full py-4 bg-red-600 text-white font-bold rounded-2xl hover:bg-red-700 active:bg-red-800 transition-all shadow-xl disabled:opacity-50 disabled:cursor-not-allowed text-lg"
              >
                {status === 'loading' ? 'Logging in...' : 'Login'}
              </button>
            </form>
          )}

          {/* Create Account Tab */}
          {currentView === 'create' && (
            <form onSubmit={handleCreateAccount} className="space-y-6">
              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="email"
                    value={createEmail}
                    onChange={(e) => {
                      setCreateEmail(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="you@example.com"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="password"
                    value={createPassword}
                    onChange={(e) => {
                      setCreatePassword(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="Minimum 6 characters"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="password"
                    value={createPasswordConfirm}
                    onChange={(e) => {
                      setCreatePasswordConfirm(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="Repeat your password"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={status !== 'idle'}
                className="w-full py-4 bg-red-600 text-white font-bold rounded-2xl hover:bg-red-700 active:bg-red-800 transition-all shadow-xl disabled:opacity-50 disabled:cursor-not-allowed text-lg"
              >
                {status === 'loading' ? 'Creating Account...' : 'Create Account'}
              </button>
            </form>
          )}

          {/* Forgot Password Tab */}
          {currentView === 'forgot' && (
            <form onSubmit={handleForgotPassword} className="space-y-6">
              <p className="text-gray-600 text-sm">Enter your email and we'll send you a link to reset your password.</p>
              
              <div>
                <label className="text-sm font-bold text-gray-700 mb-2 block">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-4 text-gray-400" size={20} />
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => {
                      setForgotEmail(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    placeholder="your@email.com"
                    className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-2xl focus:outline-none focus:border-red-500 focus:bg-white transition-all bg-gray-50 text-gray-900"
                    disabled={status === 'loading' || status === 'success'}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={status !== 'idle'}
                className="w-full py-4 bg-red-600 text-white font-bold rounded-2xl hover:bg-red-700 active:bg-red-800 transition-all shadow-xl disabled:opacity-50 disabled:cursor-not-allowed text-lg"
              >
                {status === 'loading' ? 'Sending Link...' : 'Send Reset Link'}
              </button>
            </form>
          )}

          <p className="text-center text-gray-500 text-xs mt-8 font-medium">
            Demo: Use any email with password "password" to login
          </p>
        </div>
      </div>
    </div>
  );
}
