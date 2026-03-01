import { ShieldCheck, MapPin, Search, Trash2 } from 'lucide-react';
import { useState } from 'react';

interface Device {
  id: string;
  hardwareId: string;
  name: string;
  location: string;
  status: 'monitoring' | 'fall_detected';
  lastChecked: string;
  signal: number;
}

export default function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([
    { id: '1', hardwareId: 'EG-2024-001', name: 'John Smith - Home', location: 'Home', status: 'monitoring', lastChecked: '2 minutes ago', signal: 85 },
    { id: '2', hardwareId: 'EG-2024-002', name: 'Jane Doe - Apartment', location: 'Apartment', status: 'monitoring', lastChecked: '5 minutes ago', signal: 72 },
  ]);

  const [searchQuery, setSearchQuery] = useState('');

  const handleRemoveDevice = (id: string) => {
    setDevices(devices.filter(d => d.id !== id));
  };

  const filteredDevices = devices.filter(device =>
    device.hardwareId.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="mb-12">
        <h2 className="text-4xl font-bold text-gray-900 mb-2">Monitor Devices</h2>
        <p className="text-gray-600">Search for and monitor any EtherGuard device using its Hardware ID</p>
      </div>

      {/* Info Banner */}
      <div className="bg-linear-to-r from-blue-50 to-blue-100 border-2 border-blue-200 rounded-3xl p-6 mb-8">
        <h3 className="font-bold text-blue-900 mb-2">How it works:</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Search for any device using its Hardware ID in the search bar below</li>
          <li>• Click "Monitor" to add it to your monitored devices list</li>
          <li>• View real-time status and fall detection alerts for all monitored devices</li>
        </ul>
      </div>

      {/* Search Bar */}
      <div className="mb-8 relative">
        <Search className="absolute left-4 top-3.5 text-gray-400" size={20} />
        <input
          type="text"
          placeholder="Enter Hardware ID to search (e.g., EG-2024-001)"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-6 py-4 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500 text-gray-900 text-lg"
        />
      </div>

      {/* Devices Grid */}
      {filteredDevices.length === 0 ? (
        <div className="bg-linear-to-br from-gray-50 to-white border-2 border-dashed border-gray-300 rounded-3xl p-12 text-center">
          <Search className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-2xl font-black text-gray-900 mb-2">
            {searchQuery ? 'Device Not Found' : 'No Devices Monitored Yet'}
          </h3>
          <p className="text-gray-600">
            {searchQuery
              ? `No device found with Hardware ID "${searchQuery}"`
              : 'Use the search bar above to find and monitor any EtherGuard device by entering its Hardware ID.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDevices.map((device) => (
            <div
              key={device.id}
              className={`p-6 rounded-3xl border transition-all shadow-lg hover:shadow-xl ${
                device.status === 'fall_detected'
                  ? 'bg-red-50 border-red-300 ring-4 ring-red-500 animate-pulse'
                  : 'bg-linear-to-br from-green-50 to-green-100 border-green-300'
              }`}
            >
              <div className="flex justify-between items-start mb-4">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-widest ${
                    device.status === 'fall_detected'
                      ? 'bg-red-600 text-white'
                      : 'bg-green-600 text-white'
                  }`}
                >
                  {device.status === 'fall_detected' ? '⚠️ Fall Detected' : '✓ Monitoring'}
                </span>
                <button
                  onClick={() => handleRemoveDevice(device.id)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-100 p-2 rounded-lg transition"
                  title="Remove device"
                >
                  <Trash2 size={20} />
                </button>
              </div>

              <h3 className="text-xl font-black text-gray-900 mb-1">{device.name}</h3>
              <p className="text-sm font-bold text-gray-600 mb-3 bg-white/50 px-3 py-1 rounded-lg inline-block">
                ID: {device.hardwareId}
              </p>

              <div className="space-y-3 pt-4 border-t border-white/50">
                <div className="flex items-center gap-2 text-sm">
                  <MapPin size={16} className="text-gray-600" />
                  <span className="font-medium text-gray-700">{device.location}</span>
                </div>

                <div className="flex items-center gap-2 text-sm">
                  <ShieldCheck size={16} className={device.status === 'fall_detected' ? 'text-red-600' : 'text-green-600'} />
                  <span className="font-medium text-gray-700">Last checked: {device.lastChecked}</span>
                </div>

                <div>
                  <p className="text-xs font-bold text-gray-600 mb-1">Signal Strength</p>
                  <div className="relative h-2 bg-white rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        device.signal >= 80 ? 'bg-green-600' : device.signal >= 60 ? 'bg-yellow-600' : 'bg-red-600'
                      }`}
                      style={{ width: `${device.signal}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-600 mt-1">{Math.round(device.signal)}%</p>
                </div>
              </div>

              {device.status === 'fall_detected' && (
                <button className="w-full mt-6 py-3 bg-red-600 text-white rounded-xl font-bold hover:bg-red-700 shadow-lg shadow-red-200 transition">
                  DISPATCH EMERGENCY
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      {devices.length > 0 && (
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-linear-to-br from-blue-50 to-blue-100 p-6 rounded-3xl border-2 border-blue-200 text-center">
            <p className="text-3xl font-black text-gray-900">{devices.length}</p>
            <p className="text-gray-700 font-bold">Total Devices</p>
          </div>
          <div className="bg-linear-to-br from-green-50 to-green-100 p-6 rounded-3xl border-2 border-green-200 text-center">
            <p className="text-3xl font-black text-gray-900">{devices.filter(d => d.status === 'monitoring').length}</p>
            <p className="text-gray-700 font-bold">Monitoring</p>
          </div>
          <div className="bg-linear-to-br from-red-50 to-red-100 p-6 rounded-3xl border-2 border-red-200 text-center">
            <p className="text-3xl font-black text-gray-900">{devices.filter(d => d.status === 'fall_detected').length}</p>
            <p className="text-gray-700 font-bold">Alerts</p>
          </div>
        </div>
      )}
    </div>
  );
}