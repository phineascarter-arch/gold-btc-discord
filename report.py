"""每日三次現貨價格報告；金鑰只從環境變數讀取。"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

UTC = timezone.utc
API = 'https://api.gold-api.com'

def taipei_time(value):
    return value.astimezone(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M %z')

def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError('價格必須是有限的正數')
    return result

def parse_history(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('歷史資料為空或格式錯誤')
    result = {}
    for row in rows:
        day = row['day']
        datetime.strptime(day, '%Y-%m-%d')
        if day in result:
            raise ValueError('歷史資料包含重複日期')
        result[day] = positive(row['avg_price'])
    return dict(sorted(result.items()))

def validate_coverage(series, now):
    dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in series]
    if len(dates) < 15 or (now.date()-min(dates)).days < 25:
        raise ValueError('歷史資料不足，無法產生近 30 天報告')
    if (now.date()-max(dates)).days > 4 or max(dates) > now.date():
        raise ValueError('歷史資料過期或包含未來日期')

def parse_quote(data, symbol, now):
    if data['symbol'] != symbol or data.get('currency', 'USD') != 'USD':
        raise ValueError('報價商品代號或幣別不符')
    stamp = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp > now + timedelta(minutes=5):
        raise ValueError('報價時間格式錯誤或晚於現在')
    return {'price': positive(data['price']), 'updatedAt': stamp.isoformat()}

def normalized(gold, btc):
    common = sorted(set(gold) & set(btc))
    if len(common) < 2:
        raise ValueError('兩個商品的共同日期不足')
    start = common[0]
    return ({d: gold[d] / gold[start] * 100 for d in common},
            {d: btc[d] / btc[start] * 100 for d in common})

def get_json(path, key=None, params=None):
    import requests
    for attempt in range(3):
        try:
            response = requests.get(API + path, params=params,
                                    headers={'x-api-key':key} if key else {}, timeout=(10,30))
        except requests.RequestException:
            if attempt == 2:
                raise RuntimeError('行情 API 連線失敗') from None
            time.sleep(2 ** (attempt+1))
            continue
        if response.status_code in (401,403):
            raise RuntimeError('行情 API 授權失敗：請檢查 GOLD_API_KEY 與免費方案權限')
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 2:
                time.sleep(5 * (attempt+1))
                continue
        if response.status_code != 200:
            raise RuntimeError(f'行情 API HTTP 狀態碼：{response.status_code}')
        try:
            return response.json()
        except ValueError:
            raise RuntimeError('行情 API 回傳的 JSON 格式錯誤') from None
    raise RuntimeError('行情 API 已達重試次數上限')

def fetch_report(key, now):
    # 最近 30 個 UTC 日曆日期，包含可能尚未結束的當日。
    start = now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=29)
    result = {'generated_at':now.isoformat(),'source':'https://gold-api.com', 'assets':{}}
    for symbol in ('XAU','BTC'):
        rows = get_json('/history', key, {'symbol':symbol,'startTimestamp':int(start.timestamp()),
                       'endTimestamp':int(now.timestamp()),'groupBy':'day','aggregation':'avg','orderBy':'asc'})
        series = parse_history(rows)
        series = {d:p for d,p in series.items() if start.date().isoformat() <= d <= now.date().isoformat()}
        validate_coverage(series,now)
        time.sleep(1.1)
        quote = parse_quote(get_json('/price/'+symbol),symbol,now)
        result['assets'][symbol] = {'history':series,'quote':quote}
        time.sleep(1.1)
    return result

def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib import font_manager
    # 優先使用繁體中文字型；兼容 GitHub Ubuntu、Windows 與 macOS。
    available = {font.name for font in font_manager.fontManager.ttflist}
    candidates = ['Noto Sans CJK TC', 'Noto Sans CJK JP', 'Microsoft JhengHei', 'PingFang TC']
    chosen = next((name for name in candidates if name in available), None)
    if not chosen:
        raise RuntimeError('缺少中文字型：Ubuntu 請安裝 fonts-noto-cjk，Windows 請確認微軟正黑體可用')
    plt.rcParams['font.sans-serif'] = [chosen]
    plt.rcParams['axes.unicode_minus'] = False
    now = datetime.fromisoformat(data['generated_at'])
    histories = [data['assets'][s]['history'] for s in ('XAU','BTC')]
    comparison = normalized(*histories)
    days = [(now-timedelta(days=i)).date() for i in range(29,-1,-1)]
    colors = ['#d5a62d','#f08032']
    with plt.style.context('dark_background'):
        fig,axes = plt.subplots(3,1,figsize=(12,12),sharex=True)
        fig.patch.set_facecolor('#101722')
        for ax in axes:
            ax.set_facecolor('#151f2d')
            ax.grid(alpha=.15)
        for i,(symbol,unit) in enumerate([('XAU','美元／金衡盎司'),('BTC','美元／枚')]):
            values = [histories[i].get(d.isoformat(),float('nan')) for d in days]
            axes[i].plot(days,values,color=colors[i],marker='.',linewidth=2)
            quote = data['assets'][symbol]['quote']
            axes[i].set_title(f'{symbol}｜最新報價：${quote["price"]:,.2f}',loc='left',fontsize=14)
            axes[i].set_ylabel(unit)
            stamp = datetime.fromisoformat(quote['updatedAt'])
            axes[i].text(.01,.92,'報價時間：'+taipei_time(stamp),transform=axes[i].transAxes,fontsize=9)
        for i,symbol in enumerate(('XAU','BTC')):
            axes[2].plot(days,[comparison[i].get(d.isoformat(),float('nan')) for d in days],
                         color=colors[i],marker='.',label=symbol,linewidth=2)
        axes[2].set_title('相對走勢｜首個共同日期＝100',loc='left')
        axes[2].legend()
        axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        axes[2].set_xlabel('UTC 日期｜每日平均價；當日資料可能尚未完整')
        title = '國際現貨黃金與比特幣｜最近 30 天'
        if data.get('synthetic'):
            title = '版型示範｜模擬資料，非真實行情'
        fig.suptitle(title+'\n產生時間：'+taipei_time(now),fontsize=16)
        fig.text(.06,.015,'資料來源：gold-api.com｜空白代表沒有觀測資料；未補造週末價格。',fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.94))
        fig.savefig(output,dpi=140)
        plt.close(fig)

def message(data):
    now = datetime.fromisoformat(data['generated_at'])
    lines = ['**黃金／比特幣｜近 30 天趨勢**', '產生時間：'+taipei_time(now)]
    for symbol,unit in [('XAU','美元／金衡盎司'),('BTC','美元／枚')]:
        item = data['assets'][symbol]
        quote = item['quote']
        stamp = datetime.fromisoformat(quote['updatedAt'])
        age = now-stamp
        note = ' ⚠ 非即時：可能休市或來源延遲' if age > timedelta(hours=2) else ''
        lines.append(f'{symbol}：{quote["price"]:,.2f} {unit}{note}\n報價時間：{taipei_time(stamp)}')
    lines.append('曲線為 UTC 每日平均價，當日可能尚未完整；非收盤價。缺值留白。\n來源：https://gold-api.com')
    return '\n'.join(lines)

def send_discord(webhook, content, chart):
    import requests
    parsed = urlparse(webhook)
    if parsed.scheme != 'https' or parsed.hostname != 'discord.com' or not parsed.path.startswith('/api/webhooks/'):
        raise ValueError('DISCORD_WEBHOOK_URL 必須是 Discord 的 HTTPS Webhook 網址')
    for attempt in range(2):
        try:
            with open(chart,'rb') as image:
                response = requests.post(webhook,params={'wait':'true'},
                    data={'payload_json':json.dumps({'content':content,'allowed_mentions':{'parse':[]}})},
                    files={'files[0]':('trend.png',image,'image/png')},timeout=(10,45),allow_redirects=False)
        except requests.RequestException:
            # 逾時不代表未送達；不盲目重送，以降低重複訊息的風險。
            raise RuntimeError('Discord 是否送達尚不確定；重跑前請先檢查頻道') from None
        if response.status_code == 429 and attempt == 0:
            try:
                delay = float(response.json()['retry_after'])
            except (ValueError,KeyError,TypeError):
                raise RuntimeError('Discord 要求降低頻率；請稍後再試') from None
            if not 0 <= delay <= 45:
                raise RuntimeError('Discord 要求降低頻率；請稍後再試')
            time.sleep(delay+1)
            continue
        if response.status_code != 200:
            raise RuntimeError(f'Discord HTTP {response.status_code}；重跑前請先檢查頻道')
        try:
            return str(response.json()['id'])
        except (ValueError,KeyError):
            raise RuntimeError('未取得 Discord 送達確認；重跑前請先檢查頻道') from None
    raise RuntimeError('尚未確認 Discord 已送達')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true',help='抓取真實資料並產圖，但不發送到 Discord')
    args = parser.parse_args()
    key = os.environ.get('GOLD_API_KEY','').strip()
    webhook = os.environ.get('DISCORD_WEBHOOK_URL','').strip()
    if not key or (not args.dry_run and not webhook):
        raise ValueError('請設定 GOLD_API_KEY；非預覽模式也需設定 DISCORD_WEBHOOK_URL')
    state_path = Path('data/sent.json')
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    run_id = os.environ.get('GITHUB_RUN_ID')
    if run_id and run_id in state and not args.dry_run:
        print('這次 GitHub 執行已有發送收據，略過重複發送。')
        return
    now = datetime.now(UTC)
    data = fetch_report(key,now)
    output = Path('artifacts')
    output.mkdir(exist_ok=True)
    chart = output/'trend.png'
    render(data,chart)
    text = message(data)
    (output/'report.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    (output/'message.txt').write_text(text,encoding='utf-8')
    if args.dry_run:
        print('預覽完成，尚未發送 Discord 訊息。')
        return
    message_id = send_discord(webhook,text,chart)
    state_path.parent.mkdir(exist_ok=True)
    if run_id:
        state[run_id] = {'message_id':message_id,'sent_at':now.isoformat()}
        state_path.write_text(json.dumps(dict(list(state.items())[-180:]),indent=2),encoding='utf-8')
    (state_path.parent/'latest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('已確認 Discord 訊息送達。')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # 不輸出可能包含金鑰的例外細節、網址、標頭或回應內容。
        if isinstance(exc,(ValueError,RuntimeError)):
            print('錯誤：'+str(exc),file=sys.stderr)
        else:
            print('錯誤：非預期回應或本機錯誤（'+type(exc).__name__+')',file=sys.stderr)
        sys.exit(1)
