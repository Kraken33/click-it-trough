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
  Search,
  Shuffle,
  UserPlus,
  BarChart3,
  Download,
  History,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Trash2,
  FileText,
} from 'lucide-react';

interface AnalyticsSummary {
  lifetime: {
    total_sessions: number;
    total_duration_seconds: number;
    total_videos_watched: number;
    total_likes: number;
    total_favorites: number;
    total_comments: number;
    total_follows: number;
    total_ads_skipped: number;
    total_lives_skipped: number;
    total_niche_matched: number;
    like_rate_percent: number;
    favorite_rate_percent: number;
    follow_rate_percent: number;
    niche_match_rate_percent: number;
    avg_niche_dwell_seconds: number;
    avg_generic_dwell_seconds: number;
  };
  today: {
    today_sessions: number;
    today_duration_seconds: number;
    today_videos_watched: number;
    today_likes: number;
    today_favorites: number;
    today_follows: number;
  };
  warming_health_score: {
    score: number;
    rating: string;
    factors: {
      niche_alignment: { score: number; weight: number; value_percent?: number; details: string };
      engagement_balance: { score: number; weight: number; value_percent?: number; details: string };
      dwell_differentiation: { score: number; weight: number; ratio?: number; details: string };
      session_stability: { score: number; weight: number; clean_rate_percent?: number; details: string };
    };
  };
}

interface AnalyticsTrends {
  session_progression: Array<{
    session_id: string;
    start_time: string;
    duration_seconds: number;
    videos_watched: number;
    likes_count: number;
    favorites_count: number;
    follows_count: number;
    niche_matched_count: number;
    niche_match_rate: number;
    state: string;
  }>;
  top_keywords: Array<{
    keyword: string;
    count: number;
  }>;
}

interface VideoInteraction {
  id: number;
  session_id: string;
  timestamp: string;
  caption: string;
  matched_keywords: string[];
  is_niche: boolean;
  is_ad: boolean;
  is_live: boolean;
  dwell_time_seconds: number;
  action_liked: boolean;
  action_favorited: boolean;
  action_comment_viewed: boolean;
  action_followed: boolean;
  action_skipped_early: boolean;
}

interface SavedSession {
  session_id: string;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  state: string;
  videos_watched: number;
  likes_count: number;
  favorites_count: number;
  comments_viewed: number;
  follows_count: number;
  session_follow_target: number;
  ads_skipped: number;
  lives_skipped: number;
  niche_matched_count: number;
  niche_match_rate: number;
  target_keywords: string[];
  exit_reason: string;
  videos?: VideoInteraction[];
}

