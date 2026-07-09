import React, { useEffect, useMemo, useState } from "react";

const THEME_OPTIONS = [
  { value: "slate", label: "冷调灰 Slate", hint: "默认,中性" },
  { value: "claude", label: "暖驼 Claude", hint: "Anthropic 风格" },
  { value: "ocean", label: "天蓝 Ocean", hint: "清爽明亮" },
  { value: "forest", label: "森林 Forest", hint: "数据后台" },
  { value: "dusk", label: "暮玫 Dusk", hint: "暗紫玫红" },
];

const DENSITY_OPTIONS = [
  { value: "compact", label: "紧凑", hint: "12px,一屏更多" },
  { value: "cozy", label: "标准", hint: "13px,默认" },
  { value: "roomy", label: "宽松", hint: "14.5px,易读" },
];

function applyAppearance(theme, density) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.setAttribute("data-density", density);
}

function loadInitial(key, fallback) {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw || fallback;
  } catch (err) {
    return fallback;
  }
}

function copyToClipboard(text) {
  if (!text) return false;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).catch(() => {});
    return true;
  }
  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "");
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    return true;
  } catch (err) {
    return false;
  }
}

function StatusPill({ tone = "neutral", children }) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

export default function SystemSettings({ apiFetch, systemPaths, onCopied }) {
  const [paths, setPaths] = useState(systemPaths || null);
  const [rotating, setRotating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [revealedKey, setRevealedKey] = useState(null); // string|null - last rotated/persisted key
  const [overrideKey, setOverrideKey] = useState("");
  const [overridePersist, setOverridePersist] = useState(true);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [theme, setTheme] = useState(() => loadInitial("qb_theme", "slate"));
  const [density, setDensity] = useState(() => loadInitial("qb_density", "cozy"));

  useEffect(() => {
    if (systemPaths) {
      setPaths(systemPaths);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch("/api/system/paths");
        if (!cancelled) setPaths(data);
      } catch (err) {
        if (!cancelled) setError(String(err.message || err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiFetch, systemPaths]);

  const configured = useMemo(
    () => String(paths?.secret_master_configured || "") === "true",
    [paths],
  );
  const plainMode = useMemo(
    () => String(paths?.secret_master_plain_mode ?? "true") !== "false",
    [paths],
  );
  const envVar = paths?.secret_master_env || "QUESTION_BANK_SECRET_KEY";
  const envPath = paths?.secret_master_key_path || "";

  const flash = (message) => {
    setInfo(message);
    if (onCopied) onCopied(message);
  };

  const handleRotate = async () => {
    setRotating(true);
    setError("");
    try {
      const data = await apiFetch("/api/system/master-key/rotate", {
        method: "POST",
        body: JSON.stringify({ persist: true }),
      });
      if (data?.key) {
        setRevealedKey(data.key);
        copyToClipboard(data.key);
        flash(`已生成新 master key（已复制到剪贴板，persisted=${data.persisted}）`);
      }
      const refreshed = await apiFetch("/api/system/paths");
      setPaths(refreshed);
    } catch (err) {
      setError(`轮换失败：${err.message || err}`);
    } finally {
      setRotating(false);
    }
  };

  const handleOverride = async (event) => {
    event.preventDefault();
    if (overrideKey.trim().length < 8) {
      setError("Key 至少 8 字符");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const data = await apiFetch("/api/system/master-key", {
        method: "PUT",
        body: JSON.stringify({ key: overrideKey.trim(), persist: overridePersist }),
      });
      if (data?.key) {
        setRevealedKey(data.key);
        flash("已替换 master key");
      } else {
        flash("已替换 master key（仅内存）");
      }
      setOverrideKey("");
      const refreshed = await apiFetch("/api/system/paths");
      setPaths(refreshed);
    } catch (err) {
      setError(`覆盖失败：${err.message || err}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCopyPath = () => {
    if (envPath) {
      copyToClipboard(envPath);
      flash("已复制 .env 路径到剪贴板");
    }
  };

  const handleCopyKey = () => {
    if (revealedKey) {
      copyToClipboard(revealedKey);
      flash("已复制 master key");
    }
  };

  return (
    <section className="panel settings-page">
      <div className="settings-page-header">
        <h2 className="panel-title">系统设置</h2>
        <div className="settings-page-meta">
          {plainMode ? (
            <StatusPill tone="ok">明文存储模式</StatusPill>
          ) : configured ? (
            <StatusPill tone="ok">加密模式（master key 已配置）</StatusPill>
          ) : (
            <StatusPill tone="warn">加密模式但未配置 master key</StatusPill>
          )}
        </div>
      </div>

      <p className="muted-text">
        当前存储模式：<strong>{plainMode ? "明文（本地开发友好）" : "Fernet 加密"}</strong>。
        明文模式下，<code>model-connections</code> 的 API Key 直接以原文写入 <code>manifests/evaluation.sqlite</code>，不再需要 master key。
        如果你希望改为加密模式，把 <code>QUESTION_BANK_PLAIN_API_KEYS=false</code> 写到 <code>.env</code> 后重启后端即可。
      </p>

      <div className="detail-card settings-card">
        <SectionTitle title="环境变量" />
        <div className="config-list">
          <div className="config-row">
            <div className="config-label">变量名</div>
            <div className="config-value">
              <code>{envVar}</code>
            </div>
          </div>
          <div className="config-row">
            <div className="config-label">持久化路径</div>
            <div className="config-value">
              <code>{envPath || "(未启用持久化)"}</code>
              {envPath ? (
                <button type="button" className="link-button" onClick={handleCopyPath}>
                  复制路径
                </button>
              ) : null}
            </div>
          </div>
          <div className="config-row">
            <div className="config-label">当前状态</div>
            <div className="config-value">
              {configured ? "已配置" : "未配置（写入 API Key 将失败）"}
            </div>
          </div>
        </div>
      </div>

      <div className="detail-card settings-card">
        <SectionTitle title="轮换 / 重新生成 master key" />
        <p className="muted-text">
          {plainMode ? (
            "当前是明文存储模式,master key 不会用于加密 API Key。下面这两个按钮仍保留,方便你切换到加密模式时使用。"
          ) : (
            <>
              轮换会生成新的 32 字节随机 key,覆盖 <code>{envVar}</code>。
              注意:轮换后所有已加密的 API Key 都会变成不可解密状态,需要重新录入。
            </>
          )}
        </p>
        <div className="settings-actions">
          <button
            type="button"
            className="action-button primary"
            disabled={rotating}
            onClick={handleRotate}
          >
            {rotating ? "正在生成..." : "生成新的 master key"}
          </button>
        </div>
        {revealedKey ? (
          <div className="reveal-block">
            <div className="reveal-row">
              <code className="reveal-key">{revealedKey}</code>
              <button type="button" className="link-button" onClick={handleCopyKey}>
                复制
              </button>
            </div>
            <div className="muted-text">这是新生成的 master key。请妥善保存，刷新页面后无法再次查看。</div>
          </div>
        ) : null}
      </div>

      <div className="detail-card settings-card">
        <SectionTitle title="手动覆盖" />
        <p className="muted-text">
          如果你想使用自己的 master key（≥ 8 字符），可在此粘贴。覆盖后建议重启后端或重新加载页面。
        </p>
        <form onSubmit={handleOverride} className="settings-form">
          <label className="settings-form-label">
            <span>新 master key</span>
            <input
              type="text"
              value={overrideKey}
              onChange={(event) => setOverrideKey(event.target.value)}
              placeholder="至少 8 字符"
              spellCheck={false}
            />
          </label>
          <label className="settings-form-checkbox">
            <input
              type="checkbox"
              checked={overridePersist}
              onChange={(event) => setOverridePersist(event.target.checked)}
            />
            <span>同时写入 .env</span>
          </label>
          <div className="settings-actions">
            <button
              type="submit"
              className="action-button secondary"
              disabled={saving || overrideKey.trim().length < 8}
            >
              {saving ? "正在保存..." : "保存并应用"}
            </button>
          </div>
        </form>
      </div>

      <div className="detail-card settings-card">
        <SectionTitle title="外观" meta="主题与字体大小" />
        <p className="muted-text">
          切换主题配色或调整全局字体大小,设置会立即生效并保存到本地浏览器。
        </p>

        <div className="appearance-section">
          <div className="appearance-label">配色主题</div>
          <div className="appearance-grid">
            {THEME_OPTIONS.map((opt) => (
              <button
                type="button"
                key={opt.value}
                className={`theme-card ${theme === opt.value ? "is-active" : ""}`}
                onClick={() => {
                  setTheme(opt.value);
                  applyAppearance(opt.value, density);
                  try { window.localStorage.setItem("qb_theme", opt.value); } catch (e) {}
                }}
                aria-pressed={theme === opt.value}
              >
                <div className={`theme-swatch theme-swatch--${opt.value}`} />
                <div className="theme-card-text">
                  <div className="theme-card-title">{opt.label}</div>
                  <div className="theme-card-hint">{opt.hint}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="appearance-section">
          <div className="appearance-label">字体大小</div>
          <div className="density-row">
            {DENSITY_OPTIONS.map((opt) => (
              <button
                type="button"
                key={opt.value}
                className={`density-pill ${density === opt.value ? "is-active" : ""}`}
                onClick={() => {
                  setDensity(opt.value);
                  applyAppearance(theme, opt.value);
                  try { window.localStorage.setItem("qb_density", opt.value); } catch (e) {}
                }}
                aria-pressed={density === opt.value}
              >
                <span className="density-pill-label">{opt.label}</span>
                <span className="density-pill-hint">{opt.hint}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {error ? <div className="banner banner--error">{error}</div> : null}
      {info ? <div className="banner banner--info">{info}</div> : null}
    </section>
  );
}

function SectionTitle({ title, meta }) {
  return (
    <div className="section-title">
      <h3 className="section-title-text">{title}</h3>
      {meta ? <span className="section-title-meta">{meta}</span> : null}
    </div>
  );
}
