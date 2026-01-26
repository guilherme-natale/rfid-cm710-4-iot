import React, { useState, useEffect } from 'react';
import { Activity, Radio, Database, Wifi } from 'lucide-react';
import { api } from '../services/api';
import RealTimeReadings from '../components/rfid/RealTimeReadings';
import StatsCards from '../components/rfid/StatsCards';

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_readings: 0,
    unique_epcs: 0,
    by_antenna: {}
  });
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsRes, statusRes] = await Promise.all([
        api.getRFIDStats(),
        api.getSystemStatus()
      ]);
      setStats(statsRes.data);
      setSystemStatus(statusRes.data);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <Radio className="h-6 w-6 text-blue-600" />
          Dashboard RFID
        </h1>
        <p className="text-gray-600 mt-1">Monitor em tempo real do sistema de leitura RFID</p>
      </div>

      {/* Stats Cards */}
      <StatsCards stats={stats} systemStatus={systemStatus} />

      {/* Real-time Readings */}
      <RealTimeReadings />
    </div>
  );
};

export default Dashboard;