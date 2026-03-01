import { useNavigate } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';

// Add custom animation styles
const styles = `
  html {
    scroll-behavior: smooth;
  }
  
  .snap-container {
    scroll-snap-type: y mandatory;
    overflow-y: scroll;
  }
  
  .snap-section {
    scroll-snap-align: start;
    scroll-snap-stop: always;
  }
  
  @keyframes float-down-up {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(8px); }
  }
  .animate-float-down-up {
    animation: float-down-up 2s ease-in-out infinite;
  }
`;

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="snap-container h-screen overflow-y-scroll">
      <style>{styles}</style>
      {/* Hero Section */}
      <div className="snap-section relative h-screen w-full flex items-center justify-center overflow-hidden">
        {/* Background Image with Overlay */}
        <div 
          className="absolute inset-0 z-0 bg-cover bg-center transition-transform duration-700 hover:scale-105"
          style={{ backgroundImage: `url('https://i.ibb.co/Zz0BZbvH/180205173239-vital-signs-elderly-with-children-1.jpg')` }}
        >
          <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"></div>
        </div>

        {/* Content */}
        <div className="relative z-10 text-center px-6">
          <h1 className="text-5xl md:text-7xl font-black text-white mb-6 tracking-tight">
            Care that <span className="text-red-500">Never Sleeps.</span>
          </h1>
          <p className="text-lg md:text-xl text-gray-200 mb-10 max-w-2xl mx-auto font-light">
            Using advanced WiFi sensing technology to protect our seniors with non-invasive, 24/7 fall detection.
          </p>
          
          <button 
            onClick={() => navigate('/login')}
            className="px-8 py-4 bg-white text-black font-bold rounded-2xl hover:bg-gray-200 transition-all shadow-xl"
          >
            Account Login
          </button>
        </div>

        {/* Bottom Hint - Outside centered content */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/50 text-sm animate-float-down-up">
          <span>Scroll down to learn more</span>
          <ChevronDown size={20} />
        </div>
      </div>

      {/* About Section */}
      <div className="snap-section min-h-screen flex items-center justify-center bg-linear-to-b from-gray-50 to-white py-20 px-6">
        <div className="max-w-4xl w-full">
          <h2 className="text-5xl md:text-6xl font-black text-gray-900 mb-12 text-center">Our Mission</h2>
          
          <div className="space-y-8">
            <div className="bg-white p-10 rounded-3xl shadow-lg border border-gray-100">
              <p className="text-xl md:text-2xl font-bold text-red-500 mb-4">
                Safety shouldn't mean a loss of privacy.
              </p>
              <p className="text-gray-700 text-lg leading-relaxed">
                Traditional fall detection relies on cameras or wearable pendants. Cameras are invasive, and pendants are often forgotten or refused by the elderly.
              </p>
            </div>

            <div className="bg-white p-10 rounded-3xl shadow-lg border border-gray-100">
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Our Technology</h3>
              <p className="text-gray-700 text-lg leading-relaxed">
                We use <span className="font-bold text-red-500">WiFi Channel State Information (CSI)</span>. By analyzing how WiFi signals bounce off objects and bodies in a room, our AI can detect the specific "signature" of a fall without ever recording a single image.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-linear-to-br from-red-50 to-red-100 p-8 rounded-3xl border border-red-200 text-center">
                <h4 className="text-xl font-black text-red-600 mb-3">100% Private</h4>
                <p className="text-gray-700">No cameras, no microphones, no footage.</p>
              </div>
              <div className="bg-linear-to-br from-blue-50 to-blue-100 p-8 rounded-3xl border border-blue-200 text-center">
                <h4 className="text-xl font-black text-blue-600 mb-3">Zero Wearables</h4>
                <p className="text-gray-700">Nothing to charge or wear. Truly passive.</p>
              </div>
              <div className="bg-linear-to-br from-green-50 to-green-100 p-8 rounded-3xl border border-green-200 text-center">
                <h4 className="text-xl font-black text-green-600 mb-3">Real-time</h4>
                <p className="text-gray-700">Instant alerts to caregivers 24/7.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}