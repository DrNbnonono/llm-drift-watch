import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const KIND_DEFS = [
  { key: "module", label: "题目分组 Modules", moduleField: null, codeHint: "如 D1" },
  { key: "subtype", label: "题型 Subtypes", moduleField: "module_code", codeHint: "如 math_reasoning" },
  { key: "quota_tag", label: "配额标签 Quota Tags", moduleField: "module_code", codeHint: "如 rate_counting" },
];

function StatusTone({ kind, isActive }) {
  if (!isActive) return <span className="pill pill--off">已归档</span>;
  return <span className="pill pill--on">{kind === "module" ? "启用" : "active"}</span>;
}

function EditorRow({ draft, setDraft, kindDef, allModules }) {
  return (
    <div className="taxonomy-edit-grid">
      <label>
        <span>代码 *</span>
        <input
          value={draft.code}
          onChange={(e) => setDraft({ ...draft, code: e.target.value })}
          placeholder={kindDef.codeHint}
          spellCheck={false}
        />
      </label>
      {kindDef.moduleField && (
        <label>
          <span>所属分组</span>
          <select
            value={draft.module_code || ""}
            onChange={(e) => setDraft({ ...draft, module_code: e.target.value || null })}
          >
            <option value="">(无)</option>
            {allModules.map((m) => (
              <option key={m.code} value={m.code}>{m.code}{m.display_name ? ` · ${m.display_name}` : ""}</option>
            ))}
          </select>
        </label>
      )}
      {kindDef.key === "module" && (
        <>
          <label>
            <span>父分组</span>
            <select
              value={draft.parent_group || "capability"}
              onChange={(e) => setDraft({ ...draft, parent_group: e.target.value })}
            >
              <option value="capability">capability (能力)</option>
              <option value="safety">safety (安全)</option>
              <option value="probe">probe (探针)</option>
              <option value="other">other</option>
            </select>
          </label>
          <label>
            <span>颜色 token</span>
            <input
              value={draft.color_token || ""}
              onChange={(e) => setDraft({ ...draft, color_token: e.target.value })}
              placeholder="mod-D1"
            />
          </label>
        </>
      )}
      <label>
        <span>显示名 *</span>
        <input
          value={draft.display_name}
          onChange={(e) => setDraft({ ...draft, display_name: e.target.value })}
          placeholder="如 数学推理"
        />
      </label>
      <label>
        <span>描述</span>
        <input
          value={draft.description || ""}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          placeholder="可选"
        />
      </label>
      <label>
        <span>排序</span>
        <input
          type="number"
          value={draft.sort_order ?? 0}
          onChange={(e) => setDraft({ ...draft, sort_order: parseInt(e.target.value || "0", 10) })}
        />
      </label>
      <label className="checkbox-line">
        <input
          type="checkbox"
          checked={!!draft.is_active}
          onChange={(e) => setDraft({ ...draft, is_active: e.target.checked ? 1 : 0 })}
        />
        <span>启用</span>
      </label>
    </div>
  );
}

