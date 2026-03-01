export default function AboutUs() {
  return (
    <div className="max-w-4xl mx-auto py-12">
      <h2 className="text-4xl font-black text-gray-900 mb-6">Our Mission</h2>
      <div className="bg-white/70 backdrop-blur-md p-10 rounded-[2.5rem] border border-white shadow-xl space-y-6 text-gray-700 leading-relaxed">
        <p className="text-xl font-medium">
          We believe safety shouldn't mean a loss of privacy. 
        </p>
        <p>
          Traditional fall detection relies on cameras or wearable pendants. Cameras are invasive, and pendants are often forgotten or refused by the elderly.
        </p>
        <p>
          Our project uses <strong>WiFi Channel State Information (CSI)</strong>. By analyzing how WiFi signals bounce off objects and bodies in a room, our AI can detect the specific "signature" of a fall without ever recording a single image.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
          <div className="p-4 bg-gray-50 rounded-2xl text-center">
            <h4 className="font-bold text-black">100% Private</h4>
            <p className="text-sm">No cameras, no microphones.</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-2xl text-center">
            <h4 className="font-bold text-black">Zero Wearables</h4>
            <p className="text-sm">Nothing to charge or wear.</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-2xl text-center">
            <h4 className="font-bold text-black">Real-time</h4>
            <p className="text-sm">Instant alerts to caregivers.</p>
          </div>
        </div>
      </div>
    </div>
  );
}