function formatDuration(totalSeconds: number): string {
  if (!totalSeconds || totalSeconds <= 0) return '0s';
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

interface SessionStats {
  session_id: string;
  start_time: string;
  duration_seconds: number;
  videos_watched: number;
  likes_count: number;
  favorites_count: number;
  comments_viewed: number;
  follows_count: number;
  session_follow_target: number;
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

function RangeField({
  label,
  sublabel,
  minVal,
  maxVal,
  step = 0.1,
  minLimit = 0,
  maxLimit = 100,
  unit = '',
  isPercent = false,
  badgeColor = 'pink',
  onChange,
}: {
  label: string;
  sublabel?: string;
  minVal: number;
  maxVal: number;
  step?: number;
  minLimit?: number;
  maxLimit?: number;
  unit?: string;
  isPercent?: boolean;
  badgeColor?: 'pink' | 'purple' | 'cyan' | 'amber' | 'emerald';
  onChange: (newMin: number, newMax: number) => void;
}) {
  const badgeClasses =
    badgeColor === 'purple'
      ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
      : badgeColor === 'cyan'
      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
      : badgeColor === 'amber'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
      : badgeColor === 'emerald'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
      : 'bg-pink-500/20 text-pink-300 border-pink-500/30';

  const accentColor =
    badgeColor === 'purple'
      ? 'accent-purple-500'
      : badgeColor === 'cyan'
      ? 'accent-cyan-500'
      : badgeColor === 'amber'
      ? 'accent-amber-500'
      : badgeColor === 'emerald'
      ? 'accent-emerald-500'
      : 'accent-pink-500';

  const safeMin = Number(minVal ?? minLimit);
  const safeMax = Number(maxVal ?? maxLimit);

  return (
    <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-gray-200">{label}</span>
          {sublabel && <p className="text-[11px] text-gray-400 mt-0.5">{sublabel}</p>}
        </div>
        <span className={`text-[11px] font-mono font-medium px-2 py-0.5 rounded border ${badgeClasses}`}>
          {isPercent
            ? `${Math.round(safeMin * 100)}% – ${Math.round(safeMax * 100)}%`
            : `${safeMin}${unit} – ${safeMax}${unit}`}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[11px] text-gray-400">
            <span>Min</span>
            <input
              type="number"
              step={step}
              min={minLimit}
              max={safeMax}
              value={isPercent ? Math.round(safeMin * 100) : safeMin}
              onChange={(e) => {
                const val = Number(e.target.value);
                const n = isPercent ? val / 100 : val;
                onChange(Math.min(n, safeMax), safeMax);
              }}
              className="w-14 bg-gray-950 border border-gray-700 text-right text-gray-200 px-1.5 py-0.5 rounded text-xs outline-none focus:border-pink-500"
            />
          </div>
          <input
            type="range"
            step={step}
            min={minLimit}
            max={maxLimit}
            value={safeMin}
            onChange={(e) => {
              const val = Number(e.target.value);
              onChange(Math.min(val, safeMax), safeMax);
            }}
            className={`${accentColor} w-full cursor-pointer`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[11px] text-gray-400">
            <span>Max</span>
            <input
              type="number"
              step={step}
              min={safeMin}
              max={maxLimit}
              value={isPercent ? Math.round(safeMax * 100) : safeMax}
              onChange={(e) => {
                const val = Number(e.target.value);
                const n = isPercent ? val / 100 : val;
                onChange(safeMin, Math.max(n, safeMin));
              }}
              className="w-14 bg-gray-950 border border-gray-700 text-right text-gray-200 px-1.5 py-0.5 rounded text-xs outline-none focus:border-pink-500"
            />
          </div>
          <input
            type="range"
            step={step}
            min={minLimit}
            max={maxLimit}
            value={safeMax}
            onChange={(e) => {
              const val = Number(e.target.value);
              onChange(safeMin, Math.max(val, safeMin));
            }}
            className={`${accentColor} w-full cursor-pointer`}
          />
        </div>
      </div>
    </div>
  );
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
    follows_count: 0,
    session_follow_target: 0,
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
  const [activeTab, setActiveTab] = useState<'activity' | 'niche' | 'behavior' | 'schedule' | 'analytics'>('activity');
  const [analyticsSummary, setAnalyticsSummary] = useState<AnalyticsSummary | null>(null);
  const [analyticsTrends, setAnalyticsTrends] = useState<AnalyticsTrends | null>(null);
  const [sessionsList, setSessionsList] = useState<SavedSession[]>([]);
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
  const [sessionDetails, setSessionDetails] = useState<Record<string, SavedSession>>({});
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState<boolean>(false);
  const [isLoadingSessionDetail, setIsLoadingSessionDetail] = useState<boolean>(false);
  const [activityLogs, setActivityLogs] = useState<Array<{ time: string; msg: string; type: string }>>([]);
  const [newKeyword, setNewKeyword] = useState('');
  const [newSeedTerm, setNewSeedTerm] = useState('');
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [isSearching, setIsSearching] = useState(false);
  const [activeSearchTerm, setActiveSearchTerm] = useState<string | null>(null);
  const [isTestingTags, setIsTestingTags] = useState(false);
  const [tagTestResult, setTagTestResult] = useState<any | null>(null);
  const [isTestingComment, setIsTestingComment] = useState(false);
  const [isClosingApp, setIsClosingApp] = useState(false);
  const [isTestingSwipe, setIsTestingSwipe] = useState(false);
  const [isRecoveringFeed, setIsRecoveringFeed] = useState(false);

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
                      : payload.data.current_action.includes('Niche')
                      ? 'niche'
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

  const fetchAnalyticsData = async () => {
    setIsLoadingAnalytics(true);
    try {
      const [sumRes, trRes, sessRes] = await Promise.all([
        fetch('/api/analytics/summary'),
        fetch('/api/analytics/trends'),
        fetch('/api/sessions?limit=50'),
      ]);
      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setAnalyticsSummary(sumData);
      }
      if (trRes.ok) {
        const trData = await trRes.json();
        setAnalyticsTrends(trData);
      }
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        setSessionsList(sessData.sessions || []);
      }
    } catch (e) {
      console.error('Failed to fetch analytics:', e);
    } finally {
      setIsLoadingAnalytics(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'analytics') {
      fetchAnalyticsData();
    }
  }, [activeTab]);

  const handleToggleExpandSession = async (sessionId: string) => {
    if (expandedSessionId === sessionId) {
      setExpandedSessionId(null);
      return;
    }
    setExpandedSessionId(sessionId);
    if (!sessionDetails[sessionId]) {
      setIsLoadingSessionDetail(true);
      try {
        const res = await fetch(`/api/sessions/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          setSessionDetails((prev) => ({ ...prev, [sessionId]: data }));
        }
      } catch (e) {
        console.error('Failed to load session details:', e);
      } finally {
        setIsLoadingSessionDetail(false);
      }
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete session record ${sessionId}?`)) return;
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      fetchAnalyticsData();
      if (expandedSessionId === sessionId) {
        setExpandedSessionId(null);
      }
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const handleClearAllSessions = async () => {
    if (!confirm('Are you sure you want to delete ALL historical sessions and video interaction logs? This cannot be undone.')) return;
    try {
      await fetch('/api/sessions', { method: 'DELETE' });
      fetchAnalyticsData();
      setExpandedSessionId(null);
      setSessionDetails({});
    } catch (err) {
      console.error('Error clearing sessions:', err);
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
    setIsSearching(false);
    setActiveSearchTerm(null);
    await fetch('/api/actions/stop', { method: 'POST' });
    fetchStatus();
  };

  const handleTestTags = async () => {
    try {
      setIsTestingTags(true);
      const res = await fetch('/api/actions/test-tags', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setTagTestResult(data);
        if (data.image) {
          setScreenB64(data.image);
        }
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: data.is_niche
              ? `🎯 Test on Tags: Match [${data.matched_keywords.join(', ')}] (Score: ${data.score})`
              : `⚠️ Test on Tags: No match detected on screen`,
            type: data.is_niche ? 'niche' : 'info',
          },
          ...logs.slice(0, 50),
        ]);
      } else {
        const err = await res.json().catch(() => ({ detail: 'Device unreachable' }));
        alert(`Test on Tags failed: ${err.detail || 'Device unreachable'}`);
      }
    } catch (e: any) {
      console.error('Test on tags error', e);
      alert(`Test on Tags error: ${e.message}`);
    } finally {
      setIsTestingTags(false);
    }
  };

  const handleSkip = async () => {
    await fetch('/api/actions/skip', { method: 'POST' });
  };

  const handleTestSwipe = async () => {
    if (isTestingSwipe) return;
    try {
      setIsTestingSwipe(true);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: "👆 Testing swipe gesture (verifying video change via likes)...",
          type: "info",
        },
        ...logs.slice(0, 50),
      ]);
      const res = await fetch('/api/actions/test-swipe', { method: 'POST' });
      const data = await res.json().catch(() => ({ status: 'error' }));
      if (res.ok && data.status === 'ok') {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `✅ Swipe verified successful! [${data.details || 'Video changed'}]`,
            type: "info",
          },
          ...logs.slice(0, 50),
        ]);
        fetchScreen();
      } else {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `⚠️ Swipe verification: ${data.details || 'Video did not change'}`,
            type: "ad",
          },
          ...logs.slice(0, 50),
        ]);
      }
    } catch (e: any) {
      console.error('Test swipe error', e);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: `❌ Error running swipe test: ${e.message}`,
          type: "ad",
        },
        ...logs.slice(0, 50),
      ]);
    } finally {
      setIsTestingSwipe(false);
    }
  };

  const handleTestLike = async () => {
    await fetch('/api/actions/test-like', { method: 'POST' });
  };

  const handleTestComment = async () => {
    if (isTestingComment) return;
    try {
      setIsTestingComment(true);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: "💬 Testing comment drawer (OCR verified)...",
          type: "info",
        },
        ...logs.slice(0, 50),
      ]);
      const res = await fetch('/api/actions/test-comment', { method: 'POST' });
      const data = await res.json().catch(() => ({ status: 'error', message: 'Invalid response' }));
      if (res.ok && data.status === 'ok') {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `✅ Comments verified open & closed via OCR`,
            type: "info",
          },
          ...logs.slice(0, 50),
        ]);
        fetchScreen();
      } else {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `⚠️ Comment test failed: ${data.message || data.detail || 'Could not verify'}. Opened: ${data.opened}, Closed: ${data.closed}`,
            type: "ad",
          },
          ...logs.slice(0, 50),
        ]);
      }
    } catch (e: any) {
      console.error('Test comment error', e);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: `❌ Error running comment test: ${e.message}`,
          type: "ad",
        },
        ...logs.slice(0, 50),
      ]);
    } finally {
      setIsTestingComment(false);
    }
  };

  const handleCloseApp = async () => {
    if (isClosingApp) return;
    try {
      setIsClosingApp(true);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: "📱 Closing TikTok & returning to iOS home screen (OCR verified)...",
          type: "info",
        },
        ...logs.slice(0, 50),
      ]);
      const res = await fetch('/api/actions/close-app', { method: 'POST' });
      if (res.ok) {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: "✅ TikTok closed and Home screen verified via OCR",
            type: "info",
          },
          ...logs.slice(0, 50),
        ]);
        fetchScreen();
      }
    } catch (e: any) {
      console.error('Close app error', e);
    } finally {
      setIsClosingApp(false);
    }
  };

  const handleRecoverFeed = async () => {
    if (isRecoveringFeed) return;
    try {
      setIsRecoveringFeed(true);
      setActivityLogs((logs) => [
        {
          time: new Date().toLocaleTimeString(),
          msg: "🔍 Detecting screen state and recovering to video feed...",
          type: "info",
        },
        ...logs.slice(0, 50),
      ]);
      const res = await fetch('/api/actions/recover-feed', { method: 'POST' });
      const data = await res.json().catch(() => ({ status: 'error' }));
      if (res.ok && data.status === 'ok') {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `✅ Returned to video feed (from ${data.state || 'overlay'})`,
            type: "info",
          },
          ...logs.slice(0, 50),
        ]);
        fetchScreen();
      } else {
        setActivityLogs((logs) => [
          {
            time: new Date().toLocaleTimeString(),
            msg: `⚠️ Feed recovery: ${data.state || 'Could not verify feed'}`,
            type: "ad",
          },
          ...logs.slice(0, 50),
        ]);
      }
    } catch (e: any) {
      console.error('Recover feed error', e);
    } finally {
      setIsRecoveringFeed(false);
    }
  };

  const handleTriggerSearch = async (term?: string) => {
    setIsSearching(true);
    setActiveSearchTerm(term || 'Niche Seeds');
    try {
      const url = term
        ? `/api/actions/trigger-search?term=${encodeURIComponent(term)}`
        : `/api/actions/trigger-search`;
      await fetch(url, { method: 'POST' });
    } catch (e) {
      console.error('Trigger search error', e);
    } finally {
      setTimeout(() => {
        setIsSearching(false);
        setActiveSearchTerm(null);
      }, 4000);
    }
  };

  const handleSaveConfig = async (newConfigToSave?: any) => {
    const cfg = newConfigToSave || config;
    if (!cfg) return;
    setIsSavingConfig(true);
    setSaveStatus('saving');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.config) {
          setConfig(data.config);
        }
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2500);
      } else {
        setSaveStatus('error');
      }
    } catch (e) {
      console.error('Failed to save config:', e);
      setSaveStatus('error');
    } finally {
      setIsSavingConfig(false);
    }
  };

  const parseBulkInput = (input: string, isKeyword: boolean = false): string[] => {
    if (!input || !input.trim()) return [];
    const raw = input.trim();
    let items: string[] = [];

    if (raw.includes('#')) {
      items = raw
        .split(/[\s,;\n]+/)
        .map((s) => s.replace(/^#+/, '').trim())
        .filter((s) => s.length > 0);
      if (items.length === 1 && items[0].includes('#')) {
        items = raw
          .split('#')
          .map((s) => s.trim())
          .filter((s) => s.length > 0);
      }
    } else if (/[,;\n]/.test(raw)) {
      items = raw
        .split(/[,;\n]+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    } else {
      items = [raw];
    }

    const cleaned: string[] = [];
    for (const item of items) {
      const val = isKeyword ? item.toLowerCase().trim() : item.trim();
      if (val && !cleaned.includes(val)) {
        cleaned.push(val);
      }
    }
    return cleaned;
  };

  const addKeyword = () => {
    if (!newKeyword.trim() || !config) return;
    const toAdd = parseBulkInput(newKeyword, true);
    if (toAdd.length === 0) return;

    const current = config.niche?.target_keywords || [];
    const newKeywords = toAdd.filter((kw) => !current.includes(kw));

    if (newKeywords.length > 0) {
      const updated = {
        ...config,
        niche: { ...config.niche, target_keywords: [...current, ...newKeywords] },
      };
      setConfig(updated);
      handleSaveConfig(updated);
    }
    setNewKeyword('');
  };

  const removeKeyword = (kw: string) => {
    if (!config) return;
    const updated = {
      ...config,
      niche: {
        ...config.niche,
        target_keywords: (config.niche?.target_keywords || []).filter((k: string) => k !== kw),
      },
    };
    setConfig(updated);
    handleSaveConfig(updated);
  };

  const clearAllKeywords = () => {
    if (!config) return;
    const updated = {
      ...config,
      niche: { ...config.niche, target_keywords: [] },
    };
    setConfig(updated);
    handleSaveConfig(updated);
  };

  const addSeedTerm = () => {
    if (!newSeedTerm.trim() || !config) return;
    const toAdd = parseBulkInput(newSeedTerm, false);
    if (toAdd.length === 0) return;

    const current = config.niche?.seed_terms || [];
    const newTerms = toAdd.filter((term) => !current.includes(term));

    if (newTerms.length > 0) {
      const updated = {
        ...config,
        niche: { ...config.niche, seed_terms: [...current, ...newTerms] },
      };
      setConfig(updated);
      handleSaveConfig(updated);
    }
    setNewSeedTerm('');
  };

  const removeSeedTerm = (term: string) => {
    if (!config) return;
    const updated = {
      ...config,
      niche: {
        ...config.niche,
        seed_terms: (config.niche?.seed_terms || []).filter((t: string) => t !== term),
      },
    };
    setConfig(updated);
    handleSaveConfig(updated);
  };

  const clearAllSeedTerms = () => {
    if (!config) return;
    const updated = {
      ...config,
      niche: { ...config.niche, seed_terms: [] },
    };
    setConfig(updated);
    handleSaveConfig(updated);
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
              onClick={handleTestTags}
              disabled={isTestingTags}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 transition border border-purple-500/30 flex items-center gap-1.5 shadow-sm shadow-purple-500/10"
              title="Capture current screen and test against niche tags using Apple Vision OCR"
            >
              {isTestingTags ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
                  Testing...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                  Test on Tags
                </>
              )}
            </button>
            <button
              onClick={handleTestSwipe}
              disabled={isTestingSwipe}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 transition border border-gray-700 flex items-center gap-1.5 ${isTestingSwipe ? 'opacity-70 cursor-not-allowed' : ''}`}
              title="Test biometric swipe gesture with likes verification on iPhone"
            >
              {isTestingSwipe ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-gray-400" />
                  Swiping...
                </>
              ) : (
                'Test Swipe 👆'
              )}
            </button>
            <button
              onClick={handleTestLike}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-pink-400 transition border border-gray-700"
              title="Test double tap like on iPhone"
            >
              Test Like ❤️
            </button>
            <button
              onClick={handleTestComment}
              disabled={isTestingComment}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-sky-400 transition border border-gray-700 flex items-center gap-1.5 ${isTestingComment ? 'opacity-70 cursor-not-allowed' : ''}`}
              title="Test opening and closing comment drawer on iPhone"
            >
              {isTestingComment ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-sky-400" />
                  Testing...
                </>
              ) : (
                'Test Comments 💬'
              )}
            </button>
            <button
              onClick={handleCloseApp}
              disabled={isClosingApp}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-amber-400 transition border border-gray-700 flex items-center gap-1.5 ${isClosingApp ? 'opacity-70 cursor-not-allowed' : ''}`}
              title="Close TikTok and return to iOS home screen"
            >
              {isClosingApp ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
                  Closing...
                </>
              ) : (
                'Close App 📱'
              )}
            </button>
            <button
              onClick={handleRecoverFeed}
              disabled={isRecoveringFeed}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-teal-400 transition border border-gray-700 flex items-center gap-1.5 ${isRecoveringFeed ? 'opacity-70 cursor-not-allowed' : ''}`}
              title="Detect page state (comments, share, profile, etc.) and return to TikTok video feed"
            >
              {isRecoveringFeed ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-400" />
                  Recovering...
                </>
              ) : (
                'Recover Feed 🔄'
              )}
            </button>
            {(stats.state === 'RUNNING' || stats.state === 'PAUSED' || isSearching) && (
              <button
                onClick={handleStop}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-600/30 flex items-center gap-1.5 transition animate-pulse"
                title="Stop current session or search action"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop
              </button>
            )}
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
                disabled={stats.state !== 'RUNNING' && stats.state !== 'PAUSED' && !isSearching}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-semibold transition ${
                  stats.state === 'RUNNING' || stats.state === 'PAUSED' || isSearching
                    ? 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/40 shadow-sm shadow-rose-500/10 cursor-pointer'
                    : 'bg-gray-800 text-gray-500 border-gray-700 opacity-40 cursor-not-allowed'
                }`}
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

            <button
              onClick={handleTestTags}
              disabled={isTestingTags}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 border border-purple-500/30 text-xs font-medium transition disabled:opacity-50 shadow-sm shadow-purple-500/10"
            >
              {isTestingTags ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" /> Analyzing Tags via OCR...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" /> Test Screen on Tags
                </>
              )}
            </button>

            <button
              onClick={() => handleTriggerSearch()}
              disabled={isSearching}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-gray-900 hover:bg-gray-800 text-cyan-300 border border-cyan-500/30 text-xs font-medium transition disabled:opacity-50"
            >
              {isSearching ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                  Seeding ({activeSearchTerm || 'Niche'})...
                </>
              ) : (
                <>
                  <Search className="w-3.5 h-3.5 text-cyan-400" /> Trigger Niche Search
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Telemetry, Tabs & Configuration (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
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
                <UserPlus className="w-3.5 h-3.5 text-emerald-400" /> Profiles Followed
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.follows_count}</span>
              <span className="text-[11px] text-gray-500 mt-1">
                Target: {stats.session_follow_target || (config?.follow?.follows_per_session_max ?? 3)} / session
              </span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-rose-400 font-medium flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> Ads Skipped
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.ads_skipped}</span>
              <span className="text-[11px] text-gray-500 mt-1">Filtered promotions</span>
            </div>

            <div className="bg-[#12131a] border border-gray-800/80 p-4 rounded-2xl flex flex-col">
              <span className="text-xs text-blue-400 font-medium flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-blue-400" /> Lives Skipped
              </span>
              <span className="text-2xl font-bold text-white mt-1">{stats.lives_skipped}</span>
              <span className="text-[11px] text-gray-500 mt-1">Fast-passed streams</span>
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

              <button
                onClick={() => setActiveTab('analytics')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-xl transition ${
                  activeTab === 'analytics'
                    ? 'bg-[#12131a] text-cyan-400 border-t border-x border-gray-800 shadow-sm shadow-cyan-500/10'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5 text-cyan-400" /> Analytics & History
              </button>
            </div>

            {/* Tab Contents */}
            <div className="flex-1 p-5 overflow-y-auto">
              {/* Universal Tag Test Result Card (Visible across all tabs) */}
              {tagTestResult && (
                <div className={`mb-4 p-4 rounded-xl border flex flex-col gap-2.5 transition ${
                  tagTestResult.is_niche
                    ? 'bg-purple-950/40 border-purple-500/50 text-purple-200 shadow-lg shadow-purple-500/10'
                    : 'bg-gray-900 border-gray-700 text-gray-300'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {tagTestResult.is_niche ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-5 h-5 text-amber-400 flex-shrink-0" />
                      )}
                      <span className="text-xs sm:text-sm font-bold">
                        {tagTestResult.is_niche
                          ? `🎯 Niche Match Detected: ${tagTestResult.matched_keywords.join(', ')}`
                          : '⚠️ No Target Tags Detected on Current Screen'}
                      </span>
                      {tagTestResult.is_niche && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/25 text-purple-300 border border-purple-500/30 font-medium">
                          Score: {tagTestResult.score} / 1.0 ({tagTestResult.matched_in || 'text'})
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => setTagTestResult(null)}
                      className="text-gray-400 hover:text-white text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 transition"
                    >
                      Dismiss ✕
                    </button>
                  </div>

                  {tagTestResult.is_niche ? (
                    <div className="text-xs text-gray-300 flex flex-wrap gap-x-5 gap-y-1.5 pt-1">
                      <span>⚡ <strong>Dwell Multiplier:</strong> {config?.dwell_time?.niche_match_multiplier_min ? `${config.dwell_time.niche_match_multiplier_min}x – ${config.dwell_time.niche_match_multiplier_max}x` : '1.8x – 2.8x'}</span>
                      <span>❤️ <strong>Like Chance:</strong> {Math.round((config?.probabilities?.like_niche_min ?? 0.35) * 100)}% – {Math.round((config?.probabilities?.like_niche_max ?? 0.55) * 100)}%</span>
                      <span>⭐ <strong>Favorite:</strong> {Math.round((config?.probabilities?.favorite_niche_min ?? 0.12) * 100)}% – {Math.round((config?.probabilities?.favorite_niche_max ?? 0.22) * 100)}%</span>
                      <span>📢 <strong>Sponsored/Ad:</strong> {tagTestResult.is_ad ? 'Yes (skipped)' : 'No (organic)'}</span>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400">
                      The on-screen text did not match any of your {(config?.niche?.target_keywords || []).length} keywords.
                    </div>
                  )}

                  {(tagTestResult.caption || tagTestResult.full_text) && (
                    <div className="mt-1 p-2.5 rounded-lg bg-black/50 border border-white/5 text-[11px] font-mono text-gray-300 max-h-24 overflow-y-auto">
                      <span className="text-gray-500 block text-[9px] uppercase tracking-wider mb-1">OCR Detected Text on Screen:</span>
                      {tagTestResult.caption || tagTestResult.full_text}
                    </div>
                  )}
                </div>
              )}

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
                              : log.type === 'niche'
                              ? 'bg-purple-500/15 border-purple-500/30 text-purple-300 font-medium'
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
                  {/* Apple Vision OCR Toggle Card */}
                  <div className="p-3 rounded-xl bg-gray-900/80 border border-gray-800 flex items-center justify-between">
                    <div className="flex flex-col pr-4">
                      <span className="text-xs text-gray-200 font-semibold flex items-center gap-1.5">
                        Apple Vision OCR Detection
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono">macOS Native</span>
                      </span>
                      <span className="text-[11px] text-gray-400 mt-0.5">
                        Scans on-screen text, captions & stickers to detect niche matches and multiply dwell time.
                      </span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                      <input
                        type="checkbox"
                        checked={config.vision?.enabled ?? true}
                        onChange={(e) => {
                          const updated = {
                            ...config,
                            vision: { ...config.vision, enabled: e.target.checked },
                          };
                          setConfig(updated);
                          handleSaveConfig(updated);
                        }}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-pink-600"></div>
                    </label>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-gray-300">
                        Target Niche Keywords (OCR matches in captions boost dwell & like rates)
                      </label>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleTestTags}
                          disabled={isTestingTags}
                          className="px-2.5 py-1 bg-purple-600/25 hover:bg-purple-600/35 text-purple-300 border border-purple-500/40 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-sm shadow-purple-500/10 cursor-pointer"
                          title="Capture current screen and test against niche tags using Apple Vision OCR"
                        >
                          {isTestingTags ? (
                            <>
                              <RefreshCw className="w-3 h-3 animate-spin text-purple-400" />
                              Testing Screen...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-3 h-3 text-purple-400" />
                              Test on Tags
                            </>
                          )}
                        </button>
                        {(config.niche?.target_keywords || []).length > 0 && (
                          <button
                            type="button"
                            onClick={clearAllKeywords}
                            className="text-[11px] text-gray-500 hover:text-red-400 transition"
                          >
                            Clear all ({(config.niche?.target_keywords || []).length})
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        placeholder="Single or bulk: #kukirin #ausom #lonnyo or kukirin, ausom, lonnyo"
                        value={newKeyword}
                        onChange={(e) => setNewKeyword(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
                        className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 outline-none focus:border-pink-500"
                      />
                      <button
                        onClick={addKeyword}
                        className="px-3 py-2 bg-pink-600 hover:bg-pink-500 text-white rounded-lg text-xs font-medium transition whitespace-nowrap"
                      >
                        {(() => {
                          const count = parseBulkInput(newKeyword, true).length;
                          return count > 1 ? `Add (${count}) Tags` : 'Add Tag';
                        })()}
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto">
                      {(config.niche?.target_keywords || []).map((kw: string) => (
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

                    {/* Tag Test Result Card */}
                    {tagTestResult && (
                      <div className={`mt-3 p-3.5 rounded-xl border flex flex-col gap-2 transition ${
                        tagTestResult.is_niche
                          ? 'bg-purple-950/30 border-purple-500/40 text-purple-200 shadow-md shadow-purple-500/10'
                          : 'bg-gray-900 border-gray-700 text-gray-300'
                      }`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {tagTestResult.is_niche ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                            ) : (
                              <XCircle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                            )}
                            <span className="text-xs font-bold">
                              {tagTestResult.is_niche
                                ? `Niche Match Detected: ${tagTestResult.matched_keywords.join(', ')}`
                                : 'No Target Tags Detected on Screen'}
                            </span>
                            {tagTestResult.is_niche && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-medium">
                                Score: {tagTestResult.score} / 1.0 ({tagTestResult.matched_in || 'text'})
                              </span>
                            )}
                          </div>
                          <button
                            onClick={() => setTagTestResult(null)}
                            className="text-gray-400 hover:text-white text-xs px-1"
                          >
                            ✕
                          </button>
                        </div>

                        {tagTestResult.is_niche ? (
                          <div className="text-[11px] text-gray-300 flex flex-wrap gap-x-4 gap-y-1">
                            <span>🎯 <strong>Dwell Multiplier:</strong> {config.dwell_time?.niche_match_multiplier_min ? `${config.dwell_time.niche_match_multiplier_min}x – ${config.dwell_time.niche_match_multiplier_max}x` : '1.8x – 2.8x'} boost</span>
                            <span>❤️ <strong>Like Chance:</strong> {Math.round((config?.probabilities?.like_niche_min ?? 0.35) * 100)}% – {Math.round((config?.probabilities?.like_niche_max ?? 0.55) * 100)}%</span>
                            <span>⭐ <strong>Favorite:</strong> {Math.round((config?.probabilities?.favorite_niche_min ?? 0.12) * 100)}% – {Math.round((config?.probabilities?.favorite_niche_max ?? 0.22) * 100)}%</span>
                            <span>📢 <strong>Sponsored/Ad:</strong> {tagTestResult.is_ad ? 'Yes (skipped)' : 'No (organic)'}</span>
                          </div>
                        ) : (
                          <div className="text-[11px] text-gray-400">
                            The on-screen text did not contain any of your {(config.niche?.target_keywords || []).length} keywords.
                          </div>
                        )}

                        {(tagTestResult.caption || tagTestResult.full_text) && (
                          <div className="mt-1 p-2 rounded-lg bg-black/40 border border-white/5 text-[10px] font-mono text-gray-300 max-h-20 overflow-y-auto">
                            <span className="text-gray-500 block text-[9px] uppercase tracking-wider mb-0.5">OCR Detected Text:</span>
                            {tagTestResult.caption || tagTestResult.full_text}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="border-t border-gray-800 pt-4">
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-gray-300">
                        Initial Search Seeding Terms (Searches these queries to steer FYP algorithm)
                      </label>
                      {(config.niche?.seed_terms || []).length > 0 && (
                        <button
                          type="button"
                          onClick={clearAllSeedTerms}
                          className="text-[11px] text-gray-500 hover:text-red-400 transition"
                        >
                          Clear all ({(config.niche?.seed_terms || []).length})
                        </button>
                      )}
                    </div>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        placeholder="Single or bulk: #kukirin #ausom #lonnyo or kukirin, ausom, lonnyo"
                        value={newSeedTerm}
                        onChange={(e) => setNewSeedTerm(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addSeedTerm()}
                        className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 outline-none focus:border-pink-500"
                      />
                      <button
                        onClick={addSeedTerm}
                        className="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg text-xs font-medium transition whitespace-nowrap"
                      >
                        {(() => {
                          const count = parseBulkInput(newSeedTerm, false).length;
                          return count > 1 ? `Add (${count}) Terms` : 'Add Term';
                        })()}
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {(config.niche?.seed_terms || []).map((term: string) => (
                        <span
                          key={term}
                          className="px-2.5 py-1 rounded-lg bg-gray-900 text-cyan-300 border border-cyan-500/20 text-xs flex items-center gap-2"
                        >
                          <span>🔍 {term}</span>
                          <button
                            type="button"
                            title={`Search '${term}' on TikTok now`}
                            onClick={() => handleTriggerSearch(term)}
                            disabled={isSearching}
                            className="px-1.5 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 hover:text-white text-[10px] font-semibold flex items-center gap-1 transition"
                          >
                            <Play className="w-2.5 h-2.5 fill-current" /> Search
                          </button>
                          <button
                            onClick={() => removeSeedTerm(term)}
                            className="text-gray-500 hover:text-red-400"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>

                    {/* Search Seeding Controls Card */}
                    <div className="p-3 rounded-xl bg-gray-900/80 border border-gray-800 flex flex-col gap-2.5">
                      <div className="flex items-center justify-between">
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                          <input
                            type="checkbox"
                            checked={!!config.niche?.seed_search_enabled}
                            onChange={(e) => {
                              const updated = {
                                ...config,
                                niche: { ...config.niche, seed_search_enabled: e.target.checked },
                              };
                              setConfig(updated);
                              handleSaveConfig(updated);
                            }}
                            className="accent-pink-500 rounded cursor-pointer"
                          />
                          <span className="text-xs text-gray-300 font-medium">Auto-seed search at warming start</span>
                        </label>
                        <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
                          <span>Videos/query:</span>
                          <input
                            type="number"
                            min={1}
                            max={config.niche?.seed_videos_max || 8}
                            value={config.niche?.seed_videos_min ?? 2}
                            onChange={(e) => {
                              const updated = {
                                ...config,
                                niche: {
                                  ...config.niche,
                                  seed_videos_min: Number(e.target.value),
                                  seed_videos_per_term: Number(e.target.value),
                                },
                              };
                              setConfig(updated);
                              handleSaveConfig(updated);
                            }}
                            className="w-11 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-1 py-0.5 text-center outline-none focus:border-pink-500"
                          />
                          <span>–</span>
                          <input
                            type="number"
                            min={config.niche?.seed_videos_min || 1}
                            max={12}
                            value={config.niche?.seed_videos_max ?? 5}
                            onChange={(e) => {
                              const updated = {
                                ...config,
                                niche: {
                                  ...config.niche,
                                  seed_videos_max: Number(e.target.value),
                                },
                              };
                              setConfig(updated);
                              handleSaveConfig(updated);
                            }}
                            className="w-11 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-1 py-0.5 text-center outline-none focus:border-pink-500"
                          />
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-gray-400 pt-1 border-t border-gray-800/60">
                        <span>Seed Video Attention Dwell:</span>
                        <div className="flex items-center gap-1.5">
                          <input
                            type="number"
                            step={0.5}
                            min={3}
                            max={config.niche?.seed_video_dwell_max_sec || 20}
                            value={config.niche?.seed_video_dwell_min_sec ?? 7.0}
                            onChange={(e) => {
                              const updated = {
                                ...config,
                                niche: {
                                  ...config.niche,
                                  seed_video_dwell_min_sec: Number(e.target.value),
                                },
                              };
                              setConfig(updated);
                              handleSaveConfig(updated);
                            }}
                            className="w-12 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-1 py-0.5 text-center outline-none focus:border-pink-500"
                          />
                          <span>s –</span>
                          <input
                            type="number"
                            step={0.5}
                            min={config.niche?.seed_video_dwell_min_sec || 5}
                            max={35}
                            value={config.niche?.seed_video_dwell_max_sec ?? 15.0}
                            onChange={(e) => {
                              const updated = {
                                ...config,
                                niche: {
                                  ...config.niche,
                                  seed_video_dwell_max_sec: Number(e.target.value),
                                },
                              };
                              setConfig(updated);
                              handleSaveConfig(updated);
                            }}
                            className="w-12 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-1 py-0.5 text-center outline-none focus:border-pink-500"
                          />
                          <span>s</span>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleTriggerSearch()}
                          disabled={isSearching || (config.niche?.seed_terms || []).length === 0}
                          className="flex-1 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-md shadow-cyan-500/10 cursor-pointer"
                        >
                          {isSearching ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              Seeding ({activeSearchTerm || 'Niche'})...
                            </>
                          ) : (
                            <>
                              <Search className="w-3.5 h-3.5" />
                              Trigger Niche Search Seeding
                            </>
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={handleStop}
                          disabled={!isSearching && stats.state !== 'RUNNING' && stats.state !== 'PAUSED'}
                          className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 border ${
                            isSearching || stats.state === 'RUNNING' || stats.state === 'PAUSED'
                              ? 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/40 shadow-sm shadow-rose-500/10 cursor-pointer'
                              : 'bg-gray-800 text-gray-500 border-gray-700 opacity-40 cursor-not-allowed'
                          }`}
                          title="Stop active search seeding or session"
                        >
                          <Square className="w-3.5 h-3.5 fill-current" /> Stop
                        </button>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleSaveConfig()}
                    disabled={isSavingConfig}
                    className="w-full py-2.5 bg-gradient-to-r from-pink-600 to-rose-600 text-white rounded-xl text-xs font-semibold hover:opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {saveStatus === 'saving' ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Saving to disk...
                      </>
                    ) : saveStatus === 'saved' ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" /> Saved to default_config.yaml!
                      </>
                    ) : (
                      'Apply & Save Niche Settings'
                    )}
                  </button>
                  <p className="text-[11px] text-gray-500 text-center">
                    All added niche tags and seed terms auto-save to config/default_config.yaml.
                  </p>
                </div>
              )}

              {/* Behavior & Probabilities Tab */}
              {activeTab === 'behavior' && config && (
                <div className="space-y-5 text-xs">
                  {/* Header info */}
                  <div className="p-3 rounded-xl bg-gray-900/80 border border-gray-800 flex items-center justify-between">
                    <div>
                      <span className="text-xs text-gray-200 font-semibold flex items-center gap-1.5">
                        <Shuffle className="w-3.5 h-3.5 text-pink-400" /> Human Attention & Action Randomization
                      </span>
                      <p className="text-[11px] text-gray-400 mt-0.5">
                        All values are configured as random ranges [Min, Max] sampled continuously to evade bot pattern detection.
                      </p>
                    </div>
                  </div>

                  {/* 1. Dwell Times */}
                  <div>
                    <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-pink-400" /> Dwell Times & Attention Curve
                    </h4>
                    <div className="space-y-3">
                      <RangeField
                        label="FYP Normal Video Dwell Range"
                        sublabel="Natural log-normal curve bounding video attention span"
                        minVal={config.dwell_time?.min_seconds ?? 3.5}
                        maxVal={config.dwell_time?.max_seconds ?? 35.0}
                        step={0.5}
                        minLimit={1}
                        maxLimit={60}
                        unit="s"
                        badgeColor="pink"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            dwell_time: {
                              ...config.dwell_time,
                              min_seconds: min,
                              max_seconds: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex items-center justify-between">
                        <div>
                          <span className="text-xs font-semibold text-gray-200">Log-Normal Mean Dwell</span>
                          <p className="text-[11px] text-gray-400 mt-0.5">Peak distribution center within the min-max bounds</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min={config.dwell_time?.min_seconds ?? 4}
                            max={config.dwell_time?.max_seconds ?? 30}
                            step={0.5}
                            value={config.dwell_time?.mean_seconds ?? 11.0}
                            onChange={(e) => {
                              setConfig({
                                ...config,
                                dwell_time: { ...config.dwell_time, mean_seconds: Number(e.target.value) },
                              });
                            }}
                            className="accent-pink-500 w-28 cursor-pointer"
                          />
                          <span className="text-xs font-mono font-medium text-pink-300 w-12 text-right">
                            {config.dwell_time?.mean_seconds ?? 11.0}s
                          </span>
                        </div>
                      </div>

                      <RangeField
                        label="Niche Match Dwell Multiplier"
                        sublabel="Multiplier range applied when target tags are detected on screen"
                        minVal={config.dwell_time?.niche_match_multiplier_min ?? 1.8}
                        maxVal={config.dwell_time?.niche_match_multiplier_max ?? 2.8}
                        step={0.1}
                        minLimit={1.0}
                        maxLimit={4.0}
                        unit="x"
                        badgeColor="purple"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            dwell_time: {
                              ...config.dwell_time,
                              niche_match_multiplier_min: min,
                              niche_match_multiplier_max: max,
                              niche_match_multiplier: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Ad & Sponsored Fast-Skip Dwell"
                        sublabel="Time before swiftly skipping detected commercial posts"
                        minVal={config.dwell_time?.ad_skip_min_seconds ?? 0.8}
                        maxVal={config.dwell_time?.ad_skip_max_seconds ?? 1.8}
                        step={0.1}
                        minLimit={0.3}
                        maxLimit={4.0}
                        unit="s"
                        badgeColor="emerald"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            dwell_time: {
                              ...config.dwell_time,
                              ad_skip_min_seconds: min,
                              ad_skip_max_seconds: max,
                              ad_skip_seconds: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />
                    </div>
                  </div>

                  {/* 2. Interaction Probabilities */}
                  <div className="border-t border-gray-800 pt-4">
                    <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <Heart className="w-3.5 h-3.5 text-rose-400" /> Like & Favorite Rates
                    </h4>
                    <div className="space-y-3">
                      <RangeField
                        label="Base Like Probability"
                        sublabel="Organic like rate for standard non-niche FYP videos"
                        minVal={config.probabilities?.like_base_min ?? 0.05}
                        maxVal={config.probabilities?.like_base_max ?? 0.15}
                        step={0.01}
                        minLimit={0}
                        maxLimit={0.5}
                        isPercent={true}
                        badgeColor="pink"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              like_base_min: min,
                              like_base_max: max,
                              like_base: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Niche Like Probability"
                        sublabel="High organic like rate when niche tags or topics match"
                        minVal={config.probabilities?.like_niche_min ?? 0.35}
                        maxVal={config.probabilities?.like_niche_max ?? 0.55}
                        step={0.01}
                        minLimit={0.1}
                        maxLimit={0.9}
                        isPercent={true}
                        badgeColor="pink"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              like_niche_min: min,
                              like_niche_max: max,
                              like_niche: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Double-Tap vs Heart Icon Ratio"
                        sublabel="Percentage of likes executed via screen double-tap vs side heart icon"
                        minVal={config.probabilities?.double_tap_ratio_min ?? 0.70}
                        maxVal={config.probabilities?.double_tap_ratio_max ?? 0.85}
                        step={0.01}
                        minLimit={0.2}
                        maxLimit={1.0}
                        isPercent={true}
                        badgeColor="pink"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              double_tap_ratio_min: min,
                              double_tap_ratio_max: max,
                              double_tap_ratio: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Base Favorite / Bookmark Chance"
                        sublabel="Occasional bookmarking of non-niche viral content"
                        minVal={config.probabilities?.favorite_base_min ?? 0.01}
                        maxVal={config.probabilities?.favorite_base_max ?? 0.04}
                        step={0.005}
                        minLimit={0}
                        maxLimit={0.2}
                        isPercent={true}
                        badgeColor="amber"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              favorite_base_min: min,
                              favorite_base_max: max,
                              favorite_base: Number(((min + max) / 2).toFixed(3)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Niche Favorite / Bookmark Chance"
                        sublabel="Intentional bookmarking rate for matched niche videos"
                        minVal={config.probabilities?.favorite_niche_min ?? 0.12}
                        maxVal={config.probabilities?.favorite_niche_max ?? 0.22}
                        step={0.01}
                        minLimit={0.02}
                        maxLimit={0.6}
                        isPercent={true}
                        badgeColor="amber"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              favorite_niche_min: min,
                              favorite_niche_max: max,
                              favorite_niche: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />
                    </div>
                  </div>

                  {/* 3. Comments Drawer & Inspection */}
                  <div className="border-t border-gray-800 pt-4">
                    <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <MessageCircle className="w-3.5 h-3.5 text-purple-400" /> Comment Drawer Inspection
                    </h4>
                    <div className="space-y-3">
                      <RangeField
                        label="Base Comment Drawer Open Chance"
                        sublabel="Rate of opening comment sheet on random videos"
                        minVal={config.probabilities?.comment_drawer_base_min ?? 0.01}
                        maxVal={config.probabilities?.comment_drawer_base_max ?? 0.03}
                        step={0.005}
                        minLimit={0}
                        maxLimit={0.15}
                        isPercent={true}
                        badgeColor="purple"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              comment_drawer_base_min: min,
                              comment_drawer_base_max: max,
                              comment_drawer_view_base: Number(((min + max) / 2).toFixed(3)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Niche Comment Drawer Open Chance"
                        sublabel="Rate of opening comment sheet on matched niche videos"
                        minVal={config.probabilities?.comment_drawer_niche_min ?? 0.06}
                        maxVal={config.probabilities?.comment_drawer_niche_max ?? 0.15}
                        step={0.01}
                        minLimit={0.02}
                        maxLimit={0.4}
                        isPercent={true}
                        badgeColor="purple"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              comment_drawer_niche_min: min,
                              comment_drawer_niche_max: max,
                              comment_drawer_view_niche: Number(((min + max) / 2).toFixed(2)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Comments Read Duration Range"
                        sublabel="Time spent reading comments before closing the drawer"
                        minVal={config.probabilities?.comment_read_min_seconds ?? 3.0}
                        maxVal={config.probabilities?.comment_read_max_seconds ?? 6.5}
                        step={0.5}
                        minLimit={1.0}
                        maxLimit={15.0}
                        unit="s"
                        badgeColor="purple"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              comment_read_min_seconds: min,
                              comment_read_max_seconds: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />
                    </div>
                  </div>

                  {/* 4. Creator Profile Subscriptions (Auto-Follow) */}
                  <div className="border-t border-gray-800 pt-4">
                    <div className="flex items-center justify-between mb-2.5">
                      <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                        <UserPlus className="w-3.5 h-3.5 text-emerald-400" /> Creator Profile Subscriptions (Auto-Follow)
                      </h4>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <span className="text-[11px] text-gray-400">Enabled</span>
                        <input
                          type="checkbox"
                          checked={config.follow?.enabled ?? true}
                          onChange={(e) => {
                            const updated = {
                              ...config,
                              follow: {
                                ...config.follow,
                                enabled: e.target.checked,
                              },
                            };
                            setConfig(updated);
                          }}
                          className="rounded border-gray-700 bg-gray-900 text-emerald-500 focus:ring-emerald-500/30"
                        />
                      </label>
                    </div>

                    <div className="space-y-3">
                      <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-xl flex items-center justify-between">
                        <div>
                          <span className="text-xs font-semibold text-gray-200">Min Matched Tags Condition</span>
                          <p className="text-[11px] text-gray-400 mt-0.5">
                            Minimum niche tags required on video to consider following creator
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            min={1}
                            max={10}
                            value={config.follow?.min_matched_tags ?? 2}
                            onChange={(e) => {
                              const val = Math.max(1, parseInt(e.target.value) || 2);
                              const updated = {
                                ...config,
                                follow: {
                                  ...config.follow,
                                  min_matched_tags: val,
                                },
                              };
                              setConfig(updated);
                            }}
                            className="w-16 px-2.5 py-1 text-center bg-gray-950 border border-gray-800 rounded-lg text-emerald-400 font-mono text-xs"
                          />
                          <span className="text-xs text-gray-400">tags</span>
                        </div>
                      </div>

                      <RangeField
                        label="Subscriptions per Session Range"
                        sublabel="Target follow quota randomly sampled at the start of each session"
                        minVal={config.follow?.follows_per_session_min ?? 1}
                        maxVal={config.follow?.follows_per_session_max ?? 3}
                        step={1}
                        minLimit={0}
                        maxLimit={15}
                        unit=" follows"
                        badgeColor="emerald"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            follow: {
                              ...config.follow,
                              follows_per_session_min: min,
                              follows_per_session_max: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Organic Follow Probability"
                        sublabel="Probability to initiate follow sequence when matched tags threshold is met"
                        minVal={config.follow?.follow_probability_min ?? 0.50}
                        maxVal={config.follow?.follow_probability_max ?? 0.70}
                        step={0.05}
                        minLimit={0.1}
                        maxLimit={1.0}
                        isPercent={true}
                        badgeColor="emerald"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            follow: {
                              ...config.follow,
                              follow_probability_min: min,
                              follow_probability_max: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Creator Videos Watched Before Following"
                        sublabel="Number of videos watched on creator profile before tapping follow"
                        minVal={config.follow?.profile_videos_min ?? 1}
                        maxVal={config.follow?.profile_videos_max ?? 3}
                        step={1}
                        minLimit={1}
                        maxLimit={6}
                        unit=" videos"
                        badgeColor="emerald"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            follow: {
                              ...config.follow,
                              profile_videos_min: min,
                              profile_videos_max: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Profile Video Dwell Duration"
                        sublabel="Attention span per video watched inside the creator profile"
                        minVal={config.follow?.profile_video_dwell_min_sec ?? 5.0}
                        maxVal={config.follow?.profile_video_dwell_max_sec ?? 10.0}
                        step={0.5}
                        minLimit={2.0}
                        maxLimit={25.0}
                        unit="s"
                        badgeColor="emerald"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            follow: {
                              ...config.follow,
                              profile_video_dwell_min_sec: min,
                              profile_video_dwell_max_sec: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />
                    </div>
                  </div>

                  {/* 5. Natural Pauses & Biometric Gestures */}
                  <div className="border-t border-gray-800 pt-4">
                    <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-cyan-400" /> Natural Pauses & Biometrics
                    </h4>
                    <div className="space-y-3">
                      <RangeField
                        label="Post-Action Pause Duration"
                        sublabel="Natural pause after liking, bookmarking, or closing drawer"
                        minVal={config.probabilities?.post_action_pause_min_sec ?? 0.6}
                        maxVal={config.probabilities?.post_action_pause_max_sec ?? 1.4}
                        step={0.1}
                        minLimit={0.2}
                        maxLimit={3.0}
                        unit="s"
                        badgeColor="cyan"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              post_action_pause_min_sec: min,
                              post_action_pause_max_sec: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Post-Swipe Stabilization Pause"
                        sublabel="Eye adjustment and video rendering pause immediately after swipe"
                        minVal={config.probabilities?.post_swipe_pause_min_sec ?? 0.8}
                        maxVal={config.probabilities?.post_swipe_pause_max_sec ?? 1.8}
                        step={0.1}
                        minLimit={0.3}
                        maxLimit={4.0}
                        unit="s"
                        badgeColor="cyan"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              post_swipe_pause_min_sec: min,
                              post_swipe_pause_max_sec: max,
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Rewatch Swipe-Back Chance"
                        sublabel="Occasional downward swipe to rewatch previous video"
                        minVal={config.probabilities?.rewatch_swipe_back_min ?? 0.02}
                        maxVal={config.probabilities?.rewatch_swipe_back_max ?? 0.06}
                        step={0.005}
                        minLimit={0}
                        maxLimit={0.15}
                        isPercent={true}
                        badgeColor="cyan"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              rewatch_swipe_back_min: min,
                              rewatch_swipe_back_max: max,
                              rewatch_swipe_back: Number(((min + max) / 2).toFixed(3)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />

                      <RangeField
                        label="Micro-Flick Gesture Chance"
                        sublabel="Subtle biometric touch twitch mimicking hand grip adjustment"
                        minVal={config.probabilities?.micro_flick_min ?? 0.01}
                        maxVal={config.probabilities?.micro_flick_max ?? 0.05}
                        step={0.005}
                        minLimit={0}
                        maxLimit={0.15}
                        isPercent={true}
                        badgeColor="cyan"
                        onChange={(min, max) => {
                          const updated = {
                            ...config,
                            probabilities: {
                              ...config.probabilities,
                              micro_flick_min: min,
                              micro_flick_max: max,
                              micro_flick: Number(((min + max) / 2).toFixed(3)),
                            },
                          };
                          setConfig(updated);
                        }}
                      />
                    </div>
                  </div>

                  <button
                    onClick={() => handleSaveConfig()}
                    disabled={isSavingConfig}
                    className="w-full py-2.5 bg-gradient-to-r from-pink-600 to-rose-600 text-white rounded-xl text-xs font-semibold hover:opacity-90 transition mt-3 disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-pink-500/20"
                  >
                    {saveStatus === 'saving' ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Saving to disk...
                      </>
                    ) : saveStatus === 'saved' ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" /> Saved to default_config.yaml!
                      </>
                    ) : (
                      'Apply & Save Randomized Ranges'
                    )}
                  </button>
                  <p className="text-[11px] text-gray-500 text-center">
                    All randomized ranges will be stored in config/default_config.yaml and take effect immediately.
                  </p>
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

              {/* Analytics & Session History Tab */}
              {activeTab === 'analytics' && (
                <div className="space-y-6 text-xs">
                  {/* Top Header Card */}
                  <div className="p-4 rounded-2xl bg-gradient-to-r from-cyan-950/40 via-blue-950/30 to-gray-900 border border-cyan-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg shadow-cyan-500/5">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-cyan-400" /> TikTok Algorithm Analytics & Session History
                      </h3>
                      <p className="text-[11px] text-gray-400 mt-1 max-w-xl leading-relaxed">
                        Persistent session records, itemized video interaction logs, and the 4-Factor Account Warming Health Score.
                      </p>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={fetchAnalyticsData}
                        disabled={isLoadingAnalytics}
                        className="px-2.5 py-1.5 rounded-xl bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-700 text-xs font-medium transition flex items-center gap-1.5"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isLoadingAnalytics ? 'animate-spin text-cyan-400' : ''}`} /> Refresh
                      </button>

                      <button
                        onClick={() => window.open('/api/sessions/export/download?format=csv', '_blank')}
                        className="px-2.5 py-1.5 rounded-xl bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-500/40 text-xs font-medium transition flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" /> Export CSV
                      </button>

                      <button
                        onClick={() => window.open('/api/sessions/export/download?format=json', '_blank')}
                        className="px-2.5 py-1.5 rounded-xl bg-gray-900 hover:bg-gray-800 text-gray-300 border border-gray-700 text-xs font-medium transition flex items-center gap-1.5"
                      >
                        <FileText className="w-3.5 h-3.5 text-purple-400" /> Export JSON
                      </button>

                      {sessionsList.length > 0 && (
                        <button
                          onClick={handleClearAllSessions}
                          className="px-2.5 py-1.5 rounded-xl bg-rose-950/30 hover:bg-rose-900/40 text-rose-300 border border-rose-500/30 text-xs font-medium transition flex items-center gap-1.5"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Clear History
                        </button>
                      )}
                    </div>
                  </div>

                  {/* 4-Factor Account Warming Health Score Hero Banner */}
                  {analyticsSummary && (
                    <div className="p-5 rounded-2xl bg-[#151722] border border-gray-800/90 flex flex-col md:flex-row gap-6 items-stretch">
                      {/* Left: Overall Health Score Gauge */}
                      <div className="md:w-1/3 flex flex-col justify-center items-center text-center p-4 rounded-xl bg-black/40 border border-gray-800/70">
                        <span className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">
                          Account Warming Health Score
                        </span>

                        <div className="my-3 relative flex items-center justify-center">
                          <div
                            className={`w-28 h-28 rounded-full border-4 flex flex-col items-center justify-center shadow-lg transition ${
                              analyticsSummary.warming_health_score.score >= 80
                                ? 'border-emerald-500 text-emerald-400 bg-emerald-500/10 shadow-emerald-500/20'
                                : analyticsSummary.warming_health_score.score >= 65
                                ? 'border-cyan-500 text-cyan-400 bg-cyan-500/10 shadow-cyan-500/20'
                                : analyticsSummary.warming_health_score.score >= 50
                                ? 'border-amber-500 text-amber-400 bg-amber-500/10 shadow-amber-500/20'
                                : 'border-rose-500 text-rose-400 bg-rose-500/10 shadow-rose-500/20'
                            }`}
                          >
                            <span className="text-3xl font-extrabold tracking-tight">
                              {analyticsSummary.warming_health_score.score}
                            </span>
                            <span className="text-[10px] text-gray-400 font-medium">/ 100</span>
                          </div>
                        </div>

                        <span
                          className={`px-3 py-1 rounded-full text-xs font-bold border ${
                            analyticsSummary.warming_health_score.score >= 80
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : analyticsSummary.warming_health_score.score >= 65
                              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                              : analyticsSummary.warming_health_score.score >= 50
                              ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                              : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          }`}
                        >
                          {analyticsSummary.warming_health_score.rating}
                        </span>

                        <p className="text-[10px] text-gray-500 mt-2.5 max-w-[200px] leading-tight">
                          Weighted composite index assessing FYP algorithm tuning & human-like dwell behavior.
                        </p>
                      </div>

                      {/* Right: 4-Factor Breakdown */}
                      <div className="md:w-2/3 grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                        {/* Factor 1: Niche Alignment */}
                        <div className="p-3.5 rounded-xl bg-gray-900/50 border border-gray-800 flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                                <Tag className="w-3.5 h-3.5 text-cyan-400" /> Niche Alignment
                              </span>
                              <span className="text-[10px] text-cyan-400 font-mono font-bold">
                                40% Weight • {analyticsSummary.warming_health_score.factors.niche_alignment.score} pts
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden my-2">
                              <div
                                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                                style={{ width: `${Math.min(100, analyticsSummary.warming_health_score.factors.niche_alignment.score)}%` }}
                              />
                            </div>
                          </div>
                          <span className="text-[11px] text-gray-400 leading-tight">
                            {analyticsSummary.warming_health_score.factors.niche_alignment.details}
                          </span>
                        </div>

                        {/* Factor 2: Engagement Balance */}
                        <div className="p-3.5 rounded-xl bg-gray-900/50 border border-gray-800 flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                                <Heart className="w-3.5 h-3.5 text-pink-400" /> Engagement Balance
                              </span>
                              <span className="text-[10px] text-pink-400 font-mono font-bold">
                                25% Weight • {analyticsSummary.warming_health_score.factors.engagement_balance.score} pts
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden my-2">
                              <div
                                className="h-full bg-gradient-to-r from-pink-500 to-rose-500 rounded-full"
                                style={{ width: `${Math.min(100, analyticsSummary.warming_health_score.factors.engagement_balance.score)}%` }}
                              />
                            </div>
                          </div>
                          <span className="text-[11px] text-gray-400 leading-tight">
                            {analyticsSummary.warming_health_score.factors.engagement_balance.details}
                          </span>
                        </div>

                        {/* Factor 3: Dwell Differentiation */}
                        <div className="p-3.5 rounded-xl bg-gray-900/50 border border-gray-800 flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                                <Clock className="w-3.5 h-3.5 text-purple-400" /> Dwell Quality
                              </span>
                              <span className="text-[10px] text-purple-400 font-mono font-bold">
                                20% Weight • {analyticsSummary.warming_health_score.factors.dwell_differentiation.score} pts
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden my-2">
                              <div
                                className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 rounded-full"
                                style={{ width: `${Math.min(100, analyticsSummary.warming_health_score.factors.dwell_differentiation.score)}%` }}
                              />
                            </div>
                          </div>
                          <span className="text-[11px] text-gray-400 leading-tight">
                            {analyticsSummary.warming_health_score.factors.dwell_differentiation.details}
                          </span>
                        </div>

                        {/* Factor 4: Session Stability */}
                        <div className="p-3.5 rounded-xl bg-gray-900/50 border border-gray-800 flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Stability & Safety
                              </span>
                              <span className="text-[10px] text-emerald-400 font-mono font-bold">
                                15% Weight • {analyticsSummary.warming_health_score.factors.session_stability.score} pts
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden my-2">
                              <div
                                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full"
                                style={{ width: `${Math.min(100, analyticsSummary.warming_health_score.factors.session_stability.score)}%` }}
                              />
                            </div>
                          </div>
                          <span className="text-[11px] text-gray-400 leading-tight">
                            {analyticsSummary.warming_health_score.factors.session_stability.details}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Lifetime KPI Metrics Grid */}
                  {analyticsSummary && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="p-3.5 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                        <span className="text-[11px] text-gray-400 font-medium">Lifetime Watch Time</span>
                        <span className="text-xl font-bold text-white mt-1">
                          {formatDuration(analyticsSummary.lifetime.total_duration_seconds)}
                        </span>
                        <span className="text-[10px] text-gray-500 mt-1">
                          {analyticsSummary.lifetime.total_sessions} completed sessions
                        </span>
                      </div>

                      <div className="p-3.5 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                        <span className="text-[11px] text-gray-400 font-medium">Niche Match Rate</span>
                        <span className="text-xl font-bold text-cyan-400 mt-1">
                          {analyticsSummary.lifetime.niche_match_rate_percent}%
                        </span>
                        <span className="text-[10px] text-gray-500 mt-1">
                          {analyticsSummary.lifetime.total_niche_matched} / {analyticsSummary.lifetime.total_videos_watched} videos
                        </span>
                      </div>

                      <div className="p-3.5 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                        <span className="text-[11px] text-gray-400 font-medium">Engagements Total</span>
                        <span className="text-xl font-bold text-pink-400 mt-1">
                          {analyticsSummary.lifetime.total_likes + analyticsSummary.lifetime.total_favorites + analyticsSummary.lifetime.total_follows}
                        </span>
                        <span className="text-[10px] text-gray-500 mt-1">
                          {analyticsSummary.lifetime.total_likes} ❤️ • {analyticsSummary.lifetime.total_favorites} ⭐ • {analyticsSummary.lifetime.total_follows} 👤
                        </span>
                      </div>

                      <div className="p-3.5 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                        <span className="text-[11px] text-gray-400 font-medium">Average Dwell Time</span>
                        <span className="text-xl font-bold text-purple-400 mt-1">
                          {analyticsSummary.lifetime.avg_niche_dwell_seconds}s
                        </span>
                        <span className="text-[10px] text-gray-500 mt-1">
                          vs {analyticsSummary.lifetime.avg_generic_dwell_seconds}s generic FYP
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Trends & Keyword Discovery Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Recent Sessions Progression */}
                    <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                      <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5 mb-3">
                        <TrendingUp className="w-3.5 h-3.5 text-cyan-400" /> FYP Niche Alignment Progression
                      </span>

                      {analyticsTrends && analyticsTrends.session_progression.length > 0 ? (
                        <div className="space-y-2.5">
                          {analyticsTrends.session_progression.slice(-6).map((s, idx) => (
                            <div key={idx} className="flex items-center gap-3">
                              <span className="text-[10px] text-gray-400 font-mono w-24 truncate">
                                {s.session_id.replace('sess_', '')}
                              </span>
                              <div className="flex-1 h-3 bg-gray-800 rounded-full overflow-hidden flex">
                                <div
                                  className="h-full bg-gradient-to-r from-cyan-500 to-pink-500 rounded-full"
                                  style={{ width: `${Math.round((s.niche_match_rate || 0) * 100)}%` }}
                                />
                              </div>
                              <span className="text-[11px] font-mono text-cyan-300 w-12 text-right">
                                {Math.round((s.niche_match_rate || 0) * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[11px] text-gray-500 py-3 text-center">
                          Progression curve will appear after your first sessions.
                        </p>
                      )}
                    </div>

                    {/* Top Discovered Keywords */}
                    <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                      <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5 mb-3">
                        <Tag className="w-3.5 h-3.5 text-pink-400" /> Most Frequent FYP Keywords & Hashtags
                      </span>

                      {analyticsTrends && analyticsTrends.top_keywords.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {analyticsTrends.top_keywords.map((kw, idx) => (
                            <span
                              key={idx}
                              className="px-2.5 py-1 rounded-lg bg-pink-500/10 border border-pink-500/20 text-pink-300 text-[11px] font-medium flex items-center gap-1.5"
                            >
                              <span>#{kw.keyword}</span>
                              <span className="px-1.5 py-0.2 bg-pink-500/20 rounded-md text-[9px] font-mono text-pink-200">
                                {kw.count}
                              </span>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[11px] text-gray-500 py-3 text-center">
                          Keywords identified via Apple Vision OCR will populate here.
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Detailed Sessions History & Video Inspector */}
                  <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800 flex flex-col">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                        <History className="w-3.5 h-3.5 text-cyan-400" /> Session History & Video Inspector
                      </span>
                      <span className="text-[11px] text-gray-400">
                        {sessionsList.length} recorded {sessionsList.length === 1 ? 'session' : 'sessions'}
                      </span>
                    </div>

                    {sessionsList.length === 0 ? (
                      <div className="text-center py-8 text-gray-500">
                        <p className="text-xs">No saved sessions yet.</p>
                        <p className="text-[11px] text-gray-600 mt-1">
                          Start a session from the Activity tab to automatically log videos and interactions.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        {sessionsList.map((sess) => {
                          const isExpanded = expandedSessionId === sess.session_id;
                          const detail = sessionDetails[sess.session_id];

                          return (
                            <div
                              key={sess.session_id}
                              className="rounded-xl border border-gray-800 bg-[#101118] overflow-hidden transition"
                            >
                              {/* Session Header Row */}
                              <div
                                onClick={() => handleToggleExpandSession(sess.session_id)}
                                className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer hover:bg-gray-900/60 transition select-none"
                              >
                                <div className="flex items-center gap-3">
                                  {isExpanded ? (
                                    <ChevronUp className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                                  ) : (
                                    <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" />
                                  )}
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono font-bold text-gray-200 text-xs">
                                        {sess.session_id}
                                      </span>
                                      <span
                                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                          sess.state === 'COMPLETED'
                                            ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                            : sess.state === 'RUNNING'
                                            ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20 animate-pulse'
                                            : sess.state === 'CAPTCHA_HALTED'
                                            ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                            : 'bg-gray-800 text-gray-400 border-gray-700'
                                        }`}
                                      >
                                        {sess.state}
                                      </span>
                                    </div>
                                    <span className="text-[10px] text-gray-500 block mt-0.5">
                                      {sess.start_time ? new Date(sess.start_time).toLocaleString() : ''}
                                      {sess.exit_reason ? ` • ${sess.exit_reason}` : ''}
                                    </span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-4 flex-wrap text-[11px]">
                                  <div className="flex items-center gap-3 text-gray-300">
                                    <span className="text-gray-400">
                                      ⏱️ {formatDuration(sess.duration_seconds)}
                                    </span>
                                    <span>
                                      📱 <strong className="text-white">{sess.videos_watched}</strong> vids
                                    </span>
                                    <span className="text-cyan-300">
                                      🎯 {Math.round((sess.niche_match_rate || 0) * 100)}% niche
                                    </span>
                                    <span>
                                      ❤️ {sess.likes_count} • ⭐ {sess.favorites_count} • 👤 {sess.follows_count}
                                    </span>
                                  </div>

                                  <button
                                    onClick={(e) => handleDeleteSession(sess.session_id, e)}
                                    title="Delete session"
                                    className="p-1.5 rounded-lg hover:bg-rose-950/40 text-gray-500 hover:text-rose-400 transition"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>

                              {/* Expanded Itemized Video Inspection List */}
                              {isExpanded && (
                                <div className="p-4 border-t border-gray-800/80 bg-black/40">
                                  {isLoadingSessionDetail && !detail ? (
                                    <div className="flex items-center justify-center py-4 text-gray-400 gap-2">
                                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                                      Loading video interaction details...
                                    </div>
                                  ) : detail && detail.videos && detail.videos.length > 0 ? (
                                    <div className="overflow-x-auto">
                                      <table className="w-full text-[11px] text-left">
                                        <thead>
                                          <tr className="border-b border-gray-800 text-gray-500">
                                            <th className="py-2 px-2.5 font-medium">#</th>
                                            <th className="py-2 px-2.5 font-medium">Time</th>
                                            <th className="py-2 px-2.5 font-medium">Caption OCR Snippet</th>
                                            <th className="py-2 px-2.5 font-medium">Matched Tags</th>
                                            <th className="py-2 px-2.5 font-medium">Dwell</th>
                                            <th className="py-2 px-2.5 font-medium">Actions Taken</th>
                                            <th className="py-2 px-2.5 font-medium">Type</th>
                                          </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-800/40">
                                          {detail.videos.map((vid, vIdx) => (
                                            <tr key={vid.id || vIdx} className="hover:bg-gray-900/30 transition">
                                              <td className="py-2 px-2.5 font-mono text-gray-500">{vIdx + 1}</td>
                                              <td className="py-2 px-2.5 text-gray-400 font-mono whitespace-nowrap">
                                                {vid.timestamp ? new Date(vid.timestamp).toLocaleTimeString() : ''}
                                              </td>
                                              <td className="py-2 px-2.5 text-gray-300 max-w-xs truncate" title={vid.caption}>
                                                {vid.caption || <span className="text-gray-600 italic">No text extracted</span>}
                                              </td>
                                              <td className="py-2 px-2.5">
                                                {vid.matched_keywords && vid.matched_keywords.length > 0 ? (
                                                  <div className="flex flex-wrap gap-1">
                                                    {vid.matched_keywords.map((kw, kIdx) => (
                                                      <span
                                                        key={kIdx}
                                                        className="px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-[9px] font-mono"
                                                      >
                                                        #{kw}
                                                      </span>
                                                    ))}
                                                  </div>
                                                ) : (
                                                  <span className="text-gray-600 text-[10px]">—</span>
                                                )}
                                              </td>
                                              <td className="py-2 px-2.5 font-mono text-purple-300 whitespace-nowrap">
                                                {vid.dwell_time_seconds}s
                                              </td>
                                              <td className="py-2 px-2.5">
                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                  {vid.action_liked && (
                                                    <span className="px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-300 text-[9px] font-semibold flex items-center gap-0.5">
                                                      ❤️ Like
                                                    </span>
                                                  )}
                                                  {vid.action_favorited && (
                                                    <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[9px] font-semibold flex items-center gap-0.5">
                                                      ⭐ Fav
                                                    </span>
                                                  )}
                                                  {vid.action_comment_viewed && (
                                                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[9px] font-semibold flex items-center gap-0.5">
                                                      💬 Comments
                                                    </span>
                                                  )}
                                                  {vid.action_followed && (
                                                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-semibold flex items-center gap-0.5">
                                                      👤 Followed
                                                    </span>
                                                  )}
                                                  {vid.action_skipped_early && (
                                                    <span className="px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 text-[9px] font-semibold flex items-center gap-0.5">
                                                      ⏩ Skipped
                                                    </span>
                                                  )}
                                                  {!vid.action_liked && !vid.action_favorited && !vid.action_comment_viewed && !vid.action_followed && !vid.action_skipped_early && (
                                                    <span className="text-gray-600 text-[10px]">Watched</span>
                                                  )}
                                                </div>
                                              </td>
                                              <td className="py-2 px-2.5 whitespace-nowrap">
                                                {vid.is_ad ? (
                                                  <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 text-[9px] font-bold">
                                                    SPONSORED
                                                  </span>
                                                ) : vid.is_niche ? (
                                                  <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 text-[9px] font-bold">
                                                    NICHE MATCH
                                                  </span>
                                                ) : (
                                                  <span className="px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 text-[9px]">
                                                    GENERIC FYP
                                                  </span>
                                                )}
                                              </td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  ) : (
                                    <p className="text-[11px] text-gray-500 py-3 text-center">
                                      No video interactions recorded for this session.
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
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
