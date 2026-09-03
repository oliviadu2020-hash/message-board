/* 协作审计台 · 渲染逻辑
 * 数据源：优先 fetch site/data.json（Actions 派生产物），失败则回退内置 MOCK_DATA。
 * 路由：URL Hash —— #view=stats | messages | kanban
 */
"use strict";

/* ---------- 数据契约（与 Actions 生成的 data.json 对齐） ----------
 * {
 *   generated_at: "2026-09-03T15:40:00+08:00",
 *   messages: [{ id, type, time, from, to, subject, ref? }],   // type: 邮件|协同单|回执|退回
 *   tasks:    [{ id, title, owner, state, updated_at, blocked_by?, ref? }]
 * }                                                           // state: todo|doing|blocked|review|done
 */

const MOCK_DATA = {
  generated_at: "2026-09-03T15:40:00+08:00",
  messages: [
    { id: "20260903-1540", type: "邮件",   time: "09-03 15:40", from: "alice",   to: "所有人",   subject: "频道页改版排期同步" },
    { id: "20260903-1522", type: "协同单", time: "09-03 15:22", from: "bob",     to: "alice",   subject: "T-003 早鸟票库存对账", ref: "T-003" },
    { id: "20260903-1510", type: "回执",   time: "09-03 15:10", from: "alice",   to: "bob",     subject: "已完成数据核对", ref: "20260903-1455" },
    { id: "20260903-1455", type: "协同单", time: "09-03 14:55", from: "bob",     to: "alice",   subject: "申请核对交易数据" },
    { id: "20260903-1441", type: "退回",   time: "09-03 14:41", from: "CI 邮局", to: "carol",   subject: "缺少 --ref，协同单被退回", ref: "20260903-1438" },
    { id: "20260903-1438", type: "协同单", time: "09-03 14:38", from: "carol",   to: "dave",    subject: "plus 会员页联调请求" },
    { id: "20260903-1415", type: "邮件",   time: "09-03 14:15", from: "dave",    to: "plus用增", subject: "用增活动配置说明" },
    { id: "20260903-1330", type: "回执",   time: "09-03 13:30", from: "carol",   to: "bob",     subject: "确认收到排期", ref: "20260903-1120" },
    { id: "20260903-1120", type: "邮件",   time: "09-03 11:20", from: "bob",     to: "交易系统", subject: "对账窗口变更通知" },
    { id: "20260902-1745", type: "邮件",   time: "09-02 17:45", from: "alice",   to: "所有人",   subject: "本周站会纪要" },
    { id: "20260902-1602", type: "回执",   time: "09-02 16:02", from: "dave",    to: "alice",   subject: "纪要已读，无异议", ref: "20260902-1745" },
    { id: "20260902-0950", type: "邮件",   time: "09-02 09:50", from: "carol",   to: "频道页",   subject: "投放物料尺寸确认" }
  ],
  tasks: [
    { id: "T-001", title: "频道页首屏性能优化",   owner: "alice", state: "doing",   updated_at: "09-03 15:02", ref: "20260903-1455" },
    { id: "T-002", title: "交易系统对账脚本升级", owner: "bob",   state: "review",  updated_at: "09-03 14:20" },
    { id: "T-003", title: "早鸟票库存对账",       owner: "bob",   state: "blocked", updated_at: "09-03 11:12", blocked_by: "T-002", ref: "20260903-1522" },
    { id: "T-004", title: "plus 会员页文案走查",  owner: "carol", state: "todo",    updated_at: "09-02 18:03" },
    { id: "T-005", title: "用增活动灰度方案",     owner: "dave",  state: "doing",   updated_at: "09-03 10:47" },
    { id: "T-006", title: "审计网页 v1 上线",     owner: "alice", state: "done",    updated_at: "09-01 19:26" },
    { id: "T-007", title: "CI 邮局规则补集",      owner: "dave",  state: "todo",    updated_at: "09-01 15:31" },
    { id: "T-008", title: "消息流水 ref 链可视化", owner: "carol", state: "doing",   updated_at: "09-03 15:20" },
    { id: "T-009", title: "通知台账分页策略",     owner: "bob",   state: "doing",   updated_at: "09-03 14:55" },
    { id: "T-010", title: "早鸟票余票告警阈值",   owner: "dave",  state: "doing",   updated_at: "09-03 14:02" },
    { id: "T-011", title: "频道页 AB 实验收口",   owner: "alice", state: "doing",   updated_at: "09-03 11:40" },
    { id: "T-012", title: "交易系统日志脱敏",     owner: "bob",   state: "doing",   updated_at: "09-02 17:25" },
    { id: "T-013", title: "plus 权益页缓存治理",  owner: "carol", state: "doing",   updated_at: "09-02 16:48" },
    { id: "T-014", title: "看板列滚动体验优化",   owner: "dave",  state: "doing",   updated_at: "09-02 15:33" },
    { id: "T-015", title: "公文模板 lint 规则",   owner: "alice", state: "doing",   updated_at: "09-02 14:10" },
    { id: "T-016", title: "用增漏斗埋点补全",     owner: "bob",   state: "doing",   updated_at: "09-02 11:26" },
    { id: "T-017", title: "数据快照时间校准",     owner: "carol", state: "doing",   updated_at: "09-01 18:54" },
    { id: "T-018", title: "五态流转图配色定稿",   owner: "dave",  state: "review",  updated_at: "09-01 17:02" },
    { id: "T-019", title: "审计页空态插画",       owner: "alice", state: "todo",    updated_at: "09-01 15:40" }
  ]
};

