import { useEffect, useState, useRef } from 'react';
import {
  Play,
  Pause,
  Square,
  SkipForward,
  Smartphone,
  Heart,
  Bookmark,
  MessageCircle,
  ShieldAlert,
  Sliders,
  Calendar,
  Activity,
  Tag,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

interface SessionStats {
  session_id: string;
  start_time: string;
  duration_seconds: number;
  videos_watched: number;
  likes_count: number;
  favorites_count: number;
  comments_viewed: number;
  ads_skipped: number;
  lives_skipped: number;
  niche_matched_count: number;
  current_action: string;
  current_dwell_remaining: number;
  current_caption: string;
  current_matched_keywords: string[];
  state: 'IDLE' | 'RUNNING' | 'PAUSED' | 'CAPTCHA_HALTED' | 'STOPPED';
}

interface DeviceStatus {
  connected: boolean;
  wda_alive: boolean;
  usb_devices_count: number;
  usb_devices: Array<{ serial: string; udid: string }>;
  screen_size: { width: number; height: number } | null;
}

export default function App() {
  const [device, setDevice] = useState<DeviceStatus | null>(null);
  const [stats, setStats] = useState<SessionStats>({
    session_id: '',
    start_time: '',
    duration_seconds: 0,
    videos_watched: 0,
    likes_count: 0,
    favorites_count: 0,
    comments_viewed: 0,
    ads_skipped: 0,
    lives_skipped: 0,
    niche_matched_count: 0,
    current_action: 'System Ready',
    current_dwell_remaining: 0,
    current_caption: '',
    current_matched_keywords: [],
    state: 'IDLE',
  });
  const [screenB64, setScreenB64] = useState<string | null>(null);
  const [autoMirror, setAutoMirror] = useState<boolean>(true);
  const [isFetchingScreen, setIsFetchingScreen] = useState<boolean>(false);
  const [config, setConfig] = useState<any>(null);
  const [selectedDuration, setSelectedDuration] = useState<number>(15);
  const [activeTab, setActiveTab] = useState<'activity' | 'niche' | 'behavior' | 'schedule'>('activity');
  const [activityLogs, setActivityLogs] = useState<Array<{ time: string; msg: string; type: string }>>([]);
  const [newKeyword, setNewKeyword] = useState('');
  const [newSeedTerm, setNewSeedTerm] = useState('');
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch initial status and config
  useEffect(() => {
    fetchStatus();
    fetchConfig();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket for real-time screen stream and telemetry
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    function connectWs() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'stats') {
            setStats((prev) => {
              if (payload.data.current_action && payload.data.current_action !== prev.current_action) {
                setActivityLogs((logs) => [
                  {
                    time: new Date().toLocaleTimeString(),
                    msg: payload.data.current_action,
                    type: payload.data.current_action.includes('Like')
                      ? 'like'
                      : payload.data.current_action.includes('Ad')
                      ? 'ad'
                      : 'info',
                  },
                  ...logs.slice(0, 50),
                ]);
              }
              return { ...prev, ...payload.data };
            });
          } else if (payload.type === 'screen' && payload.image) {
            setScreenB64(payload.image);
          }
        } catch (e) {
          console.error('WS Parse Error', e);
        }
      };

      ws.onclose = () => {
        setTimeout(connectWs, 2000);
      };
    }

    connectWs();
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const fetchScreen = async () => {
    try {
      setIsFetchingScreen(true);
      const res = await fetch('/api/actions/capture-screen', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.image) setScreenB64(data.image);
      }
    } catch (e) {
      console.debug('Screen fetch error', e);
    } finally {
      setIsFetchingScreen(false);
    }
  };

  // Auto-mirror effect: periodic capture when active or on mount
  useEffect(() => {
    fetchScreen();
    const timer = setInterval(() => {
      if (autoMirror) {
        fetchScreen();
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [autoMirror]);

  // Refresh screen immediately when video changes or action starts
  useEffect(() => {
    if (stats.videos_watched > 0 || stats.state === 'RUNNING') {
      fetchScreen();
    }
  }, [stats.videos_watched, stats.state]);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        setDevice(data.device);
        if (data.session) {
          setStats((prev) => ({ ...prev, ...data.session }));
        }
      }
    } catch (e) {
      console.debug('Status fetch error', e);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (e) {
      console.debug('Config fetch error', e);
    }
  };

  const handleStart = async () => {
    await fetch(`/api/actions/start?duration_minutes=${selectedDuration}`, { method: 'POST' });
    fetchStatus();
  };

  const handlePause = async () => {
    await fetch('/api/actions/pause', { method: 'POST' });
    fetchStatus();
  };

  const handleResume = async () => {
    await fetch('/api/actions/resume', { method: 'POST' });
    fetchStatus();
  };

  const handleStop = async () => {
    await fetch('/api/actions/stop', { method: 'POST' });
    fetchStatus();
  };

  const handleSkip = async () => {
    await fetch('/api/actions/skip', { method: 'POST' });
  };

  const handleTestSwipe = async () => {
    await fetch('/api/actions/test-swipe', { method: 'POST' });
  };

  const handleTestLike = async () => {
    await fetch('/api/actions/test-like', { method: 'POST' });
  };

  const handleSaveConfig = async () => {
    if (!config) return;
    setIsSavingConfig(true);
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      fetchConfig();
    } finally {
      setIsSavingConfig(false);
    }
  };

  const addKeyword = () => {
    if (!newKeyword.trim() || !config) return;
    const current = config.niche.target_keywords || [];
    if (!current.includes(newKeyword.trim())) {
      setConfig({
        ...config,
        niche: { ...config.niche, target_keywords: [...current, newKeyword.trim().toLowerCase()] },
      });
    }
    setNewKeyword('');
  };

  const removeKeyword = (kw: string) => {
    if (!config) return;
    setConfig({
      ...config,
      niche: {
        ...config.niche,
        target_keywords: config.niche.target_keywords.filter((k: string) => k !== kw),
      },
    });
  };

  const addSeedTerm = () => {
    if (!newSeedTerm.trim() || !config) return;
    const current = config.niche.seed_terms || [];
    if (!current.includes(newSeedTerm.trim())) {
      setConfig({
        ...config,
        niche: { ...config.niche, seed_terms: [...current, newSeedTerm.trim()] },
      });
    }
    setNewSeedTerm('');
  };

  const removeSeedTerm = (term: string) => {
    if (!config) return;
    setConfig({
      ...config,
      niche: {
        ...config.niche,
        seed_terms: config.niche.seed_terms.filter((t: string) => t !== term),
      },
    });
  };

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
  };

  const matchRate =
    stats.videos_watched > 0
      ? Math.round((stats.niche_matched_count / stats.videos_watched) * 100)
      : 0;

  return (
    <div className="min-h-screen bg-[#090a0f] text-gray-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-gray-800 bg-[#0e1017] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#fe2c55] to-[#25f4ee] flex items-center justify-center p-0.5 shadow-lg shadow-pink-500/20">
            <div className="w-full h-full bg-[#0e1017] rounded-[10px] flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              TikTok iOS Automation <span className="text-xs px-2 py-0.5 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20">WDA Core</span>
            </h1>
            <p className="text-xs text-gray-400">Biometric Emulation & Account Warming Suite</p>
          </div>
        </div>

        {/* Device Connectivity Status */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
            <Smartphone className="w-4 h-4 text-gray-400" />
            <span className="text-gray-300">
              iPhone: {device?.connected ? (
                <span className="text-emerald-400 font-semibold inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> WDA Online
                </span>
              ) : (
                <span className="text-amber-400 font-semibold inline-flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> WDA Offline (Port 8100)
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleTestSwipe}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 transition border border-gray-700"
              title="Test biometric swipe gesture on iPhone"
            >
              Test Swipe
            </button>
            <button
              onClick={handleTestLike}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-pink-400 transition border border-gray-700"
              title="Test double tap like on iPhone"
            >
              Test Like ❤️
            </button>
          </div>
        </div>
      </header>

      {/* Captcha Alert Banner */}
      {stats.state === 'CAPTCHA_HALTED' && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-3 flex items-center justify-between text-amber-300 text-sm animate-pulse">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <span>
              <strong>Security Challenge Detected:</strong> TikTok requested an interactive verification or captcha. Automation is safely paused. Please complete it on your iPhone.
            </span>
          </div>
          <button
            onClick={handleResume}
            className="px-4 py-1.5 rounded-lg bg-amber-500 text-black font-semibold text-xs hover:bg-amber-400 transition shadow"
          >
            I Solved It, Resume Session
          </button>
        </div>
      )}

      {/* Main Grid Workspace */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-7xl mx-auto w-full">
        {/* Left Column: iPhone Screen Mirror & Session Controls (5 cols) */}
        <div className="lg:col-span-5 flex flex-col items-center">
          {/* Mirror Header Controls */}
          <div className="w-[340px] flex items-center justify-between mb-2 px-1">
            <span className="text-xs font-medium text-gray-400 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${screenB64 ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
              Display Mirror
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setAutoMirror(!autoMirror)}
                className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium border transition ${
                  autoMirror
                    ? 'bg-pink-500/20 text-pink-400 border-pink-500/30'
                    : 'bg-gray-800 text-gray-400 border-gray-700'
                }`}
              >
                {autoMirror ? 'Auto (2s) ON' : 'Auto OFF'}
              </button>
              <button
                onClick={fetchScreen}
                title="Refresh Screen"
                className="p-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetchingScreen ? 'animate-spin text-pink-400' : ''}`} />
              </button>
            </div>
          </div>

          {/* iPhone Mockup Frame */}
          <div className="relative w-[340px] h-[690px] bg-black rounded-[48px] p-3 shadow-2xl border-4 border-gray-700 ring-1 ring-gray-600/30 flex flex-col items-center">
            {/* Dynamic Island / Speaker */}
            <div className="w-24 h-6 bg-black rounded-full absolute top-5 z-20 flex items-center justify-center">
              <div className="w-3 h-3 rounded-full bg-gray-900 ml-auto mr-2" />
            </div>

            {/* Screen Inner Display */}
            <div className="w-full h-full bg-[#12131a] rounded-[38px] overflow-hidden relative flex flex-col justify-between">
              {screenB64 ? (
                <img
                  src={`data:image/jpeg;base64,${screenB64}`}
                  alt="Live iPhone Screen"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div
                  onClick={fetchScreen}
                  className="flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-500 cursor-pointer hover:bg-white/[0.02] transition"
                >
                  <Smartphone className="w-16 h-16 stroke-1 text-gray-600 mb-3" />
                  <p className="text-sm font-medium text-gray-400">Live Mirror Standby</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Click to load screen snapshot
                  </p>
                </div>
              )}

              {/* Live Overlay: Status & Action Pills */}
              <div className="absolute top-10 left-3 right-3 flex items-center justify-between pointer-events-none z-10">
                <span
                  className={`px-2.5 py-1 rounded-full text-[11px] font-semibold backdrop-blur-md shadow ${
                    stats.state === 'RUNNING'
                      ? 'bg-emerald-500/80 text-white'
                      : stats.state === 'PAUSED'
                      ? 'bg-amber-500/80 text-white'
                      : stats.state === 'CAPTCHA_HALTED'
                      ? 'bg-red-500/80 text-white'
                      : 'bg-gray-800/80 text-gray-300'
                  }`}
                >
                  {stats.state}
                </span>

                {stats.current_dwell_remaining > 0 && (
                  <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-black/70 backdrop-blur-md text-pink-400 border border-pink-500/30 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {stats.current_dwell_remaining.toFixed(1)}s
                  </span>
                )}
              </div>

              {/* Bottom Caption Overlay */}
              {stats.current_caption && (
                <div className="absolute bottom-4 left-3 right-3 bg-black/85 backdrop-blur-md p-3 rounded-2xl border border-gray-800 text-xs text-gray-200 z-10 pointer-events-none">
                  <p className="line-clamp-2 leading-relaxed text-gray-300">{stats.current_caption}</p>
                  {stats.current_matched_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {stats.current_matched_keywords.map((kw, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-400 text-[10px] font-medium border border-pink-500/30">
                          #{kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Session Controller Panel */}
          <div className="w-[340px] mt-4 bg-[#12131a] border border-gray-800 p-4 rounded-2xl flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400 font-medium">Session Duration:</span>
              <select
                value={selectedDuration}
                onChange={(e) => setSelectedDuration(Number(e.target.value))}
                disabled={stats.state === 'RUNNING'}
                className="bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-1 focus:ring-1 focus:ring-pink-500 outline-none"
              >
                <option value={10}>10 Minutes</option>
                <option value={15}>15 Minutes</option>
                <option value={20}>20 Minutes</option>
                <option value={30}>30 Minutes</option>
                <option value={45}>45 Minutes</option>
              </select>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2">
              {stats.state === 'RUNNING' ? (
                <button
                  onClick={handlePause}
                  className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 text-xs font-semibold transition"
                >
                  <Pause className="w-4 h-4" /> Pause
                </button>
              ) : stats.state === 'PAUSED' ? (
                <button
                  onClick={handleResume}
                  className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition"
                >
                  <Play className="w-4 h-4" /> Resume
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white shadow-lg shadow-pink-500/20 text-xs font-semibold transition"
                >
                  <Play className="w-4 h-4 fill-current" /> Start Warming
                </button>
              )}

              <button
                onClick={handleStop}
                disabled={stats.state === 'IDLE' || stats.state === 'STOPPED'}
                className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 text-xs font-semibold transition disabled:opacity-40"
              >
                <Square className="w-3.5 h-3.5 fill-current" /> Stop
              </button>
            </div>

            <button
              onClick={handleSkip}
              disabled={stats.state !== 'RUNNING'}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-800 text-xs font-medium transition disabled:opacity-40"
            >
              <SkipForward className="w-3.5 h-3.5" /> Skip Current Video Now
            </button>

            <button
              onClick={async () => {
                const res = await fetch('/api/actions/capture-screen', { method: 'POST' });
                if (res.ok) {
                  const data = await res.json();
                  if (data.image) setScreenB64(data.image);
                }
              }}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-gray-900 hover:bg-gray-800 text-gray-400 border border-gray-800 text-xs font-medium transition"
            >
              <Smartphone className="w-3.5 h-3.5 text-pink-400" /> Capture Screen Snapshot
            </button>
          </div>
        </div>

        {/* Right Column: Telemetry, Tabs & Configuration (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-gray-400 font-medium">Videos Watched</span>
              <span className="text-2xl font-bold text-white mt-1">{stats.videos_watched}</span>
              <span className="text-[11px] text-gray-500 mt-1">{formatSeconds(stats.duration_seconds)} active</span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-pink-400 font-medium flex items-center gap-1.5">
                <Heart className="w-3.5 h-3.5 fill-pink-500 text-pink-500" /> Likes Given
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.likes_count}</span>
              <span className="text-[11px] text-gray-500 mt-1">
                {stats.videos_watched > 0 ? `${Math.round((stats.likes_count / stats.videos_watched) * 100)}% like rate` : '0%'}
              </span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-amber-400 font-medium flex items-center gap-1.5">
                <Bookmark className="w-3.5 h-3.5 fill-amber-500 text-amber-500" /> Bookmarked
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.favorites_count}</span>
              <span className="text-[11px] text-gray-500 mt-1">Organically saved</span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-cyan-400 font-medium flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> Niche Match Rate
              </span>
              <span className="text-2xl font-bold text-white mt-1">{matchRate}%</span>
              <span className="text-[11px] text-gray-500 mt-1">{stats.niche_matched_count} niche videos</span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-purple-400 font-medium flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5 text-purple-400" /> Comments Read
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.comments_viewed}</span>
              <span className="text-[11px] text-gray-500 mt-1">Drawer inspections</span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-emerald-400 font-medium flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-emerald-400" /> Ads Fast-Skipped
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.ads_skipped}</span>
              <span className="text-[11px] text-gray-500 mt-1">Filtered promotions</span>
            </div>
          </div>

          {/* Configuration & Tabs Card */}
          <div className="flex-1 bg-[#12131a] border border-gray-800 rounded-2xl flex flex-col overflow-hidden">
            {/* Tab Selector */}
            <div className="flex border-b border-gray-800 bg-gray-900/40 px-4 pt-3 gap-2">
              <button
                onClick={() => setActiveTab('activity')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-xl transition ${
                  activeTab === 'activity'
                    ? 'bg-[#12131a] text-pink-400 border-t border-x border-gray-800'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Activity className="w-3.5 h-3.5" /> Activity Stream
              </button>

              <button
                onClick={() => setActiveTab('niche')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-xl transition ${
                  activeTab === 'niche'
                    ? 'bg-[#12131a] text-pink-400 border-t border-x border-gray-800'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Tag className="w-3.5 h-3.5" /> Niche Targeting
              </button>

              <button
                onClick={() => setActiveTab('behavior')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-xl transition ${
                  activeTab === 'behavior'
                    ? 'bg-[#12131a] text-pink-400 border-t border-x border-gray-800'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Sliders className="w-3.5 h-3.5" /> Dwell & Probabilities
              </button>

              <button
                onClick={() => setActiveTab('schedule')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-xl transition ${
                  activeTab === 'schedule'
                    ? 'bg-[#12131a] text-pink-400 border-t border-x border-gray-800'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Calendar className="w-3.5 h-3.5" /> Daily Routine
              </button>
            </div>

            {/* Tab Contents */}
            <div className="flex-1 p-5 overflow-y-auto">
              {/* Activity Log Tab */}
              {activeTab === 'activity' && (
                <div className="flex flex-col h-full">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-gray-300">Live Emulation Events</span>
                    <span className="text-[11px] text-gray-500">Latest 50 actions</span>
                  </div>
                  <div className="space-y-2 font-mono text-xs max-h-[360px] overflow-y-auto pr-1">
                    {activityLogs.length === 0 ? (
                      <p className="text-gray-500 text-xs italic py-8 text-center">No actions recorded yet. Start a session to see real-time events.</p>
                    ) : (
                      activityLogs.map((log, i) => (
                        <div
                          key={i}
                          className={`p-2 rounded-lg border flex items-center justify-between ${
                            log.type === 'like'
                              ? 'bg-pink-500/10 border-pink-500/20 text-pink-300'
                              : log.type === 'ad'
                              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                              : 'bg-gray-900 border-gray-800 text-gray-300'
                          }`}
                        >
                          <span>{log.msg}</span>
                          <span className="text-[10px] text-gray-500 ml-2">{log.time}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* Niche Targeting Tab */}
              {activeTab === 'niche' && config && (
                <div className="space-y-5">
                  <div>
                    <label className="text-xs font-semibold text-gray-300 block mb-1.5">
                      Target Niche Keywords (OCR matches in captions boost dwell & like rates)
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        placeholder="e.g. artificial intelligence, web3, fitness..."
                        value={newKeyword}
                        onChange={(e) => setNewKeyword(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
                        className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 outline-none focus:border-pink-500"
                      />
                      <button
                        onClick={addKeyword}
                        className="px-3 py-2 bg-pink-600 hover:bg-pink-500 text-white rounded-lg text-xs font-medium transition"
                      >
                        Add Tag
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto">
                      {(config.niche.target_keywords || []).map((kw: string) => (
                        <span
                          key={kw}
                          className="px-2.5 py-1 rounded-lg bg-gray-800 text-pink-400 border border-gray-700 text-xs flex items-center gap-1.5"
                        >
                          #{kw}
                          <button
                            onClick={() => removeKeyword(kw)}
                            className="text-gray-500 hover:text-red-400"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="border-t border-gray-800 pt-4">
                    <label className="text-xs font-semibold text-gray-300 block mb-1.5">
                      Initial Search Seeding Terms (Searches these queries to steer FYP algorithm)
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        placeholder="e.g. tech gadgets, coding tutorials..."
                        value={newSeedTerm}
                        onChange={(e) => setNewSeedTerm(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addSeedTerm()}
                        className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 outline-none focus:border-pink-500"
                      />
                      <button
                        onClick={addSeedTerm}
                        className="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg text-xs font-medium transition"
                      >
                        Add Term
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(config.niche.seed_terms || []).map((term: string) => (
                        <span
                          key={term}
                          className="px-2.5 py-1 rounded-lg bg-gray-900 text-cyan-300 border border-cyan-500/20 text-xs flex items-center gap-1.5"
                        >
                          🔍 {term}
                          <button
                            onClick={() => removeSeedTerm(term)}
                            className="text-gray-500 hover:text-red-400"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleSaveConfig}
                    disabled={isSavingConfig}
                    className="w-full py-2.5 bg-gradient-to-r from-pink-600 to-rose-600 text-white rounded-xl text-xs font-semibold hover:opacity-90 transition disabled:opacity-50"
                  >
                    {isSavingConfig ? 'Saving...' : 'Apply Niche Settings'}
                  </button>
                </div>
              )}

              {/* Behavior & Probabilities Tab */}
              {activeTab === 'behavior' && config && (
                <div className="space-y-4 text-xs">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-gray-300">Mean Dwell Time: {config.dwell_time.mean_seconds}s</span>
                      <span className="text-gray-500">Range: {config.dwell_time.min_seconds}s - {config.dwell_time.max_seconds}s</span>
                    </div>
                    <input
                      type="range"
                      min={6}
                      max={25}
                      step={1}
                      value={config.dwell_time.mean_seconds}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          dwell_time: { ...config.dwell_time, mean_seconds: Number(e.target.value) },
                        })
                      }
                      className="w-full accent-pink-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-gray-300">Niche Dwell Multiplier: {config.dwell_time.niche_match_multiplier}x</span>
                      <span className="text-gray-500">Watches longer if tags match</span>
                    </div>
                    <input
                      type="range"
                      min={1.2}
                      max={3.0}
                      step={0.1}
                      value={config.dwell_time.niche_match_multiplier}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          dwell_time: { ...config.dwell_time, niche_match_multiplier: Number(e.target.value) },
                        })
                      }
                      className="w-full accent-pink-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4 border-t border-gray-800 pt-3">
                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-300">Like (Base): {Math.round(config.probabilities.like_base * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min={0.02}
                        max={0.25}
                        step={0.01}
                        value={config.probabilities.like_base}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            probabilities: { ...config.probabilities, like_base: Number(e.target.value) },
                          })
                        }
                        className="w-full accent-pink-500"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-pink-400 font-semibold">Like (Niche): {Math.round(config.probabilities.like_niche * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min={0.2}
                        max={0.8}
                        step={0.02}
                        value={config.probabilities.like_niche}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            probabilities: { ...config.probabilities, like_niche: Number(e.target.value) },
                          })
                        }
                        className="w-full accent-pink-500"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-300">Favorite (Niche): {Math.round(config.probabilities.favorite_niche * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min={0.05}
                        max={0.35}
                        step={0.01}
                        value={config.probabilities.favorite_niche}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            probabilities: { ...config.probabilities, favorite_niche: Number(e.target.value) },
                          })
                        }
                        className="w-full accent-amber-500"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-300">Read Comments: {Math.round(config.probabilities.comment_drawer_view_niche * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min={0.05}
                        max={0.4}
                        step={0.01}
                        value={config.probabilities.comment_drawer_view_niche}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            probabilities: { ...config.probabilities, comment_drawer_view_niche: Number(e.target.value) },
                          })
                        }
                        className="w-full accent-purple-500"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleSaveConfig}
                    disabled={isSavingConfig}
                    className="w-full py-2.5 bg-gradient-to-r from-pink-600 to-rose-600 text-white rounded-xl text-xs font-semibold hover:opacity-90 transition mt-2 disabled:opacity-50"
                  >
                    {isSavingConfig ? 'Saving...' : 'Apply Probability Settings'}
                  </button>
                </div>
              )}

              {/* Schedule Tab */}
              {activeTab === 'schedule' && (
                <div className="space-y-4 text-xs">
                  <div className="p-3 bg-gray-900 border border-gray-800 rounded-xl">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-200">Autonomous Daily Routine</span>
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium text-[10px]">
                        Active (3 Sessions/Day)
                      </span>
                    </div>
                    <p className="text-gray-400 mt-1 leading-relaxed text-[11px]">
                      The engine automatically wakes up during natural daily human windows with randomized start jitter (±20 mins) to browse FYP.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex items-center justify-between">
                      <div>
                        <span className="font-semibold text-gray-200 block">Morning Session</span>
                        <span className="text-[11px] text-gray-500">08:30 - 10:15 Window • 12-24 mins</span>
                      </div>
                      <span className="text-xs text-gray-400">Scheduled</span>
                    </div>

                    <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex items-center justify-between">
                      <div>
                        <span className="font-semibold text-gray-200 block">Lunch Session</span>
                        <span className="text-[11px] text-gray-500">12:45 - 14:30 Window • 12-24 mins</span>
                      </div>
                      <span className="text-xs text-gray-400">Scheduled</span>
                    </div>

                    <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex items-center justify-between">
                      <div>
                        <span className="font-semibold text-gray-200 block">Evening Session</span>
                        <span className="text-[11px] text-gray-500">19:30 - 22:15 Window • 15-30 mins</span>
                      </div>
                      <span className="text-xs text-gray-400">Scheduled</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
