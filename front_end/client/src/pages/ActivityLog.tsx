import { AlertTriangle, CheckCircle, Clock, Download, Filter } from 'lucide-react';
import { useState } from 'react';

interface Activity {
  id: string;
  type: 'fall' | 'normal_movement' | 'system_check';
  description: string;
  timestamp: string;
  severity: 'critical' | 'info';
  patient: string;
  location: string;
}

export default function ActivityLog() {
  const [activities] = useState<Activity[]>([
    {
      id: '1',
      type: 'fall',
      description: 'Fall detected',
      timestamp: '2026-03-01 14:32',
      severity: 'critical',
      patient: 'John Marston',
      location: 'Living Room'
    },
    {
      id: '2',
      type: 'normal_movement',
      description: 'Normal movement detected',
      timestamp: '2026-03-01 13:15',
      severity: 'info',
      patient: 'Arthur Morgan',
      location: 'Bedroom'
    },
    {
      id: '3',
      type: 'system_check',
      description: 'Automatic system health check passed',
      timestamp: '2026-03-01 12:00',
      severity: 'info',
      patient: 'System',
      location: 'All Units'
    },
    {
      id: '4',
      type: 'fall',
      description: 'Fall detected',
      timestamp: '2026-02-28 19:45',
      severity: 'critical',
      patient: 'John Marston',
      location: 'Bathroom'
    },
    {
      id: '5',
      type: 'normal_movement',
      description: 'Normal activity in home',
      timestamp: '2026-02-28 15:30',
      severity: 'info',
      patient: 'Arthur Morgan',
      location: 'Kitchen'
    },
  ]);

  const [filterType, setFilterType] = useState<'all' | 'fall' | 'info'>('all');

  const filteredActivities = activities.filter(activity => {
    if (filterType === 'all') return true;
    if (filterType === 'fall') return activity.severity === 'critical';
    if (filterType === 'info') return activity.severity === 'info';
    return true;
  });

  const getIcon = (_type: string, severity: string) => {
    if (severity === 'critical') {
      return <AlertTriangle className="text-red-600" size={24} />;
    }
    return <CheckCircle className="text-green-600" size={24} />;
  };

  const getBackgroundColor = (severity: string) => {
    return severity === 'critical' ? 'bg-red-50' : 'bg-green-50';
  };

  const getBorderColor = (severity: string) => {
    return severity === 'critical' ? 'border-red-200' : 'border-green-200';
  };

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Activity Log</h1>
          <p className="text-xl text-gray-600">Track all monitoring events and system activities</p>
        </div>

        {/* Controls */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          {/* Filter */}
          <div className="flex-1 bg-gray-50 border-2 border-gray-200 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Filter size={20} className="text-gray-600" />
              <span className="font-bold text-gray-900">Filter:</span>
            </div>
            <div className="flex gap-2">
              {[
                { value: 'all' as const, label: 'All Events' },
                { value: 'fall' as const, label: 'Falls Only' },
                { value: 'info' as const, label: 'System Events' },
              ].map(option => (
                <button
                  key={option.value}
                  onClick={() => setFilterType(option.value)}
                  className={`px-4 py-2 rounded-xl font-bold transition-all ${
                    filterType === option.value
                      ? 'bg-red-600 text-white'
                      : 'bg-white border-2 border-gray-300 text-gray-900 hover:border-red-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Export */}
          <button className="px-6 py-4 bg-blue-600 text-white font-bold rounded-2xl hover:bg-blue-700 transition-all flex items-center justify-center gap-2 shadow-lg">
            <Download size={20} />
            Export Report
          </button>
        </div>

        {/* Activity List */}
        <div className="space-y-4">
          {filteredActivities.length === 0 ? (
            <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-3xl p-12 text-center">
              <Clock className="mx-auto text-gray-400 mb-4" size={48} />
              <p className="text-gray-600 text-lg">No activities found for this filter.</p>
            </div>
          ) : (
            filteredActivities.map((activity) => (
              <div
                key={activity.id}
                className={`p-6 rounded-3xl border-2 transition-all hover:shadow-lg ${getBackgroundColor(activity.severity)} ${getBorderColor(activity.severity)}`}
              >
                <div className="flex items-start gap-4">
                  {/* Icon */}
                  <div className="shrink-0 pt-1">
                    {getIcon(activity.type, activity.severity)}
                  </div>

                  {/* Content */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-xl font-black text-gray-900">{activity.description}</h3>
                      {activity.severity === 'critical' && (
                        <span className="px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full">
                          CRITICAL
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-white/50">
                      <div>
                        <p className="text-xs font-bold text-gray-500 uppercase">Patient</p>
                        <p className="text-gray-900 font-bold">{activity.patient}</p>
                      </div>
                      <div>
                        <p className="text-xs font-bold text-gray-500 uppercase">Location</p>
                        <p className="text-gray-900 font-bold">{activity.location}</p>
                      </div>
                      <div className="col-span-2">
                        <p className="text-xs font-bold text-gray-500 uppercase">Time</p>
                        <div className="flex items-center gap-2 text-gray-900 font-bold">
                          <Clock size={16} />
                          {activity.timestamp}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Summary Stats */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-linear-to-br from-red-50 to-red-100 p-8 rounded-3xl border-2 border-red-200 text-center">
            <AlertTriangle className="mx-auto text-red-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">
              {activities.filter(a => a.severity === 'critical').length}
            </p>
            <p className="text-gray-700 font-bold">Falls Detected</p>
          </div>

          <div className="bg-linear-to-br from-green-50 to-green-100 p-8 rounded-3xl border-2 border-green-200 text-center">
            <CheckCircle className="mx-auto text-green-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">
              {activities.filter(a => a.severity === 'info').length}
            </p>
            <p className="text-gray-700 font-bold">System Events</p>
          </div>

          <div className="bg-linear-to-br from-blue-50 to-blue-100 p-8 rounded-3xl border-2 border-blue-200 text-center">
            <Clock className="mx-auto text-blue-600 mb-3" size={40} />
            <p className="text-3xl font-black text-gray-900">{activities.length}</p>
            <p className="text-gray-700 font-bold">Total Events</p>
          </div>
        </div>
      </div>
    </div>
  );
}
