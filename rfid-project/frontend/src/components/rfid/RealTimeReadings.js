import React, { useState, useEffect } from 'react';
import { Activity, Radio } from 'lucide-react';
import { api } from '../../services/api';

const RealTimeReadings = () => {
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReadings();
    const interval = setInterval(loadReadings, 2000); // Atualiza a cada 2s
    return () => clearInterval(interval);
  }, []);

  const loadReadings = async () => {
    try {
      const res = await api.getLatestReadings(20);
      setReadings(res.data.readings);
    } catch (error) {
      console.error('Erro ao carregar leituras:', error);
    } finally {
      setLoading(false);
    }
  };

  const getRssiColor = (rssi) => {
    if (rssi > -40) return 'text-green-600 bg-green-50';
    if (rssi > -60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getRssiBars = (rssi) => {
    if (rssi > -40) return 4;
    if (rssi > -50) return 3;
    if (rssi > -60) return 2;
    return 1;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <Radio className="h-5 w-5 text-blue-600" />
              Leituras em Tempo Real
            </h2>
            <p className="text-sm text-gray-600 mt-1">Últimas 20 leituras</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-gray-600">Atualizando</span>
          </div>
        </div>
      </div>

      <div className="p-6">
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600 mt-2">Carregando leituras...</p>
          </div>
        ) : readings.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Radio className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>Nenhuma leitura encontrada</p>
          </div>
        ) : (
          <div className="space-y-2">
            {readings.map((reading, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-4 flex-1">
                  {/* EPC */}
                  <div className="flex-1">
                    <p className="text-xs text-gray-500">EPC</p>
                    <p className="font-mono font-semibold text-gray-800">{reading.epc}</p>
                  </div>

                  {/* Timestamp */}
                  <div className="flex-1">
                    <p className="text-xs text-gray-500">Data/Hora</p>
                    <p className="text-sm text-gray-700">{reading.timestamp}</p>
                  </div>

                  {/* Antenna */}
                  <div>
                    <p className="text-xs text-gray-500">Antena</p>
                    <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                      {reading.antenna}
                    </div>
                  </div>

                  {/* RSSI */}
                  <div>
                    <p className="text-xs text-gray-500">RSSI</p>
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getRssiColor(reading.rssi)}`}>
                      {reading.rssi.toFixed(1)} dBm
                    </span>
                  </div>

                  {/* Signal Bars */}
                  <div className="flex gap-1">
                    {[...Array(4)].map((_, i) => (
                      <div
                        key={i}
                        className={`w-1 rounded-full ${
                          i < getRssiBars(reading.rssi) ? 'bg-blue-600' : 'bg-gray-300'
                        }`}
                        style={{ height: `${(i + 1) * 6}px` }}
                      ></div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default RealTimeReadings;