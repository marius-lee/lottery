/** 号码相关性 & 捆绑投注 (蒋加林, 2001 第三绝招)
 *
 *  交互模式: 用户选锚定号A → 系统推荐关联号B → 确认捆绑 → 生成时保证A+B同注
 */
import { store } from '../store.js';

/** 计算Lift: P(A∩B) / (P(A)×P(B)). Lift>1=正相关, <1=负相关 */
function computeLift(countA, countB, jointAB, totalPeriods) {
  const pA = countA / totalPeriods;
  const pB = countB / totalPeriods;
  const pAB = jointAB / totalPeriods;
  if (pA === 0 || pB === 0) return 0;
  return pAB / (pA * pB);
}

/**
 * 返回锚定号A的top关联号, 附Lift评分
 */
export function getBundledCandidates(anchor, type = 'red', topN = 8) {
  const max = type === 'red' ? 33 : 16;
  const data = store.DATA || [];
  const total = data.length;
  if (total < 10) return [];

  // count[A] = A出现总期数
  const count = new Array(max + 1).fill(0);
  const joint = Array.from({ length: max + 1 }, () => new Array(max + 1).fill(0));

  for (const row of data) {
    const nums = type === 'red' ? row.slice(1, 7) : [row[7]];
    for (const a of nums) count[a] += 1;
    for (const a of nums) {
      for (const b of nums) {
        if (a !== b) joint[a][b] += 1;
      }
    }
  }

  return Array.from({ length: max + 1 }, (_, b) => {
    if (b < 1 || b === anchor || joint[anchor][b] === 0) return null;
    return {
      num: b,
      prob: joint[anchor][b] / count[anchor],
      lift: computeLift(count[anchor], count[b], joint[anchor][b], total),
      joint: joint[anchor][b],
      countA: count[anchor],
      countB: count[b],
    };
  }).filter(Boolean).sort((x, y) => y.lift - x.lift).slice(0, topN);
}

/**
 * 渲染交互式捆绑投注选择器
 */
export function renderBundleSelector(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  let html = '<h4>捆绑投注</h4>';
  html += '<div style="font-size:11px;color:#94A3B8;margin-bottom:10px;">选一个锚定号, 系统推荐Lift最高的关联号, 确认后生成时保证同注</div>';

  // 锚定号选择器
  html += '<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">';
  html += '<span style="font-size:12px;color:#94A3B8;">锚定号 A:</span>';
  html += '<select id="bundleAnchor" onchange="refreshBundleCandidates()" style="padding:6px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);background:#1A1A2E;color:#E2E8F0;font-size:14px;">';
  html += '<option value="">-- 选择号码 --</option>';
  for (let n = 1; n <= 33; n++) {
    html += `<option value="${n}">${String(n).padStart(2, '0')}</option>`;
  }
  html += '</select>';

  // 当前捆绑状态
  const bundle = store.bundledPair;
  if (bundle) {
    html += `<span style="font-size:12px;color:#10B981;margin-left:8px;">已捆绑: <b>${String(bundle[0]).padStart(2,'0')}-${String(bundle[1]).padStart(2,'0')}</b></span>`;
    html += `<button onclick="clearBundle()" style="padding:4px 10px;border-radius:4px;border:1px solid rgba(239,68,68,0.3);background:rgba(239,68,68,0.1);color:#EF4444;font-size:11px;cursor:pointer;">清除</button>`;
  }
  html += '</div>';

  // 推荐列表
  html += '<div id="bundleCandidates" style="max-height:300px;overflow-y:auto;">';
  html += '<div style="font-size:11px;color:#64748B;">选择锚定号后显示推荐</div>';
  html += '</div>';

  el.innerHTML = html;
}

/**
 * 刷新推荐列表
 */
window.refreshBundleCandidates = function () {
  const anchor = parseInt(document.getElementById('bundleAnchor').value);
  const container = document.getElementById('bundleCandidates');
  if (!container) return;
  if (!anchor) {
    container.innerHTML = '<div style="font-size:11px;color:#64748B;">选择锚定号后显示推荐</div>';
    return;
  }

  const candidates = getBundledCandidates(anchor);
  if (candidates.length === 0) {
    container.innerHTML = '<div style="font-size:11px;color:#94A3B8;">数据不足, 需要≥10期</div>';
    return;
  }

  let html = '<table class="bt-table"><thead><tr><th>关联号B</th><th>P(B|A)</th><th>Lift</th><th>A∩B</th><th>操作</th></tr></thead><tbody>';
  for (const c of candidates) {
    const liftClass = c.lift >= 1.2 ? '#10B981' : c.lift >= 1.0 ? '#FBBF24' : '#EF4444';
    html += `<tr>
      <td style="color:#3366cc;font-weight:600;">${String(c.num).padStart(2, '0')}</td>
      <td>${(c.prob * 100).toFixed(1)}%</td>
      <td style="color:${liftClass};font-weight:600;">${c.lift.toFixed(2)}</td>
      <td>${c.joint}/${c.countA}</td>
      <td><button onclick="confirmBundle(${anchor},${c.num})"
        style="padding:4px 12px;border-radius:4px;border:none;background:#7C3AED;color:#fff;font-size:11px;cursor:pointer;">捆绑</button></td>
    </tr>`;
  }
  html += '</tbody></table>';
  html += '<div style="font-size:10px;color:#64748B;margin-top:4px;">Lift&gt;1.2=强正相关, 1.0-1.2=弱相关, &lt;1.0=负相关(不推荐)</div>';
  container.innerHTML = html;
};

/**
 * 确认捆绑对
 */
window.confirmBundle = function (a, b) {
  store.bundledPair = [a, b];
  renderBundleSelector('correlationContent');
};

/**
 * 清除捆绑
 */
window.clearBundle = function () {
  store.bundledPair = null;
  renderBundleSelector('correlationContent');
};
