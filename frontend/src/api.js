import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadMeeting = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/process-meeting', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getProcessingStatus = async (fileId) => {
  const response = await api.get(`/status/${fileId}`);
  return response.data;
};

export default api;
