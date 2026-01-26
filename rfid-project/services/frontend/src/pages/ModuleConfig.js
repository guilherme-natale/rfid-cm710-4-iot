import React, { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../services/api';

const ModuleConfig = () => {
  const [config, setConfig] = useState({
    potencia: 20,
    regiao: '3C',  // Brasil
    antenas: '0F',
    frequencia: null,
    fastid: '01'
  });
  const [currentConfig, setCurrentConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    loadCurrentConfig();
  }, []);

  const loadCurrentConfig = async () => {
    try {
      setLoading(true);
      const res = await api.getCM710Config();
      setCurrentConfig(res.data);
    } catch (error) {
      console.error('Erro ao carregar config:', error);
      showMessage('error', 'Erro ao carregar configuração');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.setCM710Config(config);
      showMessage('success', 'Configuração aplicada com sucesso!');
      setTimeout(() => loadCurrentConfig(), 2000);
    } catch (error) {
      console.error('Erro ao aplicar config:', error);
      showMessage('error', 'Erro ao aplicar configuração');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const regioes = [
    { value: '01', label: 'China 920-925 MHz' },
    { value: '02', label: 'China 840-845 MHz' },
    { value: '04', label: 'Europa 865-868 MHz' },
    { value: '08', label: 'USA 902-928 MHz' },
    { value: '16', label: 'Korea' },
    { value: '32', label: 'Japan' },
    { value: '3C', label: 'Brasil 902-928 MHz' },
    { value: '3D', label: 'ETSI Upper' },
    { value: '3E', label: 'Australia' },
    { value: '40', label: 'Israel' },
    { value: '41', label: 'Hong Kong' },
    { value: '43', label: '880-930 MHz' },
    { value: '45', label: 'Thailand' }
  ];

  const antenas = [
    { value: '01', label: 'Apenas Antena 1' },
    { value: '02', label: 'Apenas Antena 2' },
    { value: '04', label: 'Apenas Antena 3' },
    { value: '08', label: 'Apenas Antena 4' },
    { value: '0F', label: 'Todas as Antenas' }
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <Settings className="h-6 w-6 text-blue-600" />
          Configuração do Módulo CM710-4
        </h1>
        <p className="text-gray-600 mt-1">Configure potência, região, antenas e outros parâmetros</p>
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

      {/* Current Config Display */}
      {currentConfig && (
        <div className="bg-blue-50 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-blue-900 mb-4">Configuração Atual</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-blue-700 font-medium">Firmware</p>
              <p className="text-blue-900">{currentConfig.firmware || 'N/A'}</p>
            </div>
            <div>
              <p className="text-blue-700 font-medium">Temperatura</p>
              <p className="text-blue-900">{currentConfig.temperatura ? `${currentConfig.temperatura.toFixed(1)}°C` : 'N/A'}</p>
            </div>
            <div>
              <p className="text-blue-700 font-medium">Potência</p>
              <p className="text-blue-900">{currentConfig.potencia ? `${currentConfig.potencia.toFixed(0)} dBm` : 'N/A'}</p>
            </div>
            <div>
              <p className="text-blue-700 font-medium">Região</p>
              <p className="text-blue-900">{currentConfig.regiao_desc || 'N/A'}</p>
            </div>
            <div>
              <p className="text-blue-700 font-medium">Antenas</p>
              <p className="text-blue-900">{currentConfig.antenas_desc || 'N/A'}</p>
            </div>
          </div>
          <button
            onClick={loadCurrentConfig}
            disabled={loading}
            className="mt-4 flex items-center gap-2 text-blue-700 hover:text-blue-800 font-medium"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
        </div>
      )}

      {/* Config Form */}
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 space-y-6">
        {/* Potência */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Potência de Transmissão (dBm)
          </label>
          <input
            type="number"
            min="5"
            max="30"
            value={config.potencia}
            onChange={(e) => setConfig({ ...config, potencia: parseInt(e.target.value) })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p className="text-xs text-gray-500 mt-1">Valores entre 5 e 30 dBm</p>
        </div>

        {/* Região */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Região de Frequência
          </label>
          <select
            value={config.regiao}
            onChange={(e) => setConfig({ ...config, regiao: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {regioes.map(r => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>

        {/* Antenas */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Antenas Ativas
          </label>
          <select
            value={config.antenas}
            onChange={(e) => setConfig({ ...config, antenas: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {antenas.map(a => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </div>

        {/* FastID */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            FastID
          </label>
          <select
            value={config.fastid}
            onChange={(e) => setConfig({ ...config, fastid: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="01">Ligado</option>
            <option value="00">Desligado</option>
          </select>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              Aplicando...
            </>
          ) : (
            <>
              <Save className="h-5 w-5" />
              Aplicar Configuração
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default ModuleConfig;