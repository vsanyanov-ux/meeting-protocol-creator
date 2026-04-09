import axios from 'axios';

export const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const uploadMeeting = async (file, email) => {
  const formData = new FormData();
  formData.append('file', file);
  if (email) {
    formData.append('email', email);
  }
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
