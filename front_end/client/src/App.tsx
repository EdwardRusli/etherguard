import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import PairDevice from './pages/PairDevice';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Resources from './pages/Resources';
import Profile from './pages/Profile';
import { Activity, PlusCircle, Menu, X, User } from 'lucide-react';
import { useState } from 'react';

// Navigation component with mobile menu
function Navigation({ onLogout }: { onLogout: () => void }) {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  
  // Do not show the navbar if we are on the landing page ("/") or login page
  if (location.pathname === '/' || location.pathname === '/login') return null;

  const menuItems = [
    { label: 'Devices', href: '/devices' },
    { label: 'Resources', href: '/resources' },
  ];

  return (
    <nav className="border-b border-gray-200 bg-white/50 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Activity className="text-red-500" />
          <span className="text-xl font-bold tracking-tight text-gray-900">EtherGuard</span>
        </Link>

        {/* Desktop Menu */}
        <div className="hidden lg:flex gap-2 items-center">
          <div className="flex gap-1">
            {menuItems.slice(0, 3).map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={`text-sm font-medium px-3 py-2 rounded-lg transition ${
                  location.pathname === item.href
                    ? 'bg-red-100 text-red-600'
                    : 'text-gray-600 hover:text-black'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>

          {/* Profile Dropdown */}
          <div className="relative ml-4">
            <button
              onClick={() => setProfileMenuOpen(!profileMenuOpen)}
              className="flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-full hover:bg-red-700 transition font-medium shadow-lg"
            >
              <User size={18} />
              <span>Profile</span>
            </button>
            
            {profileMenuOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-white border-2 border-gray-200 rounded-xl shadow-xl py-2 z-50">
                <Link
                  to="/profile"
                  className="block px-4 py-2 text-gray-700 hover:bg-red-50 hover:text-red-600 transition font-medium"
                  onClick={() => setProfileMenuOpen(false)}
                >
                  My Profile
                </Link>
                <button
                  onClick={() => {
                    onLogout();
                    setProfileMenuOpen(false);
                  }}
                  className="w-full text-left px-4 py-2 text-gray-700 hover:bg-red-50 hover:text-red-600 transition font-medium"
                >
                  Logout
                </button>
              </div>
            )}
          </div>

          <Link to="/pair" className="flex items-center gap-1 text-sm font-medium bg-black text-white px-4 py-2 rounded-full hover:bg-gray-800 transition shadow-lg">
            <PlusCircle size={16} />
            Pair Device
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <div className="lg:hidden flex items-center gap-4">
          <Link to="/pair" className="flex items-center gap-1 text-sm font-medium bg-black text-white px-3 py-2 rounded-full hover:bg-gray-800 transition">
            <PlusCircle size={16} />
          </Link>
          <Link to="/profile" className="flex items-center gap-1 text-sm font-medium bg-red-600 text-white px-3 py-2 rounded-full hover:bg-red-700 transition">
            <User size={18} />
          </Link>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-gray-200 bg-white/95 backdrop-blur-md">
          <div className="px-6 py-4 space-y-2">
            {menuItems.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={`block px-4 py-2 rounded-lg transition font-medium ${
                  location.pathname === item.href
                    ? 'bg-red-100 text-red-600'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
                onClick={() => setMobileMenuOpen(false)}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}

function App() {
  const [userEmail, setUserEmail] = useState<string | null>(() => {
    // Initialize from localStorage
    return localStorage.getItem('userEmail');
  });

  const handleLogin = (email: string) => {
    setUserEmail(email);
    localStorage.setItem('userEmail', email);
  };

  const handleLogout = () => {
    setUserEmail(null);
    localStorage.removeItem('userEmail');
  };

  return (
    <Router>
      <div className="min-h-screen bg-linear-to-b from-white to-gray-200 text-gray-900 font-sans">
        <Navigation onLogout={handleLogout} />
        <main>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/devices" element={userEmail ? <Dashboard /> : <Navigate to="/login" />} />
            <Route path="/pair" element={userEmail ? <PairDevice /> : <Navigate to="/login" />} />
            <Route path="/resources" element={userEmail ? <Resources /> : <Navigate to="/login" />} />
            <Route path="/profile" element={userEmail ? <Profile userEmail={userEmail} /> : <Navigate to="/login" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;