import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import PairDevice from './pages/PairDevice';
import Landing from './pages/Landing';
import AboutUs from './pages/AboutUs';
import HealthTips from './pages/HealthTips';
import EmergencyContacts from './pages/EmergencyContacts';
import Accessibility from './pages/Accessibility';
import ActivityLog from './pages/ActivityLog';
import DeviceSettings from './pages/DeviceSettings';
import Resources from './pages/Resources';
import SecurityAddons from './pages/secadd';
import Addons from './pages/addons';
import { Activity, PlusCircle, Menu, X } from 'lucide-react';
import { useState } from 'react';

// Navigation component with mobile menu
function Navigation() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  // Do not show the navbar if we are on the landing page ("/")
  if (location.pathname === '/') return null;

  const menuItems = [
    { label: 'Dashboard', href: '/dashboard' },
    { label: 'Health Tips', href: '/health-tips' },
    { label: 'Add-ons', href: '/addons' },
    { label: 'Security', href: '/security' },
    { label: 'Activity Log', href: '/activity-log' },
    { label: 'Device Settings', href: '/device-settings' },
    { label: 'Emergency Contacts', href: '/emergency-contacts' },
    { label: 'Accessibility', href: '/accessibility' },
    { label: 'Resources', href: '/resources' },
    { label: 'About', href: '/about' },
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
            {menuItems.slice(0, 5).map((item) => (
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
  return (
    <Router>
      <div className="min-h-screen bg-linear-to-b from-white to-gray-200 text-gray-900 font-sans">
        <Navigation />
        <main>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/about" element={<AboutUs />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pair" element={<PairDevice />} />
            <Route path="/health-tips" element={<HealthTips />} />
            <Route path="/emergency-contacts" element={<EmergencyContacts />} />
            <Route path="/accessibility" element={<Accessibility />} />
            <Route path="/activity-log" element={<ActivityLog />} />
            <Route path="/device-settings" element={<DeviceSettings />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/security" element={<SecurityAddons />} />
            <Route path="/addons" element={<Addons />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;