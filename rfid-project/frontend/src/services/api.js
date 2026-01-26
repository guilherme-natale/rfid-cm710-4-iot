import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const api = {
  // RFID Readings
  getRFIDReadings: (params = {}) => axios.get(`${API}/rfid/readings`, { params }),
  getLatestReadings: (limit = 10) => axios.get(`${API}/rfid/readings/latest`, { params: { limit } }),
  getRFIDStats: () => axios.get(`${API}/rfid/readings/stats`),
  
  // CM710 Config
  getCM710Config: () => axios.get(`${API}/cm710/config`),
  setCM710Config: (config) => axios.post(`${API}/cm710/config`, config),
  getConfigHistory: (limit = 10) => axios.get(`${API}/cm710/config/history`, { params: { limit } }),
  
  // Network
  getNetworkStatus: () => axios.get(`${API}/network/status`),
  setNetworkConfig: (config) => axios.post(`${API}/network/config`, config),
  setWiFiConfig: (config) => axios.post(`${API}/network/wifi`, config),
  
  // System
  getSystemStatus: () => axios.get(`${API}/system/status`),
  restartService: (service) => axios.post(`${API}/system/restart-service`, null, { params: { service } })
};
