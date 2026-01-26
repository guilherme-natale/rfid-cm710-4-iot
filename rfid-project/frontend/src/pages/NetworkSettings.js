import React, { useState } from 'react';
import { Wifi, Network, Save, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../services/api';

const NetworkSettings = () => {
  const [activeTab, setActiveTab] = useState('ethernet');
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const [ethernetConfig, setEthernetConfig] = useState({
    interface: 'eth0',
    dhcp: true,
    ip_address: '',
    netmask: '24',
    gateway: '',
    dns: '8.8.8.8'
  });
  
  const [wifiConfig, setWifiConfig] = useState({
    ssid: '',
    password: '',
    security: 'WPA2'
  });

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleEthernetSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.setNetworkConfig(ethernetConfig);
      showMessage('success', 'Configuração de rede salva com sucesso!');
    } catch (error) {
      console.error('Erro:', error);
      showMessage('error', 'Erro ao salvar configuração');
    } finally {
      setLoading(false);
    }
  };

  const handleWiFiSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.setWiFiConfig(wifiConfig);
      showMessage('success', 'Configuração WiFi salva com sucesso!');
    } catch (error) {
      console.error('Erro:', error);
      showMessage('error', 'Erro ao salvar configuração WiFi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <Network className="h-6 w-6 text-blue-600" />
          Configurações de Rede
        </h1>
        <p className="text-gray-600 mt-1">Configure conexão Ethernet e WiFi</p>
      </div>

      {/* Message */}
      {message && (
        <div className={`rounded-lg p-4 flex items-center gap-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow-sm">
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px">
            <button
              onClick={() => setActiveTab('ethernet')}
              className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'ethernet'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Network className="h-4 w-4 inline mr-2" />
              Ethernet
            </button>
            <button
              onClick={() => setActiveTab('wifi')}
              className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'wifi'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Wifi className="h-4 w-4 inline mr-2" />
              WiFi
            </button>
          </nav>
        </div>

        <div className="p-6">
          {/* Ethernet Tab */}
          {activeTab === 'ethernet' && (
            <form onSubmit={handleEthernetSubmit} className="space-y-6">
              {/* DHCP Toggle */}
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-800">DHCP Automático</p>
                  <p className="text-sm text-gray-600">Obter IP automaticamente</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={ethernetConfig.dhcp}
                    onChange={(e) => setEthernetConfig({ ...ethernetConfig, dhcp: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* IP Estático */}
              {!ethernetConfig.dhcp && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Endereço IP
                    </label>
                    <input
                      type="text"
                      placeholder="192.168.1.100"
                      value={ethernetConfig.ip_address}
                      onChange={(e) => setEthernetConfig({ ...ethernetConfig, ip_address: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      required={!ethernetConfig.dhcp}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Máscara de Sub-rede
                    </label>
                    <input
                      type="text"
                      placeholder="24"
                      value={ethernetConfig.netmask}
                      onChange={(e) => setEthernetConfig({ ...ethernetConfig, netmask: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Gateway
                    </label>
                    <input
                      type="text"
                      placeholder="192.168.1.1"
                      value={ethernetConfig.gateway}
                      onChange={(e) => setEthernetConfig({ ...ethernetConfig, gateway: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      required={!ethernetConfig.dhcp}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      DNS
                    </label>
                    <input
                      type="text"
                      placeholder="8.8.8.8"
                      value={ethernetConfig.dns}
                      onChange={(e) => setEthernetConfig({ ...ethernetConfig, dns: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                ) : (
                  <>
                    <Save className="h-5 w-5" />
                    Salvar Configuração
                  </>
                )}
              </button>
            </form>
          )}

          {/* WiFi Tab */}
          {activeTab === 'wifi' && (
            <form onSubmit={handleWiFiSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nome da Rede (SSID)
                </label>
                <input
                  type="text"
                  placeholder="MinhaRede"
                  value={wifiConfig.ssid}
                  onChange={(e) => setWifiConfig({ ...wifiConfig, ssid: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Senha
                </label>
                <input
                  type="password"
                  placeholder="********"
                  value={wifiConfig.password}
                  onChange={(e) => setWifiConfig({ ...wifiConfig, password: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Segurança
                </label>
                <select
                  value={wifiConfig.security}
                  onChange={(e) => setWifiConfig({ ...wifiConfig, security: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="WPA2">WPA2</option>
                  <option value="WPA">WPA</option>
                  <option value="OPEN">Aberta</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                ) : (
                  <>
                    <Save className="h-5 w-5" />
                    Conectar WiFi
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default NetworkSettings;