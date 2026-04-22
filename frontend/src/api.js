import axios from 'axios';

export const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadMeeting = async (file, email, provider, existingFileId = null, forceCpu = false) => {
  const formData = new FormData();
  
  if (file) {
    formData.append('file', file, file.name || 'blob');
  }
  
  if (email) formData.append('email', email);
  if (provider) formData.append('provider', provider);
  if (existingFileId) formData.append('existing_file_id', existingFileId);
  if (forceCpu) formData.append('force_cpu', 'true');

  const url = `${API_BASE_URL}/process-meeting`;

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
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

export const getResults = async (fileId) => {
  const response = await api.get(`/results/${fileId}`);
  return response.data;
};

export default api;