/* ---------- 视觉语义映射 ---------- */
const MSG_STYLE = {
  "邮件":   "var(--indigo)",
  "协同单": "var(--cinnabar)",
  "回执":   "var(--plum)",
  "退回":   "var(--ochre)"
};
const STATE_STYLE = {
  todo:    { label: "未开始", c: "var(--ink-gray)" },
  doing:   { label: "进行中", c: "var(--indigo)"   },
  blocked: { label: "阻塞",   c: "var(--ochre)"    },
  review:  { label: "待确认", c: "var(--amber)"    },
  done:    { label: "已完成", c: "var(--pine)"     }
};
const STATE_ORDER = ["todo", "doing", "blocked", "review", "done"];

let DATA = null;
let msgFilter = "全部";

/* ---------- 工具 ---------- */
const $  = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const fmtTime = iso => {
  try {
    const d = new Date(iso);
    const p = n => String(n).padStart(2, "0");
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  } catch { return iso; }
};
const countType = t => DATA.messages.filter(m => m.type === t).length;
const countState = s => DATA.tasks.filter(t => t.state === s).length;

/* ---------- 概览 ---------- */
function renderStats() {
  const mail = countType("邮件"), collab = countType("协同单"),
        receipt = countType("回执"), bounce = countType("退回");
  const doing = countState("doing"), blocked = countState("blocked");
  const loopRate = collab ? Math.round((receipt / collab) * 100) + "%" : "—";
  const cards = [
    { k: "信件流通总量", v: DATA.messages.length, s: `协同单 ${collab} / 回执 ${receipt} / 邮件 ${mail}` },
    { k: "协同单闭环率", v: loopRate,            s: `已应答 ${receipt} / 派发总单量 ${collab}` },
    { k: "活跃协作任务", v: doing + blocked,      s: `进行中 ${doing} · 阻塞 ${blocked}` },
    { k: "受阻事项",     v: blocked,              s: "需跨团队协商推进", danger: blocked > 0 }
  ];
  const grid = $("#stats-grid");
  grid.innerHTML = "";
  cards.forEach(c => {
    grid.append(el("div", "card stat",
      `<div class="k">${c.k}</div>
       <div class="v${c.danger ? " danger" : ""}">${c.v}</div>
       <div class="s">${c.s}</div>`));
  });

  // 任务五态分布（横向条）
  const sb = $("#state-bars");
  sb.innerHTML = "";
  const max = Math.max(1, ...STATE_ORDER.map(countState));
  STATE_ORDER.forEach(k => {
    const st = STATE_STYLE[k], n = countState(k);
    sb.append(el("div", "bar-row",
      `<span class="name">${st.label}</span>
       <span class="track"><span class="fill" style="--c:${st.c};width:${(n / max) * 100}%"></span></span>
       <span class="n">${n}</span>`));
  });

  // 协作活跃度排行（收发合计，取前 6）
  const tally = {};
  DATA.messages.forEach(m => {
    tally[m.from] = (tally[m.from] || 0) + 1;
    if (m.to && !m.to.includes("所有")) tally[m.to] = (tally[m.to] || 0) + 1;
  });
  const top = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const rb = $("#rank-bars");
  rb.innerHTML = "";
  const rmax = Math.max(1, ...top.map(x => x[1]));
  top.forEach(([name, n], i) => {
    rb.append(el("div", "bar-row rank-row",
      `<span class="name">${i + 1}. ${name}</span>
       <span class="track"><span class="fill" style="--c:var(--accent);width:${(n / rmax) * 100}%"></span></span>
       <span class="n">${n}</span>`));
  });
}

