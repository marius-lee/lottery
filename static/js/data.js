/** 数据加载模块 — 从服务器数据库加载，无硬编码fallback */
import { store, updateData } from './store.js';

/** 页面初始化时从服务器加载数据 */
export async function loadFromServer() {
  try {
    const resp = await fetch('/api/data');
    const json = await resp.json();
    if (json.ok && json.data && json.data.length > 0) {
      updateData(json.data);
      const el = document.getElementById('dataMsg');
      if (el) {
        el.textContent = `已加载 ${json.total || json.count} 期 (${json.source})`;
        el.style.color = '#33aa33';
        setTimeout(() => { el.textContent = ''; }, 3000);
      }
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}

/** 兼容旧接口: 无默认数据，始终从服务器加载 */
export function loadDefaultData() {
  // v5: 不再硬编码数据，触发异步加载
  loadFromServer().catch(() => {});
}

/** 增量更新: 从服务器拉取最新数据 */
export async function fetchLatestData() {
  const btn = document.getElementById('dataToggle');
  const text = document.getElementById('dataBtnText');
  const msg = document.getElementById('dataMsg');
  if (!btn || btn.classList.contains('fetching')) return;
  btn.classList.add('fetching');
  if (text) text.textContent = '正在拉取...';
  if (msg) { msg.textContent = ''; msg.style.color = '#999'; }

  try {
    const resp = await fetch('/api/fetch?force=1');
    const json = await resp.json();
    btn.classList.remove('fetching');
    if (text) text.textContent = '更新数据';
    if (json.ok) {
      updateData(json.data);
      if (msg) {
        const extra = json.newCount ? ` (新增${json.newCount}期)` : '';
        msg.textContent = `✓ ${json.source} | ${json.count}期${extra}`;
        msg.style.color = '#33aa33';
      }
    } else {
      if (msg) { msg.textContent = json.msg; msg.style.color = '#cc3333'; }
    }
  } catch (e) {
    btn.classList.remove('fetching');
    if (text) text.textContent = '更新数据';
    if (msg) {
      const detail = e.message || e.toString();
      msg.textContent = `连接失败: ${detail}。请确认已启动 python3 app.py`;
      msg.style.color = '#cc3333';
    }
  }
  setTimeout(() => { if (msg) msg.textContent = ''; }, 6000);
}
