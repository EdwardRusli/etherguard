import { Wifi, Zap, RotateCw, AlertCircle, CheckCircle, Gauge } from 'lucide-react';
import { useState } from 'react';

interface Device {
  id: string;
  name: string;
  status: 'connected' | 'disconnected';
  signal: number;
  lastUpdate: string;
  firmware: string;
}

export default function DeviceSettings() {
  const [devices] = useState<Device[]>([
    {
      id: '1',
      name: 'Living Room Unit',
      status: 'connected',
      signal: 85,
      lastUpdate: '2 minutes ago',
      firmware: 'v2.1.4'
    },
    {
      id: '2',
      name: 'Bedroom Unit',
      status: 'connected',
      signal: 72,
      lastUpdate: '5 minutes ago',
      firmware: 'v2.1.4'
    },
  ]);

  const [calibrating, setCalibrating] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null);

  const handleCalibrate = (deviceId: string) => {
    setSelectedDevice(deviceId);
    setCalibrating(true);
    // Simulate calibration
    setTimeout(() => {
      setCalibrating(false);
      setSelectedDevice(null);
    }, 3000);
  };

  const getSignalColor = (signal: number) => {
    if (signal >= 80) return 'text-green-600';
    if (signal >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };



  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Device Settings</h1>
          <p className="text-xl text-gray-600">Manage and calibrate your EtherGuard monitoring devices</p>
        </div>

        {/* Connected Devices */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-8">
            <Wifi className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Connected Devices</h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {devices.map((device) => (
              <div
                key={device.id}
                className={`p-8 rounded-3xl border-2 transition-all ${
                  device.status === 'connected'
                    ? 'bg-green-50 border-green-200 shadow-lg'
                    : 'bg-red-50 border-red-200'
                }`}
              >
                {/* Device Header */}
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h3 className="text-2xl font-black text-gray-900">{device.name}</h3>
                    <p className="text-gray-600 text-sm mt-1">ID: {device.id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {device.status === 'connected' ? (
                      <span className="px-3 py-1 bg-green-600 text-white text-xs font-bold rounded-full flex items-center gap-2">
                        <CheckCircle size={14} />
                        Connected
                      </span>
                    ) : (
                      <span className="px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full flex items-center gap-2">
                        <AlertCircle size={14} />
                        Disconnected
                      </span>
                    )}
                  </div>
                </div>

                {/* Device Stats */}
                <div className="grid grid-cols-2 gap-4 pt-6 border-t border-white/50">
                  {/* Signal Strength */}
                  <div>
                    <p className="text-xs font-bold text-gray-500 uppercase mb-2">Signal Strength</p>
                    <div className="relative h-2 bg-white rounded-full overflow-hidden mb-2">
                      <div
                        className={`h-full rounded-full transition-all ${getSignalColor(device.signal)}`}
                        style={{ width: `${device.signal}%` }}
                      />
                    </div>
                    <p className={`font-black ${getSignalColor(device.signal)}`}>{device.signal}%</p>
                  </div>

                  {/* Firmware */}
                  <div>
                    <p className="text-xs font-bold text-gray-500 uppercase mb-2">Firmware</p>
                    <p className="font-black text-gray-900">{device.firmware}</p>
                  </div>

                  {/* Last Update */}
                  <div className="col-span-2">
                    <p className="text-xs font-bold text-gray-500 uppercase mb-2">Last Update</p>
                    <p className="text-gray-900 font-bold">{device.lastUpdate}</p>
                  </div>
                </div>

                {/* Calibration Button */}
                {device.status === 'connected' && (
                  <button
                    onClick={() => handleCalibrate(device.id)}
                    disabled={calibrating && selectedDevice === device.id}
                    className={`w-full mt-6 px-4 py-3 font-bold rounded-xl transition-all flex items-center justify-center gap-2 ${
                      calibrating && selectedDevice === device.id
                        ? 'bg-blue-400 text-white'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    }`}
                  >
                    <Gauge size={18} />
                    {calibrating && selectedDevice === device.id ? 'Calibrating...' : 'Calibrate Device'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Calibration Guide */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-8">
            <RotateCw className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Device Calibration</h2>
          </div>

          <div className="bg-blue-50 border-2 border-blue-200 rounded-3xl p-8">
            <h3 className="text-2xl font-black text-gray-900 mb-6">How to Calibrate Your Device</h3>
            
            <div className="space-y-6">
              {[
                {
                  step: 1,
                  title: 'Clear the Space',
                  description: 'Make sure the room is empty and there are no obstacles between the device and the monitoring area.'
                },
                {
                  step: 2,
                  title: 'Power Cycle',
                  description: 'Unplug the device for 10 seconds, then plug it back in. Wait for the LED to turn blue.'
                },
                {
                  step: 3,
                  title: 'Select Calibrate',
                  description: 'Click the "Calibrate Device" button above and wait for 3-5 minutes.'
                },
                {
                  step: 4,
                  title: 'Confirmation',
                  description: 'The device will display a confirmation when calibration is complete. The app will notify you.'
                },
              ].map((item) => (
                <div key={item.step} className="flex gap-4 items-start">
                  <div className="shrink-0 w-10 h-10 bg-red-600 text-white rounded-full flex items-center justify-center font-black">
                    {item.step}
                  </div>
                  <div className="flex-1">
                    <h4 className="font-black text-gray-900 mb-1">{item.title}</h4>
                    <p className="text-gray-700">{item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Network Settings */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-8">
            <Zap className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Network Settings</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-linear-to-br from-purple-50 to-purple-100 p-8 rounded-3xl border-2 border-purple-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">WiFi Configuration</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-bold text-gray-700 mb-2">SSID</label>
                  <input
                    type="text"
                    placeholder="Your WiFi network name"
                    className="w-full px-4 py-3 border-2 border-purple-300 rounded-xl focus:outline-none focus:border-purple-600"
                  />
                </div>
                <div>
                  <label className="block text-sm font-bold text-gray-700 mb-2">Password</label>
                  <input
                    type="password"
                    placeholder="WiFi password"
                    className="w-full px-4 py-3 border-2 border-purple-300 rounded-xl focus:outline-none focus:border-purple-600"
                  />
                </div>
                <button className="w-full px-4 py-3 bg-purple-600 text-white font-bold rounded-xl hover:bg-purple-700 transition-all">
                  Update WiFi
                </button>
              </div>
            </div>

            <div className="bg-linear-to-br from-orange-50 to-orange-100 p-8 rounded-3xl border-2 border-orange-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Advanced Settings</h3>
              <div className="space-y-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4" defaultChecked />
                  <span className="font-bold text-gray-900">Auto-update firmware</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4" defaultChecked />
                  <span className="font-bold text-gray-900">Enable debug mode</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4" />
                  <span className="font-bold text-gray-900">Send usage analytics</span>
                </label>
                <button className="w-full mt-6 px-4 py-3 bg-orange-600 text-white font-bold rounded-xl hover:bg-orange-700 transition-all">
                  Save Settings
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Troubleshooting */}
        <div className="bg-red-50 border-2 border-red-200 rounded-3xl p-8">
          <div className="flex items-start gap-4">
            <AlertCircle className="text-red-600 shrink-0" size={32} />
            <div>
              <h3 className="text-2xl font-black text-gray-900 mb-4">Troubleshooting</h3>
              <div className="space-y-3">
                <p className="text-gray-700">
                  <span className="font-bold">Device not connecting?</span> Check your WiFi network and make sure the device is within range. Try power cycling both the device and your router.
                </p>
                <p className="text-gray-700">
                  <span className="font-bold">Poor signal strength?</span> Move the device closer to your WiFi router or check for physical obstacles and interference from other electronics.
                </p>
                <p className="text-gray-700">
                  <span className="font-bold">Need more help?</span> Contact our support team at support@etherguard.io
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