/* ---------- 消息审计 ---------- */
function renderMsgFilters() {
  const types = ["全部", "邮件", "协同单", "回执", "退回"];
  const box = $("#msg-filters");
  box.innerHTML = "";
  types.forEach(t => {
    const c = el("button", "chip" + (t === msgFilter ? " on" : ""), t);
    c.style.setProperty("--chip-c", MSG_STYLE[t] || "var(--text)");
    c.addEventListener("click", () => { msgFilter = t; renderMsgFilters(); renderMessages(); });
    box.append(c);
  });
}
function renderMessages() {
  const list = $("#msg-list");
  list.innerHTML = "";
  const rows = DATA.messages.filter(m => msgFilter === "全部" || m.type === msgFilter);
  if (!rows.length) { list.append(el("div", "empty", "暂无该类型公文")); return; }
  rows.forEach(m => {
    const row = el("div", "msg");
    row.append(
      el("span", "time", m.time),
      el("span", "badge", m.type),
      el("span", "subj", `${m.subject}${m.ref ? `<span class="ref">↩ ${m.ref}</span>` : ""}`),
      el("span", "route", `${m.from}<i>→</i>${m.to}`)
    );
    row.querySelector(".badge").style.setProperty("--bc", MSG_STYLE[m.type] || "var(--text)");
    list.append(row);
  });
}

/* ---------- 任务看板 ---------- */
function renderKanban() {
  const board = $("#kanban");
  board.innerHTML = "";
  STATE_ORDER.forEach(k => {
    const st = STATE_STYLE[k];
    const tasks = DATA.tasks.filter(t => t.state === k);
    const col = el("div", "kcol");
    col.style.setProperty("--kc", st.c);
    col.append(el("h3", null, `<span class="sw"></span>${st.label}<span class="cnt">${tasks.length}</span>`));
    tasks.forEach(t => {
      const card = el("div", "kcard");
      card.style.setProperty("--kc", st.c);
      card.append(
        el("div", "id", t.id),
        el("div", "tt", t.title),
        el("div", "meta", `<span>@${t.owner}</span><span>${t.updated_at}</span>`)
      );
      if (t.blocked_by) card.append(el("div", "blk", `blocked_by ${t.blocked_by}`));
      col.append(card);
    });
    board.append(col);
  });
}

/* ---------- 路由与启动 ---------- */
const VIEWS = ["stats", "messages", "kanban"];
function show(name) {
  if (!VIEWS.includes(name)) name = "stats";
  VIEWS.forEach(v => { $("#view-" + v).hidden = v !== name; });
  document.querySelectorAll(".seg button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === name));
  if (location.hash !== "#view=" + name) history.replaceState(null, "", "#view=" + name);
}
document.querySelectorAll(".seg button").forEach(b =>
  b.addEventListener("click", () => show(b.dataset.view)));
window.addEventListener("hashchange", () => show(location.hash.replace("#view=", "")));

async function boot() {
  try {
    const r = await fetch("data.json", { cache: "no-store" });
    DATA = r.ok ? await r.json() : MOCK_DATA;
  } catch { DATA = MOCK_DATA; }
  $("#snap-time").textContent = fmtTime(DATA.generated_at);
  renderStats(); renderMsgFilters(); renderMessages(); renderKanban();
  show(location.hash.replace("#view=", "") || "stats");
}
boot();