export default function TaxonomyPage({ apiFetch, onToast }) {
  const { t } = useTranslation();
  const [kind, setKind] = useState("module");
  const [items, setItems] = useState([]);
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null); // {code, ...} or null
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/api/dict/${kind === "quota_tag" ? "quota_tags" : kind === "subtype" ? "subtypes" : "modules"}?include_inactive=true`);
      setItems(data?.items || []);
    } catch (err) {
      setError(String(err.message || err));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadModules() {
    try {
      const data = await apiFetch("/api/dict/modules?include_inactive=true");
      setModules(data?.items || []);
    } catch (err) {
      setModules([]);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  useEffect(() => {
    loadModules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function emptyDraft() {
    return {
      code: "",
      display_name: "",
      description: "",
      sort_order: 0,
      is_active: 1,
      parent_group: "capability",
      color_token: "",
      module_code: "",
    };
  }

  async function handleCreate(draft) {
    try {
      await apiFetch(`/api/dict/${kind === "quota_tag" ? "quota_tags" : kind === "subtype" ? "subtypes" : "modules"}`, {
        method: "POST",
        body: JSON.stringify(cleanPayload(draft)),
      });
      setCreating(false);
      await load();
      onToast && onToast("已新增分组");
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function handleUpdate(draft) {
    try {
      await apiFetch(`/api/dict/${kind === "quota_tag" ? "quota_tags" : kind === "subtype" ? "subtypes" : "modules"}/${encodeURIComponent(draft.code)}`, {
        method: "PUT",
        body: JSON.stringify(cleanPayload(draft)),
      });
      setEditing(null);
      await load();
      onToast && onToast("已保存");
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function handleDelete(code) {
    if (!window.confirm(`确定要归档 ${code} 吗?`)) return;
    try {
      await apiFetch(`/api/dict/${kind === "quota_tag" ? "quota_tags" : kind === "subtype" ? "subtypes" : "modules"}/${encodeURIComponent(code)}?hard=false`, {
        method: "DELETE",
      });
      await load();
      onToast && onToast("已归档");
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function handleHardDelete(code) {
    if (!window.confirm(`彻底删除 ${code} 吗?该操作不可恢复。`)) return;
    try {
      await apiFetch(`/api/dict/${kind === "quota_tag" ? "quota_tags" : kind === "subtype" ? "subtypes" : "modules"}/${encodeURIComponent(code)}?hard=true`, {
        method: "DELETE",
      });
      await load();
      onToast && onToast("已删除");
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  function cleanPayload(draft) {
    const clean = { ...draft };
    if (kind === "module") {
      clean.parent_group = clean.parent_group || "capability";
      clean.color_token = clean.color_token || "";
    } else {
      clean.module_code = clean.module_code || null;
    }
    clean.is_active = clean.is_active ? 1 : 0;
    clean.sort_order = parseInt(clean.sort_order || "0", 10) || 0;
    return clean;
  }

  const kindDef = KIND_DEFS.find((k) => k.key === kind) || KIND_DEFS[0];

  return (
    <section className="panel taxonomy-page">
      <div className="taxonomy-page-header">
        <h2 className="panel-title">分组管理</h2>
        <div className="taxonomy-tabs">
          {KIND_DEFS.map((k) => (
            <button
              key={k.key}
              type="button"
              className={`taxonomy-tab ${kind === k.key ? "is-active" : ""}`}
              onClick={() => { setKind(k.key); setCreating(false); setEditing(null); }}
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>

      <p className="muted-text">
        {kind === "module" && "题目分组(M 是 module)用于把题库分成 A1-A6 能力 / B1-B8 安全 / C1-C4 探针三层。分组元数据决定题库列表的 chip 颜色与题库新题目表单的模块下拉。"}
        {kind === "subtype" && "题型(Subtype)用于更细的题目家族,如 math_reasoning / format_constraint / stateful_simulation。"}
        {kind === "quota_tag" && "配额标签(Quota Tag)是题面上的细分配额标记,例如 rate_counting / profit_discount。"}
      </p>

      {error ? <div className="banner banner--error">{error}</div> : null}

      {creating ? (
        <CreateBar
          kindDef={kindDef}
          allModules={modules}
          onCancel={() => setCreating(false)}
          onSubmit={handleCreate}
        />
      ) : (
        <div className="taxonomy-toolbar">
          <button type="button" className="action-button primary" onClick={() => { setEditing(null); setCreating(true); }}>
            + 新增{kindDef.label.split(" ")[0]}
          </button>
          <span className="muted-text">共 {items.length} 条</span>
        </div>
      )}

      {loading ? <div className="muted-text">加载中…</div> : null}

      {!loading && (
        <div className="taxonomy-table-shell">
          <table className="data-table taxonomy-table">
            <thead>
              <tr>
                <th>代码</th>
                {kindDef.moduleField && <th>所属分组</th>}
                {kind === "module" && <th>父分组</th>}
                <th>显示名</th>
                <th>描述</th>
                <th>排序</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={kindDef.moduleField ? 8 : 7}><div className="muted-text">暂无数据,点击右上角新增按钮创建第一条记录。</div></td></tr>
              ) : items.map((item) => (
                <tr key={item.code} className={editing?.code === item.code ? "row-editing" : ""}>
                  {editing?.code === item.code ? (
                    <>
                      <td colSpan={kindDef.moduleField ? 7 : 6} className="taxonomy-edit-cell">
                        <EditorRow
                          draft={editing}
                          setDraft={setEditing}
                          kindDef={kindDef}
                          allModules={modules}
                        />
                        <div className="taxonomy-edit-actions">
                          <button type="button" className="action-button primary" onClick={() => handleUpdate(editing)}>保存</button>
                          <button type="button" className="action-button secondary" onClick={() => setEditing(null)}>取消</button>
                        </div>
                      </td>
                      <td><button type="button" className="mini-button danger" onClick={() => handleHardDelete(item.code)}>彻底删除</button></td>
                    </>
                  ) : (
                    <>
                      <td className="mono">{item.code}</td>
                      {kindDef.moduleField && <td>{item.module_code || "—"}</td>}
                      {kind === "module" && <td>{item.parent_group || "capability"}</td>}
                      <td>{item.display_name || "—"}</td>
                      <td>{item.description || "—"}</td>
                      <td>{item.sort_order ?? 0}</td>
                      <td><StatusTone kind={kind} isActive={!!item.is_active} /></td>
                      <td>
                        <div className="taxonomy-row-actions">
                          <button type="button" className="mini-button" onClick={() => setEditing({ ...item, is_active: item.is_active ? 1 : 0, sort_order: item.sort_order ?? 0 })}>编辑</button>
                          <button type="button" className="mini-button" onClick={() => handleDelete(item.code)}>{item.is_active ? "归档" : "已归档"}</button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CreateBar({ kindDef, allModules, onCancel, onSubmit }) {
  const [draft, setDraft] = useState(() => emptyDraft());
  return (
    <div className="taxonomy-create-bar">
      <div className="taxonomy-create-title">新增{kindDef.label.split(" ")[0]}</div>
      <EditorRow draft={draft} setDraft={setDraft} kindDef={kindDef} allModules={allModules} />
      <div className="taxonomy-edit-actions">
        <button type="button" className="action-button primary" onClick={() => {
          if (!draft.code || !draft.code.trim()) { window.alert("代码必填"); return; }
          if (!draft.display_name || !draft.display_name.trim()) { window.alert("显示名必填"); return; }
          onSubmit(draft);
        }}>保存</button>
        <button type="button" className="action-button secondary" onClick={onCancel}>取消</button>
      </div>
    </div>
  );
}

function emptyDraft() {
  return {
    code: "",
    display_name: "",
    description: "",
    sort_order: 0,
    is_active: 1,
    parent_group: "capability",
    color_token: "",
    module_code: "",
  };
}
