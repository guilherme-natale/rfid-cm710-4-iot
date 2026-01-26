import React, { useState, useEffect } from 'react';
import { Activity, Radio, Database, Wifi, RefreshCw } from 'lucide-react';

const StatsCards = ({ stats, systemStatus }) => {
  const getStatusColor = (status) => {
    if (status === 'running') return 'text-green-600';
    if (status === 'stopped') return 'text-red-600';
    return 'text-gray-400';
  };

  const getStatusDot = (status) => {
    if (status === 'running') return 'bg-green-500';
    if (status === 'stopped') return 'bg-red-500';
    return 'bg-gray-400';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Total Readings */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 font-medium">Total de Leituras</p>
            <p className="text-3xl font-bold text-gray-800 mt-2">
              {stats.total_readings?.toLocaleString() || 0}
            </p>
          </div>
          <div className="p-3 bg-blue-100 rounded-lg">
            <Radio className="h-6 w-6 text-blue-600" />
          </div>
        </div>
      </div>

      {/* Unique EPCs */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 font-medium">TAGs Únicas</p>
            <p className="text-3xl font-bold text-gray-800 mt-2">
              {stats.unique_epcs || 0}
            </p>
          </div>
          <div className="p-3 bg-green-100 rounded-lg">
            <Activity className="h-6 w-6 text-green-600" />
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 font-medium">RabbitMQ</p>
            <div className="flex items-center gap-2 mt-2">
              <span className={`w-3 h-3 rounded-full ${getStatusDot(systemStatus?.rabbitmq_status)} animate-pulse`}></span>
              <span className={`text-sm font-semibold ${getStatusColor(systemStatus?.rabbitmq_status)}`}>
                {systemStatus?.rabbitmq_status === 'running' ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
          <div className="p-3 bg-purple-100 rounded-lg">
            <Database className="h-6 w-6 text-purple-600" />
          </div>
        </div>
      </div>

      {/* CPU Temp */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 font-medium">Temperatura CPU</p>
            <p className="text-3xl font-bold text-gray-800 mt-2">
              {systemStatus?.cpu_temp ? `${systemStatus.cpu_temp.toFixed(1)}°C` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-orange-100 rounded-lg">
            <Activity className="h-6 w-6 text-orange-600" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatsCards;