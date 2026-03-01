import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import PairDevice from './pages/PairDevice';
import Landing from './pages/Landing';
import AboutUs from './pages/AboutUs';
import { Activity, PlusCircle } from 'lucide-react';

// This sub-component checks if we are on the Landing page
function Navigation() {
  const location = useLocation();
  
  // Do not show the navbar if we are on the landing page ("/")
  if (location.pathname === '/') return null;

  return (
    <nav className="border-b border-gray-200 bg-white/50 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <Activity className="text-red-500" />
          <span className="text-xl font-bold tracking-tight text-gray-900">EtherGuard</span>
        </Link>
        <div className="flex gap-6 items-center">
          <Link to="/dashboard" className="text-sm font-medium text-gray-600 hover:text-black transition">Overview</Link>
          <Link to="/pair" className="flex items-center gap-1 text-sm font-medium bg-black text-white px-4 py-2 rounded-full hover:bg-gray-800 transition shadow-lg">
            <PlusCircle size={16} />
            Pair Device
          </Link>
        </div>
      </div>
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
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;