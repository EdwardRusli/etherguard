import { Phone, Plus, Trash2, Edit2, AlertCircle } from 'lucide-react';
import { useState } from 'react';

interface Contact {
  id: string;
  name: string;
  relation: string;
  phone: string;
  isPrimary: boolean;
}

export default function EmergencyContacts() {
  const [contacts, setContacts] = useState<Contact[]>([
    { id: '1', name: 'Sarah Johnson', relation: 'Daughter', phone: '(555) 123-4567', isPrimary: true },
    { id: '2', name: 'Dr. James Smith', relation: 'Primary Doctor', phone: '(555) 987-6543', isPrimary: false },
  ]);

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', relation: '', phone: '' });

  const handleAddContact = () => {
    if (formData.name && formData.relation && formData.phone) {
      setContacts([
        ...contacts,
        {
          id: Date.now().toString(),
          ...formData,
          isPrimary: contacts.length === 0,
        },
      ]);
      setFormData({ name: '', relation: '', phone: '' });
      setShowForm(false);
    }
  };

  const handleDeleteContact = (id: string) => {
    setContacts(contacts.filter(c => c.id !== id));
  };

  const handleSetPrimary = (id: string) => {
    setContacts(contacts.map(c => ({ ...c, isPrimary: c.id === id })));
  };

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">Emergency Contacts</h1>
          <p className="text-xl text-gray-600">Manage trusted contacts for emergencies</p>
        </div>

        {/* Alert Box */}
        <div className="bg-red-50 border-2 border-red-200 rounded-3xl p-6 mb-8 flex items-start gap-4">
          <AlertCircle className="text-red-600 shrink-0" size={24} />
          <div>
            <p className="font-bold text-red-600">Important</p>
            <p className="text-gray-700">Always keep this list updated with accurate contact information. These contacts will be notified in case of emergencies detected by EtherGuard.</p>
          </div>
        </div>

        {/* Add Contact Button */}
        <button
          onClick={() => setShowForm(!showForm)}
          className="w-full md:w-auto px-6 py-3 bg-red-600 text-white font-bold rounded-2xl hover:bg-red-700 transition-all mb-8 flex items-center justify-center gap-2 shadow-lg"
        >
          <Plus size={20} />
          Add Contact
        </button>

        {/* Add Contact Form */}
        {showForm && (
          <div className="bg-gray-50 border-2 border-gray-200 rounded-3xl p-8 mb-8">
            <h3 className="text-2xl font-black text-gray-900 mb-6">Add New Contact</h3>
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Full Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
              />
              <input
                type="text"
                placeholder="Relation (e.g., Daughter, Doctor)"
                value={formData.relation}
                onChange={(e) => setFormData({ ...formData, relation: e.target.value })}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
              />
              <input
                type="tel"
                placeholder="Phone Number"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
              />
              <div className="flex gap-3">
                <button
                  onClick={handleAddContact}
                  className="flex-1 px-4 py-3 bg-green-600 text-white font-bold rounded-xl hover:bg-green-700 transition-all"
                >
                  Save Contact
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="flex-1 px-4 py-3 bg-gray-400 text-white font-bold rounded-xl hover:bg-gray-500 transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Contacts List */}
        <div className="space-y-4">
          <h2 className="text-2xl font-black text-gray-900 mb-6">Your Contacts</h2>
          
          {contacts.length === 0 ? (
            <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-3xl p-12 text-center">
              <Phone className="mx-auto text-gray-400 mb-4" size={48} />
              <p className="text-gray-600 text-lg">No contacts added yet. Add your first emergency contact above.</p>
            </div>
          ) : (
            contacts.map((contact) => (
              <div
                key={contact.id}
                className={`p-6 rounded-3xl border-2 transition-all shadow-md hover:shadow-lg ${
                  contact.isPrimary
                    ? 'bg-red-50 border-red-300'
                    : 'bg-white border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-black text-gray-900">{contact.name}</h3>
                      {contact.isPrimary && (
                        <span className="px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full">
                          PRIMARY
                        </span>
                      )}
                    </div>
                    <p className="text-gray-600 font-medium">{contact.relation}</p>
                    <div className="flex items-center gap-2 text-red-600 font-bold mt-3">
                      <Phone size={16} />
                      {contact.phone}
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    {!contact.isPrimary && (
                      <button
                        onClick={() => handleSetPrimary(contact.id)}
                        className="p-3 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200 transition-all"
                        title="Set as primary"
                      >
                        <Edit2 size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteContact(contact.id)}
                      className="p-3 bg-red-100 text-red-600 rounded-xl hover:bg-red-200 transition-all"
                      title="Delete contact"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
