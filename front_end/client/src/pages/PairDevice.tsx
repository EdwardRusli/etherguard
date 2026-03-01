import { useState } from 'react';
import { AlertCircle, CheckCircle } from 'lucide-react';

export default function PairDevice() {
  const [formData, setFormData] = useState({
    hardwareId: '',
    patientName: '',
    emergencyPhone: '',
    proximityContact: '',
    password: '',
  });

  const [pairingStatus, setPairingStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [statusMessage, setStatusMessage] = useState('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handlePairingSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Validate all fields are filled
    if (!formData.hardwareId || !formData.patientName || !formData.emergencyPhone || !formData.proximityContact || !formData.password) {
      setPairingStatus('error');
      setStatusMessage('Please fill in all fields.');
      return;
    }

    // Validate password (basic check - minimum 6 characters)
    if (formData.password.length < 6) {
      setPairingStatus('error');
      setStatusMessage('Password must be at least 6 characters long.');
      return;
    }

    // Simulate pairing success
    setPairingStatus('success');
    setStatusMessage(`Device "${formData.hardwareId}" successfully paired with password protection!`);
    
    // Reset form after 2 seconds
    setTimeout(() => {
      setFormData({ hardwareId: '', patientName: '', emergencyPhone: '', proximityContact: '', password: '' });
      setPairingStatus('idle');
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-linear-to-b from-white to-gray-100 flex items-center justify-center px-6 py-16 overflow-y-auto">
      <div className="w-full max-w-2xl">
        <div className="bg-white p-10 rounded-[2.5rem] shadow-2xl border border-gray-100">
          <h2 className="text-4xl font-black text-gray-900 mb-3">Register Your Device</h2>
          <p className="text-gray-600 mb-8 font-medium">Set up your EtherGuard device by entering the credentials from the physical device and emergency contact information.</p>

          {/* Device Info Box */}
          <div className="bg-blue-50 border-2 border-blue-200 rounded-2xl p-4 mb-6">
            <p className="text-sm text-blue-800"><strong>Where to find:</strong> Look on the back of your EtherGuard device for the Hardware ID and Password stickers.</p>
          </div>

          {/* Status Message */}
          {pairingStatus !== 'idle' && (
            <div className={`mb-6 p-4 rounded-2xl flex items-center gap-3 ${
              pairingStatus === 'success' 
                ? 'bg-green-50 border-2 border-green-200' 
                : 'bg-red-50 border-2 border-red-200'
            }`}>
              {pairingStatus === 'success' ? (
                <CheckCircle size={20} className="text-green-600 shrink-0" />
              ) : (
                <AlertCircle size={20} className="text-red-600 shrink-0" />
              )}
              <p className={pairingStatus === 'success' ? 'text-green-700 font-semibold' : 'text-red-700 font-semibold'}>
                {statusMessage}
              </p>
            </div>
          )}
        
          <form onSubmit={handlePairingSubmit} className="space-y-6">
            {/* Device Credentials Section */}
            <div className="bg-blue-50 border-2 border-blue-200 rounded-2xl p-6 mb-6">
              <h3 className="font-bold text-blue-900 mb-4 text-lg">Device Credentials</h3>
              <p className="text-sm text-blue-800 mb-4">These are unique identifiers printed on your physical EtherGuard device. <strong>Not your email or login password.</strong></p>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-bold text-gray-700 ml-2 mb-2 block">Device Hardware ID</label>
                  <input 
                    type="text" 
                    name="hardwareId"
                    value={formData.hardwareId}
                    onChange={handleInputChange}
                    placeholder="e.g., EG-2024-001" 
                    autoComplete="off"
                    className="w-full p-4 rounded-2xl border border-gray-100 bg-white focus:ring-2 focus:ring-blue-500 outline-none transition-all" 
                  />
                  <p className="text-xs text-gray-500 mt-2 ml-2">Found on the back of your physical EtherGuard device</p>
                </div>
                <div>
                  <label className="text-sm font-bold text-gray-700 ml-2 mb-2 block">Device Password</label>
                  <input 
                    type="text" 
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="Security code from device label" 
                    autoComplete="off"
                    className="w-full p-4 rounded-2xl border border-gray-100 bg-white focus:ring-2 focus:ring-blue-500 outline-none transition-all" 
                  />
                  <p className="text-xs text-gray-500 mt-2 ml-2">Security code printed on your physical device label (not your login password)</p>
                </div>
              </div>
            </div>

            {/* Emergency Contact Section */}
            <div className="bg-red-50 border-2 border-red-200 rounded-2xl p-6 mb-6">
              <h3 className="font-bold text-red-900 mb-4 text-lg">Emergency Contact Information</h3>
              <p className="text-sm text-red-800 mb-4">Contact details for the person or location being monitored.</p>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-bold text-gray-700 ml-2 mb-2 block">Monitoring Location/Name</label>
                  <input 
                    type="text" 
                    name="patientName"
                    value={formData.patientName}
                    onChange={handleInputChange}
                    placeholder="e.g., Living Room, Bedroom, John's Home" 
                    className="w-full p-4 rounded-2xl border border-gray-100 bg-white focus:ring-2 focus:ring-red-500 outline-none transition-all" 
                  />
                  <p className="text-xs text-gray-500 mt-2 ml-2">Person's name or location being monitored (e.g., room name, person name)</p>
                </div>
                <div>
                  <label className="text-sm font-bold text-gray-700 ml-2 mb-2 block">Phone Number</label>
                  <input 
                    type="text" 
                    name="emergencyPhone"
                    value={formData.emergencyPhone}
                    onChange={handleInputChange}
                    placeholder="+1 (555) 123-4567" 
                    className="w-full p-4 rounded-2xl border border-gray-100 bg-white focus:ring-2 focus:ring-red-500 outline-none transition-all" 
                  />
                </div>
                <div>
                  <label className="text-sm font-bold text-gray-700 ml-2 mb-2 block">Emergency Contact Person</label>
                  <input 
                    type="text" 
                    name="proximityContact"
                    value={formData.proximityContact}
                    onChange={handleInputChange}
                    placeholder="Name of family member or neighbor" 
                    className="w-full p-4 rounded-2xl border border-gray-100 bg-white focus:ring-2 focus:ring-red-500 outline-none transition-all" 
                  />
                </div>
              </div>
            </div>
            
            <button 
              type="submit"
              className="w-full py-5 bg-black text-white rounded-2xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={pairingStatus !== 'idle'}
            >
              Register Device
            </button>

            <p className="text-xs text-gray-600 text-center">After registration, anyone with the Hardware ID can monitor this device on the Devices page.</p>
          </form>
        </div>
      </div>
    </div>
  );
}