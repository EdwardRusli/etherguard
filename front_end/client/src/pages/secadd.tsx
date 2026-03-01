import { Shield, Lock, Eye, AlertTriangle, Key, Smartphone, CheckCircle } from 'lucide-react';
import { useState } from 'react';

import type { LucideIcon } from 'lucide-react';

interface SecurityFeature {
  id: string;
  title: string;
  description: string;
  status: 'enabled' | 'disabled';
  icon: LucideIcon;
}

export default function SecurityAddons() {
  const [features, setFeatures] = useState<SecurityFeature[]>([
    {
      id: '1',
      title: '2-Factor Authentication',
      description: 'Add an extra layer of security to your account with SMS or email verification codes.',
      status: 'enabled',
      icon: Key
    },
    {
      id: '2',
      title: 'Device Lock',
      description: 'Require authentication to access sensitive device settings and emergency functions.',
      status: 'enabled',
      icon: Lock
    },
    {
      id: '3',
      title: 'Session Timeout',
      description: 'Automatically log out after 15 minutes of inactivity for added security.',
      status: 'disabled',
      icon: Smartphone
    },
    {
      id: '4',
      title: 'Encrypted Data Transfer',
      description: 'All data is encrypted end-to-end when sent to monitoring devices.',
      status: 'enabled',
      icon: Shield
    },
    {
      id: '5',
      title: 'Login Alerts',
      description: 'Get notified whenever your account is accessed from a new device.',
      status: 'enabled',
      icon: AlertTriangle
    },
    {
      id: '6',
      title: 'Activity Monitoring',
      description: 'Track all account activity and suspicious login attempts.',
      status: 'enabled',
      icon: Eye
    },
  ]);

  const toggleFeature = (id: string) => {
    setFeatures(features.map(f => 
      f.id === id ? { ...f, status: f.status === 'enabled' ? 'disabled' : 'enabled' } : f
    ));
  };

  const tips = [
    {
      title: 'Strong Passwords',
      description: 'Use passwords with at least 12 characters, including uppercase, lowercase, numbers, and symbols.',
      color: 'from-red-50 to-red-100',
      borderColor: 'border-red-200',
      accentColor: 'text-red-600'
    },
    {
      title: 'Regular Updates',
      description: 'Keep firmware and app updated to receive the latest security patches and fixes.',
      color: 'from-blue-50 to-blue-100',
      borderColor: 'border-blue-200',
      accentColor: 'text-blue-600'
    },
    {
      title: 'Secure Network',
      description: 'Ensure your WiFi network uses WPA3 encryption and you have a strong WiFi password.',
      color: 'from-green-50 to-green-100',
      borderColor: 'border-green-200',
      accentColor: 'text-green-600'
    },
    {
      title: 'Privacy Controls',
      description: 'Review and customize privacy settings regularly to control who can see monitoring data.',
      color: 'from-purple-50 to-purple-100',
      borderColor: 'border-purple-200',
      accentColor: 'text-purple-600'
    },
    {
      title: 'Backup Codes',
      description: 'Save backup authentication codes in a secure location for account recovery.',
      color: 'from-orange-50 to-orange-100',
      borderColor: 'border-orange-200',
      accentColor: 'text-orange-600'
    },
    {
      title: 'Device Management',
      description: 'Regularly review connected devices and remove access for devices you no longer use.',
      color: 'from-cyan-50 to-cyan-100',
      borderColor: 'border-cyan-200',
      accentColor: 'text-cyan-600'
    },
  ];

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Security Add-ons</h1>
          <p className="text-xl text-gray-600">Protect your data and account with advanced security features</p>
        </div>

        {/* Security Features */}
        <div className="mb-16">
          <div className="flex items-center gap-3 mb-8">
            <Shield className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Security Features</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.id}
                  className={`p-8 rounded-3xl border-2 transition-all ${
                    feature.status === 'enabled'
                      ? 'bg-green-50 border-green-200 shadow-lg'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <Icon className={feature.status === 'enabled' ? 'text-green-600' : 'text-gray-400'} size={32} />
                    <button
                      onClick={() => toggleFeature(feature.id)}
                      className={`px-4 py-2 rounded-full text-xs font-bold transition-all ${
                        feature.status === 'enabled'
                          ? 'bg-green-600 text-white'
                          : 'bg-gray-300 text-gray-700'
                      }`}
                    >
                      {feature.status === 'enabled' ? '✓ Active' : 'Inactive'}
                    </button>
                  </div>

                  <h3 className="text-xl font-black text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-gray-700">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Security Tips */}
        <div>
          <div className="flex items-center gap-3 mb-8">
            <AlertTriangle className="text-red-600" size={32} />
            <h2 className="text-3xl font-black text-gray-900">Security Best Practices</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {tips.map((tip, idx) => (
              <div
                key={idx}
                className={`bg-linear-to-br ${tip.color} p-8 rounded-3xl border-2 ${tip.borderColor} shadow-lg hover:shadow-xl transition-all`}
              >
                <CheckCircle className={`${tip.accentColor} mb-4`} size={32} />
                <h3 className="text-xl font-black text-gray-900 mb-3">{tip.title}</h3>
                <p className="text-gray-700 leading-relaxed">{tip.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Security Audit */}
        <div className="mt-16 bg-linear-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-3xl p-8">
          <div className="flex items-start gap-4">
            <Eye className="text-blue-600 shrink-0" size={32} />
            <div className="flex-1">
              <h3 className="text-2xl font-black text-gray-900 mb-3">Security Audit</h3>
              <p className="text-gray-700 mb-6">
                Run a comprehensive security audit to check your account status, connected devices, and security settings.
              </p>
              <button className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-all">
                Run Security Audit
              </button>
            </div>
          </div>
        </div>

        {/* Report Section */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-linear-to-br from-red-50 to-red-100 p-8 rounded-3xl border-2 border-red-200 text-center">
            <AlertTriangle className="mx-auto text-red-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">0</p>
            <p className="text-gray-700 font-bold">Security Issues</p>
          </div>

          <div className="bg-linear-to-br from-green-50 to-green-100 p-8 rounded-3xl border-2 border-green-200 text-center">
            <CheckCircle className="mx-auto text-green-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">{features.filter(f => f.status === 'enabled').length}</p>
            <p className="text-gray-700 font-bold">Features Enabled</p>
          </div>

          <div className="bg-linear-to-br from-blue-50 to-blue-100 p-8 rounded-3xl border-2 border-blue-200 text-center">
            <Shield className="mx-auto text-blue-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">Excellent</p>
            <p className="text-gray-700 font-bold">Security Score</p>
          </div>
        </div>

        {/* Warning */}
        <div className="mt-8 bg-red-50 border-2 border-red-200 rounded-3xl p-8">
          <p className="text-gray-700">
            <span className="font-bold text-red-600">Important:</span> Never share your password or authentication codes with anyone, not even EtherGuard support staff. We will never ask for your password.
          </p>
        </div>
      </div>
    </div>
  );
}
