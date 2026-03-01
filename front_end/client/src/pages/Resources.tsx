import { MessageSquare, Download, FileText, Video, Mail, Phone } from 'lucide-react';
import { useState } from 'react';

export default function Resources() {
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'guides' | 'videos' | 'faq'>('all');

  const resources = [
    {
      id: '1',
      category: 'guides',
      title: 'Getting Started with EtherGuard',
      description: 'Complete guide for setting up your monitoring system from unboxing to first deployment.',
      type: 'PDF Guide',
      icon: FileText,
      duration: '5 min read'
    },
    {
      id: '2',
      category: 'videos',
      title: 'Device Setup Tutorial',
      description: 'Step-by-step video showing how to unbox, power on, and connect your device.',
      type: 'Video',
      icon: Video,
      duration: '4:32'
    },
    {
      id: '3',
      category: 'guides',
      title: 'Understanding WiFi Settings',
      description: 'Learn about WiFi CSI technology and how it enables our privacy-first fall detection.',
      type: 'PDF Guide',
      icon: FileText,
      duration: '8 min read'
    },
    {
      id: '4',
      category: 'faq',
      title: 'FAQ - Frequently Asked Questions',
      description: 'Answers to common questions about EtherGuard and fall detection technology.',
      type: 'FAQ Document',
      icon: MessageSquare,
      duration: 'Quick Reference'
    },
    {
      id: '5',
      category: 'videos',
      title: 'Calibration Best Practices',
      description: 'Video guide on proper device calibration for optimal fall detection accuracy.',
      type: 'Video',
      icon: Video,
      duration: '5:45'
    },
    {
      id: '6',
      category: 'guides',
      title: 'Safety Tips for Seniors',
      description: 'Comprehensive guide on home safety modifications to prevent falls.',
      type: 'PDF Guide',
      icon: FileText,
      duration: '10 min read'
    },
  ];

  const faqs = [
    {
      question: 'How accurate is EtherGuard?',
      answer: 'EtherGuard uses advanced WiFi CSI technology to detect falls with 95%+ accuracy. The system is continuously learning and improving.'
    },
    {
      question: 'Is my data private?',
      answer: 'Yes, completely. We never collect video, audio, or images. Our WiFi sensing technology analyzes signal patterns only, ensuring complete privacy.'
    },
    {
      question: 'How long does calibration take?',
      answer: 'Initial calibration typically takes 3-5 minutes per room. This helps the system learn the unique characteristics of your environment.'
    },
    {
      question: 'What if the internet goes down?',
      answer: 'The device operates locally and stores data. When internet is restored, it will sync all events to the cloud.'
    },
    {
      question: 'Can I use multiple devices?',
      answer: 'Yes, you can deploy multiple units throughout your home. Each device can monitor independently or work together.'
    },
    {
      question: 'What is the warranty?',
      answer: 'All devices come with a 2-year manufacturer warranty covering defects and hardware failures.'
    },
  ];

  const contactMethods = [
    {
      icon: Mail,
      title: 'Email Support',
      description: 'support@etherguard.io',
      responseTime: 'Within 24 hours',
      color: 'from-blue-50 to-blue-100',
      borderColor: 'border-blue-200',
      accentColor: 'text-blue-600'
    },
    {
      icon: Phone,
      title: 'Phone Support',
      description: '1-800-GUARD-FALL',
      responseTime: 'Mon-Fri, 9AM-5PM',
      color: 'from-green-50 to-green-100',
      borderColor: 'border-green-200',
      accentColor: 'text-green-600'
    },
    {
      icon: MessageSquare,
      title: 'Live Chat',
      description: 'Available on our website',
      responseTime: 'Real-time assistance',
      color: 'from-purple-50 to-purple-100',
      borderColor: 'border-purple-200',
      accentColor: 'text-purple-600'
    },
  ];

  const filteredResources = resources.filter(resource =>
    selectedCategory === 'all' || resource.category === selectedCategory
  );

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Help & Resources</h1>
          <p className="text-xl text-gray-600">Everything you need to get the most out of EtherGuard</p>
        </div>

        {/* Knowledge Base Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-black text-gray-900 mb-8">Knowledge Base</h2>

          {/* Filter Tabs */}
          <div className="flex gap-3 mb-8 overflow-x-auto pb-2">
            {[
              { value: 'all' as const, label: 'All Resources' },
              { value: 'guides' as const, label: 'Guides' },
              { value: 'videos' as const, label: 'Videos' },
              { value: 'faq' as const, label: 'FAQ' },
            ].map(tab => (
              <button
                key={tab.value}
                onClick={() => setSelectedCategory(tab.value)}
                className={`px-6 py-3 rounded-xl font-bold whitespace-nowrap transition-all ${
                  selectedCategory === tab.value
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Resources Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredResources.map(resource => {
              const Icon = resource.icon;
              return (
                <div
                  key={resource.id}
                  className="bg-linear-to-br from-gray-50 to-white border-2 border-gray-200 rounded-3xl p-8 hover:shadow-lg transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-4">
                    <Icon className="text-red-600 group-hover:scale-110 transition-transform" size={32} />
                    <span className="px-3 py-1 bg-red-100 text-red-600 text-xs font-bold rounded-full">
                      {resource.type}
                    </span>
                  </div>

                  <h3 className="text-xl font-black text-gray-900 mb-3">{resource.title}</h3>
                  <p className="text-gray-600 mb-6">{resource.description}</p>

                  <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                    <span className="text-sm text-gray-500 font-bold">{resource.duration}</span>
                    <button className="px-4 py-2 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 transition-all">
                      <Download size={16} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-black text-gray-900 mb-8">Frequently Asked Questions</h2>

          <div className="space-y-4">
            {faqs.map((faq, idx) => (
              <details
                key={idx}
                className="group bg-linear-to-br from-gray-50 to-white border-2 border-gray-200 rounded-3xl p-8 cursor-pointer transition-all hover:border-red-200 hover:shadow-lg"
              >
                <summary className="flex items-center justify-between font-bold text-gray-900 text-lg group-open:text-red-600">
                  {faq.question}
                  <span className="transition-transform group-open:rotate-180">▼</span>
                </summary>
                <p className="text-gray-700 mt-4 leading-relaxed">{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>

        {/* Contact Support */}
        <div className="mb-16">
          <h2 className="text-3xl font-black text-gray-900 mb-8">Get in Touch</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {contactMethods.map((method, idx) => {
              const Icon = method.icon;
              return (
                <div
                  key={idx}
                  className={`bg-linear-to-br ${method.color} border-2 ${method.borderColor} rounded-3xl p-8 text-center`}
                >
                  <Icon className={`${method.accentColor} mx-auto mb-4`} size={40} />
                  <h3 className="text-xl font-black text-gray-900 mb-2">{method.title}</h3>
                  <p className={`${method.accentColor} font-bold mb-3`}>{method.description}</p>
                  <p className="text-gray-600 text-sm">{method.responseTime}</p>
                  <button className={`w-full mt-6 px-4 py-3 ${method.accentColor.replace('text-', 'bg-')} text-white font-bold rounded-xl hover:opacity-80 transition-all`}>
                    Contact Us
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Documentation */}
        <div className="bg-linear-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-3xl p-8">
          <div className="flex items-start gap-4">
            <FileText className="text-blue-600 shrink-0" size={32} />
            <div className="flex-1">
              <h3 className="text-2xl font-black text-gray-900 mb-3">Technical Documentation</h3>
              <p className="text-gray-700 mb-6">
                Access our complete technical documentation, API references, and developer guides.
              </p>
              <button className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-all">
                View Documentation
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
