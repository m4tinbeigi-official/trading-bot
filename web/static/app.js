// Rick Sanchez MT5 Quant Suite - Live WebSocket Client

let ws = null;
let reconnectTimer = null;

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    addLogLine("🟢 اتصال WebSocket به سرور ربات با موفقیت برقرار شد.", "win");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "TELEMETRY") {
        updateDashboard(data);
      }
    } catch (e) {
      console.error("Error parsing WS telemetry:", e);
    }
  };

  ws.onclose = () => {
    addLogLine("🟡 ارتباط WebSocket قطع شد. تلاش مجدد تا ۳ ثانیه دیگر...", "warn");
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
      }, 3000);
    }
  };

  ws.onerror = (err) => {
    console.error("WebSocket Error:", err);
  };
}

function updateDashboard(data) {
  const acc = data.account || {};
  const positions = data.positions || [];
  const history = data.closed_trades || [];
  const quotes = data.quotes || {};

  // 1. Mode Badge
  const modeBadge = document.getElementById("mode-badge");
  const modeText = document.getElementById("mode-text");
  if (data.execution_mode === "LIVE_MT5" || acc.mode === "LIVE_MT5") {
    modeBadge.className = "mode-badge live";
    modeText.innerText = "🟢 LIVE MT5 BRIDGE";
  } else {
    modeBadge.className = "mode-badge paper";
    modeText.innerText = "🟡 PAPER SIMULATOR";
  }

  // 2. Metrics
  const balance = acc.balance || 0;
  const equity = acc.equity || 0;
  const freeMargin = acc.margin_free || 0;
  const marginUsed = acc.margin || 0;
  const unrealized = equity - balance;

  document.getElementById("val-balance").innerText = `$${balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById("val-equity").innerText = `$${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById("val-margin-free").innerText = `$${freeMargin.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById("sub-margin-used").innerText = `مارجین درگیر: $${marginUsed.toFixed(2)}`;
  
  const pnlPct = balance > 0 ? ((unrealized / balance) * 100) : 0;
  const pnlSub = document.getElementById("sub-unrealized-pnl");
  pnlSub.innerText = `سود باز: ${unrealized >= 0 ? '+' : ''}$${unrealized.toFixed(2)} (${pnlPct.toFixed(2)}%)`;
  pnlSub.style.color = unrealized >= 0 ? "var(--color-green)" : "var(--color-red)";

  // 3. Win Rate & Trade Count
  const totalClosed = history.length;
  const winCount = history.filter(h => (h.profit || 0) > 0).length;
  const winRate = totalClosed > 0 ? ((winCount / totalClosed) * 100).toFixed(1) : "0.0";
  document.getElementById("val-win-rate").innerText = `${winRate}%`;
  document.getElementById("sub-trades-count").innerText = `تعداد معاملات بسته: ${totalClosed} (${winCount} برنده)`;

  // 4. Circuit Breaker Banner
  const alertBanner = document.getElementById("alert-banner");
  if (data.circuit_breaker) {
    alertBanner.classList.remove("hidden");
    document.getElementById("alert-msg").innerText = data.circuit_breaker_reason || "سقف ریسک روزانه نقض شد. ورود به معامله متوقف شد.";
  } else {
    alertBanner.classList.add("hidden");
  }

  // 5. Market Quotes
  for (const [sym, q] of Object.entries(quotes)) {
    const sLower = sym.toLowerCase();
    const elBid = document.getElementById(`price-${sLower}-bid`);
    const elAsk = document.getElementById(`price-${sLower}-ask`);
    if (elBid && q.bid) elBid.innerText = `Bid: ${q.bid.toFixed(sym.includes("EUR") || sym.includes("GBP") ? 5 : 2)}`;
    if (elAsk && q.ask) elAsk.innerText = `Ask: ${q.ask.toFixed(sym.includes("EUR") || sym.includes("GBP") ? 5 : 2)}`;
  }

  // 6. Active Positions Table
  renderPositionsTable(positions);

  // 7. Closed Trades Table
  renderHistoryTable(history);

  // 8. Session Highlighting
  updateSessionBadges();
}

function renderPositionsTable(positions) {
  const tbody = document.getElementById("positions-tbody");
  document.getElementById("positions-count").innerText = `${positions.length} پوزیشن فعال`;

  if (!positions || positions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">در حال حاضر هیچ پوزیشن بازی وجود ندارد.</td></tr>`;
    return;
  }

  tbody.innerHTML = positions.map(p => {
    const isBuy = (p.side || "").toUpperCase() === "BUY";
    const profit = p.profit || 0;
    const profitClass = profit >= 0 ? "pnl-positive" : "pnl-negative";
    return `
      <tr>
        <td>#${p.ticket}</td>
        <td><strong>${p.symbol}</strong></td>
        <td><span class="${isBuy ? 'tag-buy' : 'tag-sell'}">${p.side}</span></td>
        <td>${p.volume}</td>
        <td>${p.entry_price}</td>
        <td>${p.current_price || p.entry_price}</td>
        <td>${p.stop_loss || '--'}</td>
        <td>${p.take_profit || '--'}</td>
        <td class="${profitClass}">${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}</td>
        <td>${p.open_time || '--'}</td>
      </tr>
    `;
  }).join("");
}

