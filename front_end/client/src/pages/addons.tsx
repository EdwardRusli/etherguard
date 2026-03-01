import { Zap, Bell, Smartphone, Users, BarChart3, Clock, Download, Star, CheckCircle } from 'lucide-react';
import { useState } from 'react';

import type { LucideIcon } from 'lucide-react';

interface Addon {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  category: string;
  status: 'installed' | 'available';
  pricing: 'free' | 'premium';
  rating: number;
  downloads: number;
}

export default function Addons() {
  const [addons, _setAddons] = useState<Addon[]>([
    {
      id: '1',
      name: 'Advanced Notifications',
      description: 'Get detailed alerts with custom notification rules and escalation procedures.',
      icon: Bell,
      category: 'Notifications',
      status: 'installed',
      pricing: 'free',
      rating: 4.8,
      downloads: 2340
    },
    {
      id: '2',
      name: 'Analytics Dashboard',
      description: 'Detailed insights into fall patterns, movement trends, and health metrics over time.',
      icon: BarChart3,
      category: 'Analytics',
      status: 'available',
      pricing: 'premium',
      rating: 4.9,
      downloads: 1890
    },
    {
      id: '3',
      name: 'Multi-Device Sync',
      description: 'Seamlessly sync data across multiple EtherGuard units and devices.',
      icon: Smartphone,
      category: 'Advanced',
      status: 'installed',
      pricing: 'free',
      rating: 4.7,
      downloads: 3120
    },
    {
      id: '4',
      name: 'Caregiver Network',
      description: 'Invite multiple caregivers and manage their access levels and permissions.',
      icon: Users,
      category: 'Collaboration',
      status: 'available',
      pricing: 'free',
      rating: 4.6,
      downloads: 2560
    },
    {
      id: '5',
      name: 'Smart Schedules',
      description: 'Create schedules for different monitoring modes and activity patterns.',
      icon: Clock,
      category: 'Automation',
      status: 'installed',
      pricing: 'free',
      rating: 4.5,
      downloads: 1920
    },
    {
      id: '6',
      name: 'Performance Report Generator',
      description: 'Automatically generate weekly and monthly performance reports for health professionals.',
      icon: BarChart3,
      category: 'Reports',
      status: 'available',
      pricing: 'premium',
      rating: 4.7,
      downloads: 890
    },
    {
      id: '7',
      name: 'Emergency Integration',
      description: 'Direct integration with local emergency services for automatic dispatch.',
      icon: Zap,
      category: 'Emergency',
      status: 'available',
      pricing: 'premium',
      rating: 4.9,
      downloads: 1240
    },
    {
      id: '8',
      name: 'Voice Commands',
      description: 'Control your system with voice commands for hands-free operation.',
      icon: Smartphone,
      category: 'Accessibility',
      status: 'available',
      pricing: 'premium',
      rating: 4.4,
      downloads: 1450
    },
  ]);

  const [filter, setFilter] = useState<'all' | 'installed' | 'available'>('all');

  const filteredAddons = addons.filter(addon => {
    if (filter === 'all') return true;
    return addon.status === filter;
  });

  const handleInstall = (id: string) => {
    _setAddons(addons.map(addon =>
      addon.id === id ? { ...addon, status: 'installed' as const } : addon
    ));
  };



  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Add-ons & Extensions</h1>
          <p className="text-xl text-gray-600">Enhance your EtherGuard system with powerful add-ons</p>
        </div>

        {/* Filter Section */}
        <div className="bg-gray-50 border-2 border-gray-200 rounded-3xl p-6 mb-12">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <h3 className="font-bold text-gray-900 mb-3">Filter by Status:</h3>
              <div className="flex gap-2 flex-wrap">
                {[
                  { value: 'all' as const, label: 'All Add-ons', count: addons.length },
                  { value: 'installed' as const, label: 'Installed', count: addons.filter(a => a.status === 'installed').length },
                  { value: 'available' as const, label: 'Available', count: addons.filter(a => a.status === 'available').length },
                ].map(option => (
                  <button
                    key={option.value}
                    onClick={() => setFilter(option.value)}
                    className={`px-4 py-2 rounded-xl font-bold transition-all ${
                      filter === option.value
                        ? 'bg-red-600 text-white'
                        : 'bg-white border-2 border-gray-300 text-gray-900 hover:border-red-300'
                    }`}
                  >
                    {option.label} ({option.count})
                  </button>
                ))}
              </div>
            </div>

            {/* Search (optional) */}
            <input
              type="text"
              placeholder="Search add-ons..."
              className="px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500 w-full md:w-64"
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          <div className="bg-linear-to-br from-blue-50 to-blue-100 p-6 rounded-3xl border-2 border-blue-200 text-center">
            <Zap className="mx-auto text-blue-600 mb-2" size={32} />
            <p className="text-2xl font-black text-gray-900">{addons.length}</p>
            <p className="text-gray-700 font-bold">Total Add-ons</p>
          </div>
          <div className="bg-linear-to-br from-green-50 to-green-100 p-6 rounded-3xl border-2 border-green-200 text-center">
            <CheckCircle className="mx-auto text-green-600 mb-2" size={32} />
            <p className="text-2xl font-black text-gray-900">{addons.filter(a => a.status === 'installed').length}</p>
            <p className="text-gray-700 font-bold">Installed</p>
          </div>
          <div className="bg-linear-to-br from-purple-50 to-purple-100 p-6 rounded-3xl border-2 border-purple-200 text-center">
            <Download className="mx-auto text-purple-600 mb-2" size={32} />
            <p className="text-2xl font-black text-gray-900">{addons.filter(a => a.pricing === 'free').length}</p>
            <p className="text-gray-700 font-bold">Free</p>
          </div>
          <div className="bg-linear-to-br from-orange-50 to-orange-100 p-6 rounded-3xl border-2 border-orange-200 text-center">
            <Star className="mx-auto text-orange-600 mb-2" size={32} />
            <p className="text-2xl font-black text-gray-900">4.7★</p>
            <p className="text-gray-700 font-bold">Avg Rating</p>
          </div>
        </div>

        {/* Add-ons Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {filteredAddons.map((addon) => {
            const Icon = addon.icon;
            return (
              <div
                key={addon.id}
                className={`p-8 rounded-3xl border-2 transition-all shadow-lg hover:shadow-xl ${
                  addon.status === 'installed'
                    ? 'bg-linear-to-br from-green-50 to-green-100 border-green-200'
                    : 'bg-linear-to-br from-white to-gray-50 border-gray-200'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <Icon className={addon.status === 'installed' ? 'text-green-600' : 'text-red-600'} size={40} />
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      addon.status === 'installed'
                        ? 'bg-green-600 text-white'
                        : 'bg-gray-300 text-gray-900'
                    }`}>
                      {addon.status === 'installed' ? '✓ Installed' : 'Available'}
                    </span>
                    <div className="mt-2 flex items-center gap-1 text-orange-500 font-bold">
                      <Star size={14} fill="currentColor" />
                      {addon.rating}
                    </div>
                  </div>
                </div>

                {/* Content */}
                <h3 className="text-xl font-black text-gray-900 mb-2">{addon.name}</h3>
                <p className="text-gray-700 text-sm mb-6">{addon.description}</p>

                {/* Meta */}
                <div className="pt-6 border-t border-white/50 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 font-medium">Category</span>
                    <span className={`px-3 py-1 rounded-lg text-xs font-bold ${
                      addon.category === 'Notifications' ? 'bg-blue-100 text-blue-600' :
                      addon.category === 'Analytics' ? 'bg-purple-100 text-purple-600' :
                      addon.category === 'Advanced' ? 'bg-cyan-100 text-cyan-600' :
                      addon.category === 'Collaboration' ? 'bg-pink-100 text-pink-600' :
                      addon.category === 'Automation' ? 'bg-yellow-100 text-yellow-600' :
                      addon.category === 'Reports' ? 'bg-green-100 text-green-600' :
                      addon.category === 'Emergency' ? 'bg-red-100 text-red-600' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {addon.category}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 font-medium">Downloads</span>
                    <span className="font-bold text-gray-900">{addon.downloads.toLocaleString()}</span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 font-medium">Price</span>
                    <span className={`font-bold ${addon.pricing === 'free' ? 'text-green-600' : 'text-orange-600'}`}>
                      {addon.pricing === 'free' ? 'Free' : 'Premium'}
                    </span>
                  </div>
                </div>

                {/* Install Button */}
                <button
                  onClick={() => handleInstall(addon.id)}
                  disabled={addon.status === 'installed'}
                  className={`w-full mt-6 px-4 py-3 rounded-xl font-bold transition-all ${
                    addon.status === 'installed'
                      ? 'bg-green-600 text-white cursor-not-allowed'
                      : 'bg-red-600 text-white hover:bg-red-700'
                  }`}
                >
                  {addon.status === 'installed' ? '✓ Installed' : 'Install'}
                </button>
              </div>
            );
          })}
        </div>

        {/* Coming Soon */}
        <div className="mt-16 bg-linear-to-br from-purple-50 to-purple-100 border-2 border-purple-200 rounded-3xl p-8">
          <div className="text-center">
            <Zap className="mx-auto text-purple-600 mb-4" size={48} />
            <h3 className="text-2xl font-black text-gray-900 mb-2">More Coming Soon!</h3>
            <p className="text-gray-700 mb-6">
              We're constantly developing new add-ons and features. Sign up to get notified when new add-ons are released.
            </p>
            <button className="px-6 py-3 bg-purple-600 text-white font-bold rounded-xl hover:bg-purple-700 transition-all">
              Notify Me
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
