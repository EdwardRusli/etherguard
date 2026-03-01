import { Settings, Volume2, Eye, Smartphone, BookOpen, HelpCircle } from 'lucide-react';
import { useState } from 'react';

export default function Accessibility() {
  const [settings, setSettings] = useState({
    textSize: 'medium',
    highContrast: false,
    largeButtons: false,
    animations: true,
    soundAlerts: true,
  });

  const guides = [
    {
      icon: Smartphone,
      title: 'Getting Started with EtherGuard',
      description: 'Learn how to set up your device and pair it with the monitoring system.',
      sections: [
        'Device Placement',
        'WiFi Connection',
        'Initial Setup',
        'Pairing with App'
      ]
    },
    {
      icon: Volume2,
      title: 'Audio & Notifications',
      description: 'Understand how alerts and notifications will reach your caregivers.',
      sections: [
        'Alert Types',
        'Sound Settings',
        'Notification Frequency',
        'Custom Preferences'
      ]
    },
    {
      icon: Eye,
      title: 'Visual Features',
      description: 'Explore accessibility options for better visibility and readability.',
      sections: [
        'Text Size Options',
        'Color Contrast',
        'Icon Clarity',
        'Display Settings'
      ]
    },
  ];

  const handleSettingChange = (key: keyof typeof settings) => {
    setSettings(prev => ({
      ...prev,
      [key]: typeof prev[key] === 'boolean' ? !prev[key] : prev[key]
    }));
  };

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Accessibility</h1>
          <p className="text-xl text-gray-600">Customize your experience for comfort and ease of use</p>
        </div>

        {/* Settings Section */}
        <div className="mb-16">
          <div className="flex items-center gap-3 mb-8">
            <Settings className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Display & Interface Settings</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Text Size */}
            <div className="bg-linear-to-br from-blue-50 to-blue-100 p-8 rounded-3xl border-2 border-blue-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Text Size</h3>
              <div className="space-y-3">
                {['small', 'medium', 'large'].map(size => (
                  <label key={size} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="radio"
                      name="textSize"
                      checked={settings.textSize === size}
                      onChange={() => setSettings(prev => ({ ...prev, textSize: size }))}
                      className="w-4 h-4"
                    />
                    <span className={`font-bold capitalize ${
                      size === 'small' ? 'text-sm' : size === 'large' ? 'text-lg' : 'text-base'
                    }`}>
                      {size === 'small' ? 'Small' : size === 'large' ? 'Large' : 'Medium'}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* High Contrast */}
            <div className="bg-linear-to-br from-purple-50 to-purple-100 p-8 rounded-3xl border-2 border-purple-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">High Contrast Mode</h3>
              <button
                onClick={() => handleSettingChange('highContrast')}
                className={`w-full px-4 py-3 rounded-xl font-bold transition-all ${
                  settings.highContrast
                    ? 'bg-purple-600 text-white'
                    : 'bg-white border-2 border-purple-300 text-gray-900'
                }`}
              >
                {settings.highContrast ? '✓ Enabled' : 'Enable'}
              </button>
              <p className="text-sm text-gray-700 mt-3">Increases color contrast for better visibility</p>
            </div>

            {/* Large Buttons */}
            <div className="bg-linear-to-br from-green-50 to-green-100 p-8 rounded-3xl border-2 border-green-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Large Touch Buttons</h3>
              <button
                onClick={() => handleSettingChange('largeButtons')}
                className={`w-full px-4 py-3 rounded-xl font-bold transition-all ${
                  settings.largeButtons
                    ? 'bg-green-600 text-white'
                    : 'bg-white border-2 border-green-300 text-gray-900'
                }`}
              >
                {settings.largeButtons ? '✓ Enabled' : 'Enable'}
              </button>
              <p className="text-sm text-gray-700 mt-3">Makes buttons and controls easier to tap</p>
            </div>

            {/* Animations */}
            <div className="bg-linear-to-br from-orange-50 to-orange-100 p-8 rounded-3xl border-2 border-orange-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Animations</h3>
              <button
                onClick={() => handleSettingChange('animations')}
                className={`w-full px-4 py-3 rounded-xl font-bold transition-all ${
                  settings.animations
                    ? 'bg-orange-600 text-white'
                    : 'bg-white border-2 border-orange-300 text-gray-900'
                }`}
              >
                {settings.animations ? '✓ Enabled' : 'Enable'}
              </button>
              <p className="text-sm text-gray-700 mt-3">Reduce motion and animations</p>
            </div>

            {/* Sound Alerts */}
            <div className="bg-linear-to-br from-cyan-50 to-cyan-100 p-8 rounded-3xl border-2 border-cyan-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Sound Alerts</h3>
              <button
                onClick={() => handleSettingChange('soundAlerts')}
                className={`w-full px-4 py-3 rounded-xl font-bold transition-all ${
                  settings.soundAlerts
                    ? 'bg-cyan-600 text-white'
                    : 'bg-white border-2 border-cyan-300 text-gray-900'
                }`}
              >
                {settings.soundAlerts ? '✓ Enabled' : 'Enable'}
              </button>
              <p className="text-sm text-gray-700 mt-3">Play sounds for notifications and alerts</p>
            </div>

            {/* Reset */}
            <div className="bg-linear-to-br from-red-50 to-red-100 p-8 rounded-3xl border-2 border-red-200">
              <h3 className="text-xl font-black text-gray-900 mb-4">Reset to Default</h3>
              <button
                onClick={() => setSettings({
                  textSize: 'medium',
                  highContrast: false,
                  largeButtons: false,
                  animations: true,
                  soundAlerts: true,
                })}
                className="w-full px-4 py-3 bg-white border-2 border-red-300 text-gray-900 font-bold rounded-xl hover:bg-red-50 transition-all"
              >
                Reset All
              </button>
              <p className="text-sm text-gray-700 mt-3">Restore default settings</p>
            </div>
          </div>
        </div>

        {/* Guides Section */}
        <div>
          <div className="flex items-center gap-3 mb-8">
            <BookOpen className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Learning Guides</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {guides.map((guide, idx) => {
              const Icon = guide.icon;
              return (
                <div key={idx} className="bg-white border-2 border-gray-200 rounded-3xl p-8 hover:shadow-lg transition-all">
                  <Icon className="text-red-600 mb-4" size={40} />
                  <h3 className="text-2xl font-black text-gray-900 mb-3">{guide.title}</h3>
                  <p className="text-gray-600 mb-6">{guide.description}</p>
                  
                  <div className="space-y-2 pt-6 border-t border-gray-200">
                    {guide.sections.map((section, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <HelpCircle size={16} className="text-blue-600 shrink-0" />
                        <p className="text-gray-700 font-medium">{section}</p>
                      </div>
                    ))}
                  </div>

                  <button className="w-full mt-6 px-4 py-3 bg-red-600 text-white font-bold rounded-xl hover:bg-red-700 transition-all">
                    Learn More
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Support */}
        <div className="mt-16 bg-linear-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-3xl p-8">
          <div className="flex items-start gap-4">
            <HelpCircle className="text-blue-600 shrink-0" size={32} />
            <div>
              <h3 className="text-2xl font-black text-gray-900 mb-2">Need Help?</h3>
              <p className="text-gray-700 mb-4">
                If you have questions about accessibility features or need assistance, contact our support team.
              </p>
              <button className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-all">
                Contact Support
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