function renderHistoryTable(history) {
  const tbody = document.getElementById("history-tbody");
  document.getElementById("history-count").innerText = `${history.length} معامله`;

  if (!history || history.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">هنوز معامله‌ای بسته نشده است.</td></tr>`;
    return;
  }

  tbody.innerHTML = [...history].reverse().map(h => {
    const isBuy = (h.side || "").toUpperCase() === "BUY";
    const profit = h.profit || 0;
    const profitClass = profit >= 0 ? "pnl-positive" : "pnl-negative";
    return `
      <tr>
        <td>#${h.ticket}</td>
        <td><strong>${h.symbol}</strong></td>
        <td><span class="${isBuy ? 'tag-buy' : 'tag-sell'}">${h.side}</span></td>
        <td>${h.volume}</td>
        <td>${h.entry_price}</td>
        <td>${h.exit_price}</td>
        <td class="${profitClass}">${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}</td>
        <td><span class="session-badge">${h.reason || 'EXIT'}</span></td>
        <td>${h.close_time || '--'}</td>
      </tr>
    `;
  }).join("");
}

function updateSessionBadges() {
  const utcHour = new Date().getUTCHours();
  
  // London: 08:00 - 16:00 UTC
  const isLondon = utcHour >= 8 && utcHour < 16;
  // NY: 13:00 - 21:00 UTC
  const isNY = utcHour >= 13 && utcHour < 21;
  // Tokyo: 00:00 - 08:00 UTC
  const isTokyo = utcHour >= 0 && utcHour < 8;

  toggleBadge("session-london", isLondon);
  toggleBadge("session-ny", isNY);
  toggleBadge("session-tokyo", isTokyo);
}

function toggleBadge(id, isActive) {
  const el = document.getElementById(id);
  if (el) {
    if (isActive) el.classList.add("active");
    else el.classList.remove("active");
  }
}

function addLogLine(text, type = "info") {
  const box = document.getElementById("console-box");
  const time = new Date().toLocaleTimeString('en-GB');
  const line = document.createElement("div");
  line.className = `log-line ${type}`;
  line.innerText = `[${time}] ${text}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

// Controls
document.getElementById("btn-panic").addEventListener("click", async () => {
  if (!confirm("⚠️ آیا از بستن اضطراری تمام پوزیشن‌ها و توقف ربات اطمینان دارید؟")) return;
  try {
    const res = await fetch("/api/panic", { method: "POST" });
    const data = await res.json();
    addLogLine(`🚨 دستور بستن اضطراری اعمال شد: ${data.closed_positions} پوزیشن بسته شد.`, "loss");
  } catch (e) {
    console.error("Panic error:", e);
  }
});

document.getElementById("btn-toggle-bot").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/toggle", { method: "POST" });
    const data = await res.json();
    const isRunning = data.bot_running;
    document.getElementById("btn-toggle-icon").innerText = isRunning ? "⏸️" : "▶️";
    document.getElementById("btn-toggle-text").innerText = isRunning ? "توقف ربات" : "شروع مجدد ربات";
    addLogLine(`وضعیت اجرایی ربات تغییر یافت به: ${isRunning ? 'فعال (ACTIVE)' : 'متوقف (PAUSED)'}`, isRunning ? "win" : "warn");
  } catch (e) {
    console.error("Toggle error:", e);
  }
});

document.getElementById("btn-clear-logs").addEventListener("click", () => {
  document.getElementById("console-box").innerHTML = "";
});

// Init
window.addEventListener("DOMContentLoaded", () => {
  connectWebSocket();
  updateSessionBadges();
  setInterval(updateSessionBadges, 60000);
});
