import { Heart, Activity, Apple, Droplet, Moon, Users } from 'lucide-react';

export default function HealthTips() {
  const tips = [
    {
      icon: Heart,
      title: 'Heart Health',
      description: 'Maintain a healthy heart with regular exercise and proper diet.',
      tips: ['Walk 30 minutes daily', 'Reduce sodium intake', 'Manage stress levels', 'Regular checkups'],
      color: 'from-red-50 to-red-100',
      borderColor: 'border-red-200',
      accentColor: 'text-red-600'
    },
    {
      icon: Activity,
      title: 'Daily Movement',
      description: 'Stay active to maintain strength and balance.',
      tips: ['Gentle stretching', 'Balance exercises', 'Tai Chi or yoga', 'Strength training'],
      color: 'from-blue-50 to-blue-100',
      borderColor: 'border-blue-200',
      accentColor: 'text-blue-600'
    },
    {
      icon: Apple,
      title: 'Nutrition',
      description: 'A balanced diet is essential for overall wellness.',
      tips: ['Fruits & vegetables', 'Lean proteins', 'Whole grains', 'Stay hydrated'],
      color: 'from-green-50 to-green-100',
      borderColor: 'border-green-200',
      accentColor: 'text-green-600'
    },
    {
      icon: Moon,
      title: 'Sleep Quality',
      description: 'Quality sleep improves health and recovery.',
      tips: ['7-8 hours nightly', 'Consistent schedule', 'Dark, cool room', 'Limit screen time'],
      color: 'from-purple-50 to-purple-100',
      borderColor: 'border-purple-200',
      accentColor: 'text-purple-600'
    },
    {
      icon: Droplet,
      title: 'Hydration',
      description: 'Proper hydration is vital for all body functions.',
      tips: ['6-8 glasses daily', 'Drink with meals', 'Morning water first', 'Monitor urine color'],
      color: 'from-cyan-50 to-cyan-100',
      borderColor: 'border-cyan-200',
      accentColor: 'text-cyan-600'
    },
    {
      icon: Users,
      title: 'Social Connection',
      description: 'Stay connected with family and friends.',
      tips: ['Daily calls or visits', 'Join group activities', 'Attend events', 'Volunteer'],
      color: 'from-amber-50 to-amber-100',
      borderColor: 'border-amber-200',
      accentColor: 'text-amber-600'
    },
  ];

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Health & Wellness</h1>
          <p className="text-xl text-gray-600">Essential tips for a healthier, happier life</p>
        </div>

        {/* Tips Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {tips.map((tip, idx) => {
            const Icon = tip.icon;
            return (
              <div 
                key={idx}
                className={`bg-linear-to-br ${tip.color} p-8 rounded-3xl border-2 ${tip.borderColor} shadow-lg hover:shadow-xl transition-all`}
              >
                <div className="flex items-center gap-3 mb-4">
                  <Icon className={`${tip.accentColor}`} size={32} />
                  <h3 className="text-2xl font-black text-gray-900">{tip.title}</h3>
                </div>
                
                <p className="text-gray-700 font-medium mb-6">{tip.description}</p>
                
                <div className="space-y-3 pt-6 border-t-2 border-white/50">
                  {tip.tips.map((item, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full ${tip.accentColor} mt-2 shrink-0`}></div>
                      <p className="text-gray-700 text-sm">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Disclaimer */}
        <div className="mt-16 bg-blue-50 border-2 border-blue-200 rounded-3xl p-8">
          <p className="text-gray-700 text-center">
            <span className="font-bold text-blue-600">Note:</span> These are general wellness suggestions. Always consult with healthcare professionals before starting new health routines.
          </p>
        </div>
      </div>
    </div>
  );
}
