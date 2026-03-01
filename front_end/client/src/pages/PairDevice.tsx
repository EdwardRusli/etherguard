export default function PairDevice() {
  return (
    <div className="h-screen flex items-start justify-center px-6 pt-20 overflow-hidden">
      <div className="w-full max-w-xl">
        <div className="bg-white/90 p-10 rounded-[2.5rem] shadow-2xl border border-white">
        <h2 className="text-3xl font-black text-gray-900 mb-2">New Module</h2>
        <p className="text-gray-500 mb-8 font-medium">Link a WiFi sensor to a patient's address.</p>
        
        <form className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-xs font-bold text-gray-400 uppercase ml-2 mb-1 block">Hardware ID</label>
              <input type="text" placeholder="e.g. WF-2026-X" className="w-full p-4 rounded-2xl border border-gray-100 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-black outline-none transition-all" />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-bold text-gray-400 uppercase ml-2 mb-1 block">Patient Name</label>
              <input type="text" placeholder="Full Name" className="w-full p-4 rounded-2xl border border-gray-100 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-black outline-none transition-all" />
            </div>
            <div>
              <label className="text-xs font-bold text-gray-400 uppercase ml-2 mb-1 block">Emergency Phone</label>
              <input type="text" placeholder="+1..." className="w-full p-4 rounded-2xl border border-gray-100 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-black outline-none transition-all" />
            </div>
            <div>
              <label className="text-xs font-bold text-gray-400 uppercase ml-2 mb-1 block">Proximity Contact</label>
              <input type="text" placeholder="Neighbor/Relative" className="w-full p-4 rounded-2xl border border-gray-100 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-black outline-none transition-all" />
            </div>
          </div>
          
          <button className="w-full py-5 bg-black text-white rounded-2xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl">
            Confirm Pairing
          </button>
        </form>
      </div>
      </div>
    </div>
  );
}