import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  FileAudio, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Mail, 
  FileText, 
  Mic,
  ArrowRight,
  FileDown,
  ChevronDown,
  ShieldCheck,
  Languages,
  Server,
  Wifi,
  Cpu,
  Lock,
  LockOpen,
  LogOut,
  History,
  ArrowLeft,
  Clock,
  Calendar,
  ExternalLink,
  HardDrive,
  Database
} from 'lucide-react';

import { motion, AnimatePresence } from 'framer-motion';
import protocolLogo from './assets/protocolist-logo.png';
import yandexLogo from './assets/yandex-logo.png';
import qwenLogo from './assets/qwen-logo.png';
import { uploadMeeting, getProcessingStatus, getSystemInfo, getHistory, getHealth, API_BASE_URL } from './api';


const PROVIDER_NAMES = {
  yandex: 'YandexGPT',
  local: 'Qwen'
};

const PROVIDER_CONTOUR = {
  yandex: 'Открытый',
  local: 'Закрытый'
};

const App = () => {
  const [file, setFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [status, setStatus] = useState(null); // { status: '', message: '' }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [recipientEmail, setRecipientEmail] = useState('v.s.anyanov@gmail.com');
  const [systemInfo, setSystemInfo] = useState({ location: 'Загрузка...', default_provider: 'yandex', provider_name: 'Яндекс Cloud', is_online: false });
  const [selectedProvider, setSelectedProvider] = useState('local');
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [shouldSendEmail, setShouldSendEmail] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [view, setView] = useState('main'); // 'main' | 'archive'
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [healthData, setHealthData] = useState(null);
  const fileInputRef = useRef(null);

  const backendFailCount = useRef(0);

  // Initialize Session ID
  useEffect(() => {
    let sid = localStorage.getItem('protocolist_session_id');
    if (!sid) {
      sid = `sid-${Math.random().toString(36).substr(2, 9)}-${Date.now().toString(36)}`;
      localStorage.setItem('protocolist_session_id', sid);
    }
    setSessionId(sid);

    // Initial Auth Check
    const checkAuth = async () => {
      const storedPwd = localStorage.getItem('protocolist_password');
      if (!storedPwd) {
        setIsAuthenticated(false);
        setAuthChecking(false);
        return;
      }
      try {
        await getSystemInfo(); // This will fail with 401 if password is wrong
        setIsAuthenticated(true);
      } catch (err) {
        if (err.response?.status === 401) {
          setIsAuthenticated(false);
        } else {
          // If it's a network error, we might still be "authed" but offline
          setIsAuthenticated(!!storedPwd);
        }
      }
      setAuthChecking(false);
    };
    checkAuth();
  }, []);

  // Fetch system and health info on mount
  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const info = await getSystemInfo();
        setSystemInfo(info);
        if (!selectedProvider) {
          setSelectedProvider(info.default_provider);
        }
        setIsBackendOnline(true);
        backendFailCount.current = 0; // Reset on success
      } catch (err) {
        console.error("Failed to fetch system info:", err);
        backendFailCount.current += 1;
        if (backendFailCount.current >= 3) {
          setIsBackendOnline(false);
        }
      }

      // Also fetch health/disk info
      try {
        const health = await getHealth();
        setHealthData(health);
      } catch (err) {
        console.error("Failed to fetch health info:", err);
      }
    };
    fetchInfo();
    const interval = setInterval(fetchInfo, 5000); // Poll every 5s for health (less frequent than system info was, but combined)
    return () => clearInterval(interval);
  }, [selectedProvider]);

  // Poll status when fileId is present
  useEffect(() => {
    let interval;
    if (fileId && (!status || (status.status !== 'completed' && status.status !== 'error'))) {
      interval = setInterval(async () => {
        try {
          const data = await getProcessingStatus(fileId);
          setStatus(data);
          if (data.status === 'completed' || data.status === 'error') {
            clearInterval(interval);
            setLoading(false);
          }
        } catch (err) {
          console.error("Polling error:", err);
          // Don't stop polling on momentary network errors
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [fileId, status]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setAuthError('');
    try {
      localStorage.setItem('protocolist_password', password);
      await getSystemInfo();
      setIsAuthenticated(true);
      setError(null);
    } catch (err) {
      setAuthError(err.response?.data?.detail || "Неверный пароль. Попробуйте еще раз.");
      localStorage.removeItem('protocolist_password');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (isFallback = false, fallbackProvider = null, forceCpu = false) => {
    if (!file && !isFallback) return;
    setLoading(true);
    setError(null);
    if (!isFallback) setStatus(null);
    
    try {
      const targetProvider = fallbackProvider || selectedProvider;
      const result = await uploadMeeting(
        isFallback ? null : file, 
        recipientEmail, 
        targetProvider, 
        isFallback ? fileId : null, 
        forceCpu,
        sessionId,
        shouldSendEmail
      );
      if (!isFallback) setFileId(result.file_id);
      setStatus({ status: 'starting', message: 'Перезапуск с новыми параметрами...' });
    } catch (err) {
      setError(err.response?.data?.detail || "Ошибка при обработке запроса.");
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('protocolist_password');
    setIsAuthenticated(false);
    setPassword('');
    setAuthError('');
  };
  
  const fetchHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await getHistory(50);
      setHistory(data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleSwitchToArchive = () => {
    setView('archive');
    fetchHistory();
  };


  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('active');
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('active');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('active');
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setError(null);
    }
  };

  const getProgress = () => {
    if (!status || !status.status) return 0;
    
    switch(status.status) {
      case 'starting': return 5;
      case 'transcribing': return 40;
      case 'summarizing': return 75;
      case 'verifying': return 90;
      case 'sending': return 95;
      case 'completed': return 100;
      case 'failed': return 0;
      case 'error': return 0;
      default: return status.status ? 50 : 0;
    }
  };

  const reset = () => {
    setFile(null);
    setFileId(null);
    setStatus(null);
    setLoading(false);
    setError(null);
  };

  const currentStepIndex = () => {
    if (!status) return 0;
    // Map backend status names to indices: 
    // starting=0, uploading=1, transcribing=2, summarizing=3, verifying=4, sending=5, completed=6
    const steps = ['starting', 'uploading', 'transcribing', 'summarizing', 'verifying', 'sending', 'completed'];
    // Fallback mapping for older/alternative names
    let currentStatus = status.status;
    if (currentStatus === 'generating') currentStatus = 'summarizing';
    if (currentStatus === 'emailing') currentStatus = 'sending';
    
    const idx = steps.indexOf(currentStatus);
    return idx === -1 ? 0 : idx;
  };

  const isActiveStep = (stepName) => {
    if (!status?.status) return false;
    let currentStatus = status.status;
    // Map backend status to frontend step names
    if (currentStatus === 'summarizing') currentStatus = 'generating';
    if (currentStatus === 'sending') currentStatus = 'emailing';
    // starting should also be mapped to uploading for the first step icon to pulse
    if (currentStatus === 'starting') currentStatus = 'uploading';
    return currentStatus === stepName;
  };

  if (authChecking) {
    return (
      <div className="bg-mesh" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Loader2 className="animate-spin text-primary" size={48} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <div className="bg-mesh"></div>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card"
            style={{ maxWidth: '400px', width: '100%', padding: '3rem' }}
          >
            <header style={{ textAlign: 'center', marginBottom: '2rem' }}>
              <div style={{ width: 64, height: 64, margin: '0 auto 1rem' }}>
                <img src={protocolLogo} alt="Logo" style={{ width: '100%', borderRadius: 16 }} />
              </div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Вход в систему</h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Для работы с сервисом требуется аутентификация</p>
            </header>

            <form onSubmit={handleLogin}>
              <div style={{ position: 'relative', marginBottom: '1.5rem' }}>
                <Lock style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--primary)', opacity: 0.7 }} size={18} />
                <input 
                  type="password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Пароль доступа"
                  autoFocus
                  className="glass-input"
                  style={{ width: '100%', paddingLeft: '3rem', borderRadius: 12, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: 'white', height: '3.5rem' }}
                />
              </div>
              
              {authError && (
                <motion.div 
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  style={{ marginBottom: '1.5rem', color: '#fca5a5', fontSize: '0.85rem', textAlign: 'center' }}
                >
                  {authError}
                </motion.div>
              )}

              <button 
                type="submit" 
                className="btn btn-primary" 
                disabled={!password || loading}
                style={{ height: '3.5rem' }}
              >
                {loading ? <Loader2 className="animate-spin" /> : "Войти"}
              </button>
            </form>
            
            <div style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.75rem', color: 'rgba(255,255,255,0.3)' }}>
              Protocolist v5.2.0 • Система защищена
            </div>
          </motion.div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="bg-mesh"></div>
      <div className="container">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="glass-card"
          style={{ position: 'relative' }}
        >
            <div style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', display: 'flex', gap: '0.75rem' }}>
              {view === 'main' && (
                <button 
                  onClick={handleSwitchToArchive}
                  style={{ 
                    background: 'rgba(79, 70, 229, 0.1)', 
                    border: '1px solid rgba(79, 70, 229, 0.2)', 
                    color: 'var(--primary)',
                    padding: '0.5rem 1rem',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.8rem',
                    transition: 'all 0.2s',
                    fontWeight: 600
                  }}
                  className="hover-bg-glass"
                >
                  <History size={16} />
                  <span>История</span>
                </button>
              )}
              <button 
                onClick={handleLogout}
                style={{ 
                  background: 'rgba(255,255,255,0.05)', 
                  border: '1px solid rgba(255,255,255,0.1)', 
                  color: 'rgba(255,255,255,0.5)',
                  padding: '0.5rem',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.8rem',
                  transition: 'all 0.2s'
                }}
                className="hover-bg-glass"
                title="Выйти из системы"
              >
                <LogOut size={16} />
                <span>Выйти</span>
              </button>
            </div>

          <header style={{ textAlign: 'center', marginBottom: '3rem' }}>

            <motion.div 
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200 }}
              style={{ width: 84, height: 84, margin: '0 auto 1.5rem', position: 'relative' }}
            >
              <img 
                src={protocolLogo} 
                alt="Logo" 
                style={{ 
                  width: '100%', 
                  height: '100%', 
                  borderRadius: 22, 
                  boxShadow: '0 12px 24px -6px rgba(0,0,0,0.4)',
                  display: 'block'
                }} 
              />
            </motion.div>
            <h1>Протоколист</h1>
            <p className="subtitle">Профессиональное создание протоколов совещаний.</p>
            
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '1.5rem', flexWrap: 'wrap' }}>
              <div className="system-badge" style={{ borderColor: isBackendOnline ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)' }}>
                <Server size={14} style={{ color: isBackendOnline ? '#22c55e' : '#ef4444' }} /> 
                <span style={{ fontSize: '0.85rem' }}>Система: </span>
                <span className={isBackendOnline ? "status-pulse" : ""} style={{ 
                  color: isBackendOnline ? '#22c55e' : '#ef4444', 
                  fontWeight: 'bold',
                  fontSize: '0.85rem'
                }}>
                  {isBackendOnline ? 'Работает' : 'Не работает'}
                </span>
              </div>
              <div className="system-badge">
                <Cpu size={14} style={{ color: 'var(--primary)' }} /> 
                <span style={{ fontSize: '0.85rem' }}>Модель: </span>
                <span style={{ color: 'var(--primary)', fontWeight: 'bold', fontSize: '0.85rem' }}>
                  {PROVIDER_NAMES[selectedProvider || systemInfo.default_provider] || '---'}
                </span>
              </div>
              <div className="system-badge" style={{ borderColor: (selectedProvider || systemInfo.default_provider) === 'local' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)' }}>
                {(selectedProvider || systemInfo.default_provider) === 'local' ? (
                  <Lock size={14} style={{ color: '#22c55e' }} />
                ) : (
                  <LockOpen size={14} style={{ color: '#ef4444' }} />
                )}
                <span style={{ fontSize: '0.85rem' }}>Контур: </span>
                <span style={{
                  color: (selectedProvider || systemInfo.default_provider) === 'local' ? '#22c55e' : '#ef4444',
                  fontWeight: 'bold',
                  fontSize: '0.85rem'
                }}>
                  {PROVIDER_CONTOUR[selectedProvider || systemInfo.default_provider] || '---'}
                </span>
              </div>
            </div>
          </header>

          <AnimatePresence mode="wait">
            {view === 'archive' ? (
              <motion.div 
                key="archive-view"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
                  <button 
                    onClick={() => setView('main')}
                    style={{ 
                      background: 'none', 
                      border: 'none', 
                      color: 'var(--text-muted)', 
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.5rem',
                      borderRadius: '8px'
                    }}
                    className="hover-bg-glass"
                  >
                    <ArrowLeft size={20} />
                    <span>Назад</span>
                  </button>
                  <h2 style={{ fontSize: '1.5rem', margin: 0 }}>История протоколов</h2>
                </div>

                {historyLoading ? (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                    <Loader2 className="animate-spin text-primary" size={40} />
                  </div>
                ) : history.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
                    <Clock size={48} style={{ opacity: 0.2, margin: '0 auto 1.5rem' }} />
                    <p>История пуста. Создайте свой первый протокол!</p>
                  </div>
                ) : (
                  <div className="archive-list">
                    {history.map((item) => (
                      <div key={item.file_id} className="archive-item">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', overflow: 'hidden' }}>
                          <div style={{ 
                            width: '40px', 
                            height: '40px', 
                            borderRadius: '10px', 
                            background: 'rgba(79, 70, 229, 0.1)', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            flexShrink: 0
                          }}>
                            <FileText size={20} color="var(--primary)" />
                          </div>
                          <div style={{ overflow: 'hidden' }}>
                            <div style={{ 
                              fontWeight: 600, 
                              fontSize: '0.95rem', 
                              whiteSpace: 'nowrap', 
                              overflow: 'hidden', 
                              textOverflow: 'ellipsis',
                              marginBottom: '0.25rem'
                            }}>
                              {item.filename}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <Calendar size={12} /> {new Date(item.updated_at).toLocaleDateString()}
                              </span>
                              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <Clock size={12} /> {new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                              {!item.file_exists && (
                                <span style={{ color: '#f87171', fontWeight: 600 }}>• Файл удален</span>
                              )}
                            </div>
                          </div>
                        </div>
                        
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {item.file_exists ? (
                            <a 
                              href={`${API_BASE_URL}/download/${item.file_id}?password=${localStorage.getItem('protocolist_password')}`}
                              className="btn"
                              style={{ 
                                padding: '0.5rem 1rem', 
                                fontSize: '0.8rem', 
                                background: 'rgba(16, 185, 129, 0.1)', 
                                border: '1px solid rgba(16, 185, 129, 0.2)',
                                color: '#10b981',
                                borderRadius: '8px',
                                textDecoration: 'none'
                              }}
                              download
                            >
                              <FileDown size={14} /> Скачать
                            </a>
                          ) : (
                            <button 
                              className="btn"
                              disabled
                              style={{ 
                                padding: '0.5rem 1rem', 
                                fontSize: '0.8rem', 
                                background: 'rgba(255, 255, 255, 0.03)', 
                                border: '1px solid rgba(255, 255, 255, 0.05)',
                                color: 'rgba(255, 255, 255, 0.2)',
                                borderRadius: '8px'
                              }}
                            >
                              Удален
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            ) : !fileId ? (

              <motion.div 
                key="upload-section"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
              >
                <div 
                  className="dropzone"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current.click()}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={handleFileChange} 
                    style={{ display: 'none' }}
                    accept=".mp3,.m4a,.aac,.wav,.mp4,.webm,.mov,.avi,.ogg,.flac,.txt,.pdf,.docx"
                  />
                  <Upload className="dropzone-icon" />
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ fontWeight: 600 }}>{file ? file.name : "Нажмите или перетащите файл"}</p>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.5rem', lineHeight: '1.4' }}>
                      Аудио: MP3, WAV, M4A, AAC, OGG, FLAC<br/>
                      Видео: MP4, WEBM, MOV, AVI<br/>
                      Документы: PDF, DOCX, TXT<br/>
                      (до 500 МБ)
                    </p>
                  </div>
                </div>

                {error && (
                  <motion.div 
                    initial={{ opacity: 0 }} 
                    animate={{ opacity: 1 }}
                    style={{ marginTop: '1.5rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--error)', borderRadius: 12, color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.75rem' }}
                  >
                    <AlertCircle size={20} />
                    <span style={{ fontSize: '0.875rem' }}>{error}</span>
                  </motion.div>
                )}

                <div style={{ marginTop: '2.5rem' }}>
                  <div className="input-field-group" style={{ marginBottom: '1.5rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                      Выберите модель:
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                      <ProviderOption 
                        id="yandex" 
                        name="Онлайн" 
                        subtitle="Открытый контур"
                        selected={selectedProvider === 'yandex'} 
                        onClick={() => setSelectedProvider('yandex')} 
                      />
                      <ProviderOption 
                        id="local" 
                        name="Локально" 
                        subtitle="Закрытый контур"
                        selected={selectedProvider === 'local'} 
                        onClick={() => setSelectedProvider('local')} 
                      />
                    </div>
                  </div>


                  <div 
                    className="input-field-group" 
                    style={{ marginBottom: '1.5rem' }}
                  >
                    <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                      Отправить готовый протокол на email:
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Mail style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--primary)', opacity: 0.7 }} size={18} />
                      <input 
                        type="email" 
                        value={recipientEmail}
                        onChange={(e) => setRecipientEmail(e.target.value)}
                        placeholder="your-email@example.com"
                        className="glass-input"
                        style={{ width: '100%', paddingLeft: '3rem', borderRadius: 12, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: 'white', height: '3.5rem' }}
                      />
                    </div>
                    
                    <div 
                      onClick={() => setShouldSendEmail(!shouldSendEmail)}
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '0.75rem', 
                        marginTop: '1rem', 
                        cursor: 'pointer',
                        userSelect: 'none',
                        padding: '0.5rem',
                        borderRadius: '8px',
                        transition: 'background 0.2s',
                      }}
                      className="hover-bg-glass"
                    >
                      <div style={{ 
                        width: '20px', 
                        height: '20px', 
                        borderRadius: '4px', 
                        border: '2px solid var(--primary)', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        background: shouldSendEmail ? 'var(--primary)' : 'transparent',
                        transition: 'all 0.2s'
                      }}>
                        {shouldSendEmail && <CheckCircle2 size={14} color="white" />}
                      </div>
                      <span style={{ fontSize: '0.85rem', color: shouldSendEmail ? 'white' : 'var(--text-muted)' }}>
                        Отправить результат на почту
                      </span>
                    </div>
                  </div>
                  
                  <button 
                    className="btn btn-primary" 
                    disabled={!file || loading || !isBackendOnline}
                    onClick={() => handleUpload()}
                  >
                    {loading ? <Loader2 className="animate-spin" /> : "Создать протокол"}
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.div 
                key="status-section"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <div style={{ marginBottom: '2rem' }}>
                    <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.75rem', 
                    marginBottom: '1.5rem', 
                    padding: '0.75rem 1rem', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '12px',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}>
                    <FileAudio size={20} className="text-primary" style={{ color: 'var(--primary)' }} />
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>Текущий файл:</span>
                      <span style={{ fontWeight: 600, fontSize: '1rem' }}>{status?.filename || file?.name || 'Загрузка...'}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontWeight: 600 }}>
                      {`Выполнено: ${status?.status === 'completed' ? '100%' : `${Math.round((currentStepIndex() / 6) * 100)}%`}`}
                    </span>
                    <span style={{ fontSize: '0.875rem', color: 'var(--primary)' }}>
                      {status?.status === 'completed' ? 'Завершено' : 'В процессе...'}
                    </span>
                  </div>
                  <div className="progress-track">
                    <motion.div 
                      className="progress-fill"
                      initial={{ width: '0%' }}
                      animate={{ width: `${(currentStepIndex() / 6) * 100}%` }}
                    />
                  </div>
                </div>

                <div className="status-container">
                  <StatusStep 
                    title="Загрузка" 
                    desc={(status?.status === 'starting' || status?.status === 'uploading') && status?.message ? status.message : (selectedProvider === 'local' ? "Подготовка файла для локальной обработки" : "Загружаем аудио в облачное хранилище")} 
                    icon={<Upload size={18} />}
                    isActive={status?.status === 'uploading' || status?.status === 'starting'}
                    isComplete={currentStepIndex() > 1}
                  />
                  <StatusStep 
                    title="Транскрипция" 
                    desc={isActiveStep('transcribing') && status?.message ? status.message : `Распознавание речи: ${selectedProvider === 'yandex' ? 'SpeechKit' : 'Whisper'}`} 
                    icon={<Mic size={18} />}
                    isActive={isActiveStep('transcribing')}
                    isComplete={currentStepIndex() > 2}
                  />
                  <StatusStep 
                    title="Анализ и Саммери" 
                    desc={isActiveStep('generating') && status?.message ? status.message : `Генерация протокола через ${selectedProvider?.toUpperCase() || 'AI'}`} 
                    icon={<FileText size={18} />}
                    isActive={isActiveStep('generating')}
                    isComplete={currentStepIndex() > 3}
                  />
                  <StatusStep 
                    title="Верификация" 
                    desc="AI-Аудитор проверяет точность протокола" 
                    icon={<ShieldCheck size={18} />}
                    isActive={status?.status === 'verifying'}
                    isComplete={currentStepIndex() > 4}
                  />
                  <StatusStep 
                    title="Завершение" 
                    desc={status?.email_error ? "Протокол готов, но ошибка почты" : (status?.status === 'error' ? "Ошибка выполнения" : "Формирование DOCX и отправка email")} 
                    icon={<CheckCircle2 size={18} />}
                    isActive={status?.status === 'emailing'}
                    isComplete={currentStepIndex() > 5 && !status?.email_error && !status?.error}
                    isWarning={status?.email_error}
                    isError={status?.status === 'error'}
                  />
                </div>

                {status?.status === 'completed' && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ marginTop: '3rem' }}
                  >
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                      <CheckCircle2 size={48} color={status?.email_error ? "#fbbf24" : "var(--secondary)"} />
                      <h3 style={{ fontSize: '1.5rem', color: status?.email_error ? "#fbbf24" : "white" }}>
                        {status?.email_error ? "Протокол готов (с ошибкой почты)" : "Протокол готов!"}
                      </h3>
                      <div style={{ 
                        margin: '1.5rem 0',
                        padding: '1.5rem',
                        borderRadius: '16px',
                        border: status?.email_error ? '2px solid #fbbf24' : '1px solid rgba(255,255,255,0.1)',
                        background: status?.email_error ? 'rgba(251, 191, 36, 0.1)' : 'rgba(255,255,255,0.05)',
                        maxWidth: '90%',
                        textAlign: 'center',
                        boxShadow: status?.email_error ? '0 0 20px rgba(251, 191, 36, 0.1)' : 'none'
                      }}>
                        <p style={{ color: status?.email_error ? "#fde68a" : "var(--text-muted)", fontSize: '1rem', margin: 0, lineHeight: '1.6', fontWeight: 500 }}>
                          {status?.message || "Файл сформирован и доступен для скачивания."}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                        <a 
                          href={`${API_BASE_URL}/download/${fileId}?password=${localStorage.getItem('protocolist_password')}`} 
                          className="btn" 
                          style={{ background: 'var(--secondary)', color: 'white', display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', width: 'auto', padding: '0.75rem 1.5rem', borderRadius: 12, fontWeight: 500 }}
                          download
                        >
                          <FileDown size={18} /> Скачать DOCX
                        </a>
                        <button className="btn btn-primary" style={{ width: 'auto' }} onClick={reset}>
                          Новый файл
                        </button>
                      </div>
                    </div>

                    {/* Results Transparency Section */}
                    <div style={{ marginTop: '4rem', paddingTop: '2rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '2rem', color: 'var(--primary)' }}>
                        <ShieldCheck size={20} />
                        <h4 style={{ margin: 0, fontSize: '1.1rem' }}>Прозрачность и верификация</h4>
                      </div>
                      
                      <Accordion 
                        title="Отчет AI-Аудитора" 
                        icon={<ShieldCheck size={18} />}
                        content={status.verification_report}
                        type="verification"
                      />
                      
                      <Accordion 
                        title="Полная расшифровка текста" 
                        icon={<Languages size={18} />}
                        content={status.transcription}
                        type="transcription"
                      />
                    </div>
                  </motion.div>
                )}

                {status?.status === 'awaiting_fallback' && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ marginTop: '2rem', padding: '2rem', background: 'rgba(251, 191, 36, 0.1)', border: '1px solid #fbbf24', borderRadius: 16, textAlign: 'center' }}
                  >
                    <Cpu size={48} color="#fbbf24" style={{ margin: '0 auto 1rem' }} />
                    <h3 style={{ color: '#fbbf24', marginBottom: '0.5rem' }}>Проблема с видеокартой (GPU)</h3>
                    <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                      Локальная обработка на GPU временно недоступна. Как вы хотите продолжить?
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      <button 
                        className="btn" 
                        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                        onClick={() => handleUpload(true, 'local', true)}
                      >
                        🐢 На процессоре (CPU)<br/>
                        <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>Это будет ОЧЕНЬ медленно</span>
                      </button>
                      <button 
                        className="btn btn-primary"
                        onClick={() => handleUpload(true, 'yandex', false)}
                      >
                        ☁️ Через Облако (Яндекс)<br/>
                        <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>Быстро, но расходует лимиты</span>
                      </button>
                    </div>
                  </motion.div>
                )}

                {status?.status === 'error' && (
                  <div style={{ marginTop: '3rem', textAlign: 'center' }}>
                    <AlertCircle color="var(--error)" size={48} style={{ margin: '0 auto 1rem' }} />
                    <h3 style={{ color: 'var(--error)' }}>Произошла ошибка</h3>
                    <p>{status.message}</p>
                    <button className="btn btn-primary" style={{ marginTop: '1.5rem', width: 'auto' }} onClick={reset}>
                      Попробовать снова
                    </button>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          {/* Footer Section with Disk Info */}
          <footer style={{ 
            marginTop: '3rem', 
            paddingTop: '1.5rem', 
            borderTop: '1px solid rgba(255,255,255,0.08)', 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            flexWrap: 'wrap',
            gap: '1rem'
          }}>
            <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.3)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Protocolist v5.2.0</span>
              {healthData?.tasks_in_queue > 0 && (
                <span style={{ 
                  background: 'rgba(59, 130, 246, 0.1)', 
                  color: 'var(--primary)', 
                  padding: '2px 6px', 
                  borderRadius: '4px',
                  fontWeight: 600
                }}>
                  Очередь: {healthData.tasks_in_queue}
                </span>
              )}
            </div>
            
            {healthData && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <HardDrive size={14} style={{ opacity: 0.6 }} />
                  <span>Свободно: {healthData.disk_free_gb} ГБ</span>
                  <div style={{ 
                    width: '60px', 
                    height: '6px', 
                    background: 'rgba(255,255,255,0.05)', 
                    borderRadius: '3px', 
                    overflow: 'hidden',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}>
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${healthData.disk_used_percent}%` }}
                      style={{ 
                        height: '100%', 
                        background: healthData.disk_used_percent > 90 ? '#ef4444' : healthData.disk_used_percent > 70 ? '#f59e0b' : 'var(--secondary)',
                        boxShadow: healthData.disk_used_percent > 90 ? '0 0 8px rgba(239, 68, 68, 0.4)' : 'none'
                      }} 
                    />
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <Database size={14} style={{ opacity: 0.6 }} />
                  <span>Всего: {healthData.disk_total_gb} ГБ</span>
                </div>
              </div>
            )}
          </footer>
        </motion.div>
      </div>
    </>
  );
};

const StatusStep = ({ title, desc, icon, isActive, isComplete, isError, isWarning }) => {
  // Determine state
  const stepState = isError ? 'error' : isWarning ? 'warning' : isComplete ? 'complete' : isActive ? 'active' : '';
  
  return (
    <div className={`status-step ${isActive ? 'active' : ''}`} style={{ opacity: isComplete || isActive || isError || isWarning ? 1 : 0.4 }}>
      <div className={`step-icon ${stepState}`} style={{ 
        background: isError ? 'rgba(239, 68, 68, 0.2)' : isWarning ? 'rgba(251, 191, 36, 0.2)' : undefined,
        borderColor: isError ? '#ef4444' : isWarning ? '#fbbf24' : undefined,
        color: isError ? '#ef4444' : isWarning ? '#fbbf24' : undefined,
        borderWidth: isError || isWarning ? '2px' : '1px',
        borderStyle: 'solid'
      }}>
        {isComplete ? <CheckCircle2 size={18} color="white" /> : (isError || isWarning) ? <AlertCircle size={18} /> : icon}
      </div>
      <div className="step-content">
        <div className="step-title" style={{ color: isComplete ? 'var(--secondary)' : isError ? '#ef4444' : isWarning ? '#fbbf24' : isActive ? 'var(--primary)' : 'inherit' }}>
          {title}
        </div>
        <div className="step-desc" style={{ color: isError ? '#fca5a5' : isWarning ? '#fde68a' : 'var(--text-muted)' }}>{desc}</div>
      </div>
      {isActive && <Loader2 className="animate-spin" size={18} color="var(--primary)" />}
    </div>
  );
};

const Accordion = ({ title, icon, content, type }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  if (!content) return null;

  return (
    <div className={`glass-accordion ${isOpen ? 'open' : ''}`} style={{ marginBottom: '1rem' }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{ width: '100%', background: 'none', border: 'none', padding: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', color: 'white' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ color: type === 'verification' ? 'var(--secondary)' : 'var(--primary)' }}>{icon}</span>
          <span style={{ fontWeight: 500 }}>{title}</span>
        </div>
        <motion.div animate={{ rotate: isOpen ? 180 : 0 }}>
          <ChevronDown size={20} />
        </motion.div>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '0 1.5rem 1.5rem', color: 'var(--text-muted)', fontSize: '0.925rem', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
              <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 8, borderLeft: `3px solid ${type === 'verification' ? 'var(--secondary)' : 'var(--primary)'}` }}>
                {content}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const ProviderOption = ({ id, name, subtitle, selected, onClick }) => (
  <button 
    onClick={onClick}
    style={{ 
      padding: '0.75rem', 
      borderRadius: 12, 
      border: '1px solid', 
      borderColor: selected ? 'var(--primary)' : 'rgba(255,255,255,0.1)', 
      background: selected ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255,255,255,0.02)', 
      color: selected ? 'white' : 'var(--text-muted)',
      cursor: 'pointer',
      fontSize: '0.8rem',
      fontWeight: selected ? 600 : 400,
      transition: 'all 0.2s ease',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.25rem'
    }}
  >
    <div style={{ 
      width: '32px', 
      height: '32px', 
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: id === 'yandex' ? '50%' : '6px',
      marginBottom: '0.25rem',
      overflow: 'hidden'
    }}>
      <img 
        src={id === 'yandex' ? yandexLogo : qwenLogo} 
        alt={name}
        style={{ 
          width: '100%', 
          height: '100%', 
          objectFit: id === 'yandex' ? 'cover' : 'contain',
          transform: id === 'yandex' ? 'scale(1.05)' : 'none'
        }}
      />
    </div>
    <span style={{ fontSize: '0.85rem' }}>{name}</span>
    {subtitle && <span style={{ fontSize: '0.65rem', opacity: 0.6 }}>{subtitle}</span>}
  </button>
);

export default App;
