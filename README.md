# 黃金與比特幣：Discord 自動趨勢圖

每天台灣時間 **00:00（午夜）、08:00 與 12:00（中午）**，發送最近 30 天的 XAU/USD 現貨黃金、BTC/USD 趨勢圖到指定 Discord 文字頻道。

## 免費資料來源確認（2026-11-26）

採用 **gold-api.com**，注意名稱有連字號，不是 goldapi.dev 或 goldapi.io。

- [官方價格表](https://gold-api.com/pricing)：Free 方案即時報價免費；歷史與 OHLC 共用每小時 10 次查詢。
- [官方 API 參考](https://gold-api.com/llms.txt)：XAU 是現貨黃金、單位為金衡盎司；預設 USD。同時支援 BTC。歷史日資料使用 `/history`，需免費 API Key。
- [使用條款](https://gold-api.com/terms)：資料按現狀提供，不保證不中斷。
- 每次報告需要 2 次歷史查詢、2 次即時查詢。正常一天共 6 次歷史查詢；短時間反覆測試也會消耗額度。
- 已實際驗證不需金鑰的 XAU 與 BTC 即時端點回傳 JSON、USD、價格和時間戳。**尚未取得你的免費 Key，因此 30 天歷史查詢目前是依官方文件實作，尚未完成帳號實測。** 下方 Preview 是部署前的必要驗證。
- 歷史曲線使用 UTC「每日平均價」，不是收盤價；當日資料可能未完整。休市缺值留白，不補造價格。比較圖只使用兩者共同日期，首個共同日設為 100。
- 取得少於 15 個觀測日、歷史跨度不足 25 天或尾端超過 4 天未更新會停止，不發送不足以代表 30 天的圖表。最新報價超過 2 小時會標示延遲／可能休市。

## 1. 建立 Discord Webhook

1. 在你的 Discord 伺服器準備一個文字頻道，例如 `市場趨勢`。
2. 開啟「伺服器設定 → 整合（Integrations）→ Webhooks → 建立 Webhook」。需要管理 Webhook 的權限。
3. 名稱可設為「Gold & Bitcoin」，選擇接收報告的頻道並儲存。
4. 按「複製 Webhook URL」，稍後貼入 GitHub Secret。

URL 通常長這樣：`https://discord.com/api/webhooks/數字/一長串Token`。
**不要加 `/github`，不要貼進程式、README 或聊天室。** 本專案由 Python 呼叫 Discord API，並非 GitHub commit 通知整合。

[Discord 官方建立教學](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)

## 2. 取得免費資料 API Key

1. 開啟 [gold-api.com 免費方案](https://gold-api.com/pricing)。
2. 點選 Free / Get Started Free，建立帳號，從帳號頁取得 API Key。
3. 保持 **Free**，本專案不需要 Premium，也不會自動升級。
4. Key 稍後存入 `GOLD_API_KEY`，不要寫在檔案中。

若帳號頁顯示的免費條件已改變，先停止部署並重新確認，勿為了讓程式跑通而付費。

## 3. 建立 GitHub 儲存庫並上傳

1. GitHub → New repository，名稱例如 `gold-btc-discord`。
2. 選 **Public**，可勾選 Add a README file，建立儲存庫。
3. 解壓縮交付的 ZIP。把 `report.py`、`requirements.txt`、`README.md`、`tests` 資料夾上傳到儲存庫根目錄（Add file → Upload files），提交變更。
4. **工作流程不要漏掉：** GitHub → Add file → Create new file，檔名輸入 `.github/workflows/report.yml`，把壓縮包中同名檔案的全文貼上，提交至預設分支。
5. `.gitignore` 也可用 Create new file 新增。Windows 可能不容易注意到點開頭資料夾，所以第 4 步特別獨立處理。

最終結構應該是：

```text
儲存庫根目錄/
├── .github/workflows/report.yml
├── .gitignore
├── report.py
├── requirements.txt
├── README.md
└── tests/
    ├── test_report.py
    └── test_delivery.py
```

不要多包一層 `gold-btc-discord/`，否則 workflow 找不到程式。

公開儲存庫使用標準 GitHub-hosted runner 的 Actions 執行時間免費。資料檔、程式、Actions 日誌與產物可能公開；API Key 和 Webhook 放在 Secrets。[官方計費說明](https://docs.github.com/en/actions/concepts/billing-and-usage)

## 4. 設定兩個 Secrets 與寫入權限

儲存庫 → Settings → Secrets and variables → Actions → New repository secret：

| Name（必須完全相同） | Secret |
|---|---|
| `GOLD_API_KEY` | gold-api.com 的免費 API Key |
| `DISCORD_WEBHOOK_URL` | Discord 複製的完整 Webhook URL |

再到 Settings → Actions → General → Workflow permissions，允許 **Read and write permissions** 並儲存。工作流程只要求 `contents: write`，用來保存 `data/latest.json` 與發送收據 `data/sent.json`。

如有組織政策、分支保護或 Rulesets 禁止 Actions 寫入，請先處理該儲存庫允許的權限；建議用專用的新儲存庫。不要把 Secret 放在 Settings → Webhooks，那是另一種功能。

## 5. 先預覽，確認歷史來源真的可用

1. 點 Actions → **黃金與比特幣每日報告**。首次可能需要啟用 Actions。
2. 按 **Run workflow**，選預設分支，保留 `僅預覽，不發送至 Discord` 勾選。
3. 等執行完成，應為綠色成功。
4. 開啟該次執行，在 Artifacts 下載 `gold-btc-...`。
5. 檢查 `trend.png`（三個面板）、`message.txt`（中文摘要）、`report.json`（原始報告資料）。

這一步會呼叫真實 API，但不會向 Discord 發訊息，也不會修改 data 收據。確認圖表有近 30 天資料、日期正確且價格合理後，再做下一步。

## 6. 手動測試發送與啟用每日排程

再次 Run workflow，**取消勾選 僅預覽，不發送至 Discord**。

成功後，Discord 應收到一張圖和一段價格摘要，GitHub 根目錄會出現 `data/`。預設分支有 workflow 後，排程自動生效，電腦與 Colab 都不必開著。

```yaml
schedule:
  - cron: '0 0,4,16 * * *'
```

| UTC 執行時間 | 台灣時間 |
|---|---|
| 00:00 | 當天 08:00 |
| 04:00 | 當天 12:00（中午） |
| 16:00 | 隔天 00:00（午夜） |

GitHub Actions 不保證準點，整點可能延遲，負載過高甚至可能跳過某次排程；本版本不補發錯過的時段。若你之後需要嚴格準時，需改用有排程保障的執行環境。

公開儲存庫連續 60 天沒有活動可能停用排程。本專案正常送出後會提交收據／最新資料，保持可追蹤紀錄；若長期失敗，仍需到 Actions 檢查並重新啟用。請保留 GitHub Actions 失敗通知。

[GitHub 官方排程限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

## 發送紀錄與限制

- 同時只允許一個 workflow 執行，避免排程和手動測試互撞。
- 已提交收據的同一 GitHub run，按 Re-run 不會再次發送。新的 Run workflow 視為新的手動發送。
- Discord timeout 或 5xx 不會盲目重發，因為訊息可能已送達。先查看 Discord 頻道，再決定是否重跑。
- 如果 Discord 已送達，但 GitHub 儲存收據失敗，重跑仍可能重複。這不是「保證只送一次」的系統；請先確認頻道。
- `data/latest.json` 每次覆寫，但 Git 提交歷史保存之前版本；PNG／文字快照用 Actions artifacts 保存 7 天。
- 資料抓取失敗時工作流程會變紅，不發送錯誤行情。失敗通知以 GitHub Actions 為主，未額外向 Discord 發錯誤警報。

## 常見問題

| 狀況 | 處理 |
|---|---|
| API 401 / 403 | 確認 Key 來自 gold-api.com、未貼入多餘空白，且 Free 帳號有歷史權限。 |
| API 429 | 歷史查詢每小時最多 10 次；等額度恢復，不要連續按重跑。 |
| 歷史資料不足 | 該帳號／來源沒有足夠日資料，勿改用期貨或假資料硬補；保留錯誤訊息以便診斷。 |
| Discord 401 / 404 | Webhook 可能刪除或失效，重建並更新 Secret。 |
| Discord 403 | 檢查 Webhook、頻道與伺服器權限。 |
| 保存發送收據與最新資料 失敗 | 檢查寫入權限／分支保護；Discord 可能已收到，先看頻道。 |
| 沒有 Run workflow | workflow 必須放在預設分支的 `.github/workflows/report.yml`。 |
| 手動執行成功但 Discord 沒訊息 | 預設是 僅預覽，不發送至 Discord，取消勾選再執行。 |
| 08:00 沒立刻收到 | 先看 Actions 是否排隊／失敗，排程不保證準時。 |

## 本機與 Colab（選用）

Python 3.12：

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python report.py --dry-run
```

執行前由作業系統環境變數設定 `GOLD_API_KEY`。要真實發送再設定 `DISCORD_WEBHOOK_URL` 並移除 `--dry-run`。不要將金鑰寫入 notebook 儲存格。

Colab 可使用左側鑰匙圖示 Secrets 儲存同名金鑰，允許 notebook 存取後：

```python
import os
from google.colab import userdata
os.environ['GOLD_API_KEY'] = userdata.get('GOLD_API_KEY')
os.environ['DISCORD_WEBHOOK_URL'] = userdata.get('DISCORD_WEBHOOK_URL')
```

Colab／Ubuntu 需先執行 `!apt-get -qq update && apt-get -qq install -y fonts-noto-cjk` 安裝中文字型，再執行程式。正式 GitHub workflow 已自動處理字型。

在已上傳 report.py 和 requirements.txt 的目錄執行上述安裝與命令即可。Colab 只用於手動測試，正式排程仍由 GitHub Actions 執行。
