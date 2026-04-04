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
  Languages
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { uploadMeeting, getProcessingStatus, API_BASE_URL } from './api';

const App = () => {
  const [file, setFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [status, setStatus] = useState(null); // { status: '', message: '' }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

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

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setStatus(null);
    
    try {
      const result = await uploadMeeting(file);
      setFileId(result.file_id);
    } catch (err) {
      setError(err.response?.data?.detail || "Ошибка при загрузке файла. Убедитесь, что бэкенд запущен.");
      setLoading(false);
    }
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

  const reset = () => {
    setFile(null);
    setFileId(null);
    setStatus(null);
    setLoading(false);
    setError(null);
  };

  const currentStepIndex = () => {
    if (!status) return 0;
    const steps = ['starting', 'uploading', 'transcribing', 'generating', 'verifying', 'emailing', 'completed'];
    const idx = steps.indexOf(status.status);
    return idx === -1 ? 0 : idx;
  };

  return (
    <>
      <div className="bg-mesh"></div>
      <div className="container">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="glass-card"
        >
          <header style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <motion.div 
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200 }}
              style={{ background: 'var(--primary)', width: 64, height: 64, borderRadius: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}
            >
              <FileAudio color="white" size={32} />
            </motion.div>
            <h1>Meeting Protocol Creator</h1>
            <p className="subtitle">Профессиональное создание протоколов совещаний из аудиозаписей.</p>
          </header>

          <AnimatePresence mode="wait">
            {!fileId ? (
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
                  <button 
                    className="btn btn-primary" 
                    disabled={!file || loading}
                    onClick={handleUpload}
                  >
                    {loading ? <Loader2 className="animate-pulse" /> : "Создать протокол"}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontWeight: 600 }}>Статус обработки</span>
                    <span style={{ fontSize: '0.875rem', color: 'var(--primary)' }}>
                      {status?.status === 'completed' ? 'Завершено 100%' : 'В процессе...'}
                    </span>
                  </div>
                  <div className="progress-track">
                    <motion.div 
                      className="progress-fill"
                      initial={{ width: '0%' }}
                      animate={{ width: `${(currentStepIndex() + 1) * 16.66}%` }}
                    />
                  </div>
                </div>

                <div className="status-container">
                  <StatusStep 
                    title="Загрузка" 
                    desc="Загружаем аудио в облачное хранилище" 
                    icon={<Upload size={18} />}
                    isActive={status?.status === 'uploading'}
                    isComplete={currentStepIndex() > 1}
                  />
                  <StatusStep 
                    title="Транскрипция" 
                    desc="Превращаем голос в текст (Yandex SpeechKit)" 
                    icon={<Mic size={18} />}
                    isActive={status?.status === 'transcribing'}
                    isComplete={currentStepIndex() > 2}
                  />
                  <StatusStep 
                    title="Анализ и Саммери" 
                    desc="Создаем протокол с помощью YandexGPT" 
                    icon={<FileText size={18} />}
                    isActive={status?.status === 'generating'}
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
                    title="Отправка" 
                    desc="Формируем DOCX и отправляем на email" 
                    icon={<Mail size={18} />}
                    isActive={status?.status === 'emailing'}
                    isComplete={currentStepIndex() > 5}
                  />
                </div>

                {status?.status === 'completed' && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ marginTop: '3rem' }}
                  >
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                      <CheckCircle2 size={48} />
                      <h3 style={{ fontSize: '1.5rem' }}>Протокол готов!</h3>
                      <p style={{ color: 'var(--text-muted)' }}>Файл сформирован и доступен для скачивания.</p>
                      <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                        <a 
                          href={`${API_BASE_URL}/download/${fileId}`} 
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
        </motion.div>
      </div>
    </>
  );
};

const StatusStep = ({ title, desc, icon, isActive, isComplete }) => (
  <div className={`status-step ${isActive ? 'active' : ''}`} style={{ opacity: isComplete || isActive ? 1 : 0.4 }}>
    <div className={`step-icon ${isComplete ? 'complete' : isActive ? 'active' : ''}`}>
      {isComplete ? <CheckCircle2 size={18} color="white" /> : icon}
    </div>
    <div className="step-content">
      <div className="step-title" style={{ color: isComplete ? 'var(--secondary)' : isActive ? 'var(--primary)' : 'inherit' }}>
        {title}
      </div>
      <div className="step-desc">{desc}</div>
    </div>
    {isActive && <Loader2 className="animate-spin" size={18} color="var(--primary)" />}
  </div>
);

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

export default App;
