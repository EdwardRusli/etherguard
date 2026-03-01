import { ShieldCheck, MapPin, Phone, AlertTriangle } from 'lucide-react';

const mockDevices = [
  { id: '1', name: 'Living Room - Unit A', status: 'safe', patient: 'Arthur Morgan', location: '123 Oak St.', contact: 'Dutch (555-0123)' },
  { id: '2', name: 'Bedroom - Unit B', status: 'fall_detected', patient: 'John Marston', location: '456 Hill Rd.', contact: 'Abigail (555-0987)' },
];

export default function Dashboard() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <h2 className="text-4xl font-bold mb-12 text-center">Monitoring Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockDevices.map((device) => (
          <div key={device.id} className={`p-6 rounded-3xl border transition-all shadow-sm bg-white/80 ${
            device.status === 'fall_detected' ? 'ring-4 ring-red-500 animate-pulse border-red-200' : 'border-white'
          }`}>
            <div className="flex justify-between items-start mb-4">
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-widest ${
                device.status === 'fall_detected' ? 'bg-red-500 text-white' : 'bg-green-100 text-green-700'
              }`}>
                {device.status === 'fall_detected' ? 'Critical Fall' : 'Monitoring'}
              </span>
              {device.status === 'fall_detected' ? <AlertTriangle className="text-red-500" /> : <ShieldCheck className="text-green-500" />}
            </div>

            <h3 className="text-xl font-bold text-gray-800">{device.patient}</h3>
            <p className="text-gray-500 text-sm mb-4">{device.name}</p>

            <div className="space-y-3 pt-4 border-t border-gray-100">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <MapPin size={16} /> <span>{device.location}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-600 font-medium">
                <Phone size={16} /> <span className="text-red-600">{device.contact}</span>
              </div>
            </div>

            {device.status === 'fall_detected' && (
              <button className="w-full mt-6 py-3 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 shadow-lg shadow-red-200">
                DISPATCH EMERGENCY
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}