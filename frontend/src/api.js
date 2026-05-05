import axios from 'axios';

export const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add interceptor to include password in all axios requests
api.interceptors.request.use((config) => {
  const pwd = localStorage.getItem('protocolist_password');
  if (pwd) {
    config.headers['X-App-Password'] = pwd;
  }
  return config;
});

export const uploadMeeting = async (file, email, provider, existingFileId = null, forceCpu = false, sessionId = null, sendEmail = true) => {
  const formData = new FormData();
  
  if (file) {
    formData.append('file', file, file.name || 'blob');
  }
  
  if (email) formData.append('email', email);
  if (provider) formData.append('provider', provider);
  if (existingFileId) formData.append('existing_file_id', existingFileId);
  if (forceCpu) formData.append('force_cpu', 'true');
  if (sessionId) formData.append('session_id', sessionId);
  formData.append('send_email', sendEmail ? 'true' : 'false');

  const url = `${API_BASE_URL}/process-meeting`;
  const pwd = localStorage.getItem('protocolist_password');

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    headers: pwd ? { 'X-App-Password': pwd } : {},
    // Note: Do NOT set Content-Type header, fetch will handle it with boundary
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || 'Upload failed');
    error.response = { data: errorData };
    throw error;
  }

  return response.json();
};

export const getProcessingStatus = async (fileId) => {
  const response = await api.get(`/status/${fileId}`);
  return response.data;
};

export const getSystemInfo = async () => {
  const response = await api.get('/info');
  return response.data;
};

export const getHistory = async (limit = 50) => {
  const response = await api.get(`/history?limit=${limit}`);
  return response.data;
};

export const getHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;

