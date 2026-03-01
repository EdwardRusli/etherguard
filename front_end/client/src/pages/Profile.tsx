import { Mail, Phone, MessageCircle, Facebook, Camera, Save, X } from 'lucide-react';
import { useState } from 'react';

interface UserProfile {
  name: string;
  email: string;
  phone: string;
  telegramHandle: string;
  profilePicture: string;
  preferredNotifications: {
    whatsapp: boolean;
    sms: boolean;
    email: boolean;
    telegram: boolean;
  };
}

export default function Profile({ userEmail }: { userEmail: string }) {
  const initialProfile: UserProfile = {
    name: 'John Smith',
    email: userEmail,
    phone: '(555) 123-4567',
    telegramHandle: '@johnsmith',
    profilePicture: 'https://api.dicebear.com/7.x/avataaars/svg?seed=John',
    preferredNotifications: {
      whatsapp: true,
      sms: false,
      email: true,
      telegram: true,
    },
  };

  const [profile, setProfile] = useState<UserProfile>(initialProfile);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState<UserProfile>(initialProfile);
  const [previewImage, setPreviewImage] = useState(initialProfile.profilePicture);

  const handleInputChange = (field: keyof Omit<UserProfile, 'preferredNotifications' | 'profilePicture'>, value: string) => {
    // Prevent email field from being edited
    if (field === 'email') return;
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleNotificationChange = (channel: keyof UserProfile['preferredNotifications']) => {
    setFormData(prev => ({
      ...prev,
      preferredNotifications: {
        ...prev.preferredNotifications,
        [channel]: !prev.preferredNotifications[channel],
      },
    }));
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviewImage(reader.result as string);
        setFormData(prev => ({ ...prev, profilePicture: reader.result as string }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = () => {
    setProfile(formData);
    setEditMode(false);
  };

  const handleCancel = () => {
    setFormData(profile);
    setPreviewImage(profile.profilePicture);
    setEditMode(false);
  };

  return (
    <div className="min-h-screen bg-white py-12 px-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">My Profile</h1>
          <p className="text-xl text-gray-600">Manage your account settings and preferences</p>
        </div>

        {/* Profile Card */}
        <div className="bg-linear-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-3xl p-8 mb-8">
          <div className="flex flex-col md:flex-row items-center gap-8">
            {/* Profile Picture */}
            <div className="relative">
              <img
                src={editMode ? previewImage : profile.profilePicture}
                alt="Profile"
                className="w-32 h-32 rounded-full border-4 border-blue-300 object-cover shadow-lg"
              />
              {editMode && (
                <label className="absolute bottom-0 right-0 bg-red-600 text-white p-3 rounded-full cursor-pointer hover:bg-red-700 transition shadow-lg">
                  <Camera size={20} />
                  <input type="file" className="hidden" accept="image/*" onChange={handleImageChange} />
                </label>
              )}
            </div>

            {/* Profile Info */}
            <div className="flex-1 text-center md:text-left">
              <h2 className="text-3xl font-black text-gray-900 mb-2">{profile.name}</h2>
              <p className="text-gray-600 font-medium mb-4">{profile.email}</p>
              <button
                onClick={() => {
                  setEditMode(!editMode);
                  setFormData(profile);
                  setPreviewImage(profile.profilePicture);
                }}
                className={`px-6 py-2 rounded-xl font-bold transition ${
                  editMode
                    ? 'bg-gray-400 text-white'
                    : 'bg-red-600 text-white hover:bg-red-700'
                }`}
              >
                {editMode ? 'Cancel' : 'Edit Profile'}
              </button>
            </div>
          </div>
        </div>

        {/* Edit Form */}
        {editMode && (
          <div className="bg-gray-50 border-2 border-gray-200 rounded-3xl p-8 mb-8">
            <h3 className="text-2xl font-black text-gray-900 mb-6">Edit Your Information</h3>

            <div className="space-y-6">
              {/* Name */}
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">Full Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
                />
              </div>

              {/* Email */}
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">Email Address</label>
                <p className="text-sm text-gray-500 mb-2 italic">This email is linked to your account and cannot be changed</p>
                <input
                  type="email"
                  value={formData.email}
                  disabled
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl bg-gray-100 text-gray-600 cursor-not-allowed"
                />
              </div>

              {/* Phone */}
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">Phone Number</label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
                />
              </div>

              {/* Telegram */}
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">Telegram Handle</label>
                <input
                  type="text"
                  value={formData.telegramHandle}
                  onChange={(e) => handleInputChange('telegramHandle', e.target.value)}
                  placeholder="@yourhandle"
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-red-500"
                />
              </div>
            </div>

            {/* Notification Preferences */}
            <div className="mt-8 pt-8 border-t-2 border-gray-300">
              <h4 className="text-xl font-black text-gray-900 mb-4">Preferred Notification Channels</h4>
              <p className="text-gray-600 text-sm mb-6">Select how you want to receive alerts about fall detection and monitoring events:</p>

              <div className="space-y-3">
                {[
                  { key: 'whatsapp', label: 'WhatsApp', icon: '💬', color: 'from-green-50 to-green-100 border-green-200' },
                  { key: 'sms', label: 'SMS Message', icon: '📱', color: 'from-blue-50 to-blue-100 border-blue-200' },
                  { key: 'email', label: 'Email', icon: '📧', color: 'from-purple-50 to-purple-100 border-purple-200' },
                  { key: 'telegram', label: 'Telegram', icon: '📨', color: 'from-cyan-50 to-cyan-100 border-cyan-200' },
                ].map(channel => (
                  <label
                    key={channel.key}
                    className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition ${
                      formData.preferredNotifications[channel.key as keyof typeof formData.preferredNotifications]
                        ? channel.color
                        : 'bg-white border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={formData.preferredNotifications[channel.key as keyof typeof formData.preferredNotifications]}
                      onChange={() => handleNotificationChange(channel.key as keyof typeof formData.preferredNotifications)}
                      className="w-5 h-5 cursor-pointer"
                    />
                    <span className="text-2xl">{channel.icon}</span>
                    <div className="flex-1">
                      <p className="font-bold text-gray-900">{channel.label}</p>
                      <p className="text-sm text-gray-600">
                        {channel.key === 'whatsapp' && 'Receive alerts via WhatsApp'}
                        {channel.key === 'sms' && 'Receive alerts via SMS/Text message'}
                        {channel.key === 'email' && 'Receive alerts via email'}
                        {channel.key === 'telegram' && 'Receive alerts via Telegram'}
                      </p>
                    </div>
                    {formData.preferredNotifications[channel.key as keyof typeof formData.preferredNotifications] && (
                      <span className="text-green-600 font-black">✓</span>
                    )}
                  </label>
                ))}
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-4 mt-8">
              <button
                onClick={handleSave}
                className="flex-1 px-6 py-3 bg-green-600 text-white font-bold rounded-xl hover:bg-green-700 transition flex items-center justify-center gap-2 shadow-lg"
              >
                <Save size={20} />
                Save Changes
              </button>
              <button
                onClick={handleCancel}
                className="flex-1 px-6 py-3 bg-gray-400 text-white font-bold rounded-xl hover:bg-gray-500 transition flex items-center justify-center gap-2"
              >
                <X size={20} />
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Display Info (when not editing) */}
        {!editMode && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Contact Information */}
            <div className="bg-linear-to-br from-orange-50 to-orange-100 p-6 rounded-3xl border-2 border-orange-200">
              <div className="flex items-center gap-3 mb-4">
                <Mail className="text-orange-600" size={24} />
                <h3 className="text-lg font-black text-gray-900">Email</h3>
              </div>
              <p className="text-gray-700 font-medium">{profile.email}</p>
            </div>

            <div className="bg-linear-to-br from-cyan-50 to-cyan-100 p-6 rounded-3xl border-2 border-cyan-200">
              <div className="flex items-center gap-3 mb-4">
                <Phone className="text-cyan-600" size={24} />
                <h3 className="text-lg font-black text-gray-900">Phone</h3>
              </div>
              <p className="text-gray-700 font-medium">{profile.phone}</p>
            </div>

            <div className="bg-linear-to-br from-pink-50 to-pink-100 p-6 rounded-3xl border-2 border-pink-200">
              <div className="flex items-center gap-3 mb-4">
                <MessageCircle className="text-pink-600" size={24} />
                <h3 className="text-lg font-black text-gray-900">Telegram</h3>
              </div>
              <p className="text-gray-700 font-medium">{profile.telegramHandle}</p>
            </div>

            {/* Notification Preferences Summary */}
            <div className="bg-linear-to-br from-green-50 to-green-100 p-6 rounded-3xl border-2 border-green-200">
              <div className="flex items-center gap-3 mb-4">
                <Facebook className="text-green-600" size={24} />
                <h3 className="text-lg font-black text-gray-900">Notifications</h3>
              </div>
              <div className="space-y-2">
                {profile.preferredNotifications.whatsapp && <p className="text-gray-700 text-sm">✓ WhatsApp</p>}
                {profile.preferredNotifications.sms && <p className="text-gray-700 text-sm">✓ SMS</p>}
                {profile.preferredNotifications.email && <p className="text-gray-700 text-sm">✓ Email</p>}
                {profile.preferredNotifications.telegram && <p className="text-gray-700 text-sm">✓ Telegram</p>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
