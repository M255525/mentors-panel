# CLAUDE.md — mentors-panel

單檔前端網站：使用者可勾選 `nuwa-skill` 蒸餾出的7位人物視角思維顧問（黃仁勳、郭台銘、周杰倫、賈伯斯、科特勒、香奈兒、卡帕西），針對人生規劃/工作任務/工作計畫等問題提問，被選中的角色各自以其思維框架獨立回覆、並列呈現。無建置步驟、無框架，直接開啟 `index.html`（`file://`）或以靜態伺服器託管即可，響應式支援桌機/平板/手機。

## 架構

- `index.html`：單檔，內嵌CSS/JS，無外部資源（`personas-data.js`除外）。
- `personas-data.js`：`window.PERSONAS = [...]`，由 `scripts/build_personas.py` 產生，**不要手改**。
- `data/personas-source.json`：機械萃取結果，**是這個repo內部的唯一真實來源**（因為 `~/.claude/skills/*-perspective/SKILL.md` 在使用者家目錄、不在這個repo裡，換到別台機器就讀不到）。
- `manual.html`：操作手冊。

## API 金鑰處理（重要）

**使用者自備金鑰（BYOK）**，純靜態網站，不經任何開發者控制的後端：
- 金鑰只存於使用者瀏覽器 `localStorage`（key `mentorsApiConfig`），前端直接 `fetch()` 打 Claude/OpenAI/Gemini/OpenRouter 官方API，不會、也不可能在開發者這邊洩漏。
- CORS處理與 `政府補助認證產生器/sbir-generator`、`行銷內容工具/Prompt`、`行銷內容工具/SocialPost` 同一套：Claude需`anthropic-dangerous-direct-browser-access: true` header；Gemini金鑰放`x-goog-api-key` header（不放URL query）；OpenAI/OpenRouter用`Authorization: Bearer`。429/500/503/529自動重試2次（間隔8s/16s），180秒逾時。
- **與上述3個專案的差異**：本專案的 `callLLM(provider, model, apiKey, systemPrompt, messages, onRetry)` 支援多輪`messages`陣列（每位角色各自記得自己的問答歷史，但看不到其他角色的回覆），而非其他專案用的單輪`prompt`字串。這是本專案內獨立複製的版本，不是共用檔案；三個來源專案的`callLLM`若有安全性修正（例如CORS header變動），需要手動同步過來。

## SKILL.md → personas-data.js 轉換管線

`scripts/build_personas.py` 分兩階段：

1. **`extract_sections()`**：讀取 `~/.claude/skills/<id>-perspective/SKILL.md`，去YAML frontmatter、用固定字串切除檔尾「本Skill由女媧・Skill造人術生成」版權區塊、按9個固定H2標題前綴（角色扮演規則/身份卡/核心心智模型/決策啟發式/表達DNA/人物時間線或關鍵節點/價值觀與反模式/智識譜系/誠實邊界）分類切段，捨棄「附錄：調研來源」整節。對誠實邊界等段落做**片語級**黑話替換（`快速檔`→`快速版`、`蒸餾`→`整理`等，見`JARGON_REPLACEMENTS`），轉換完做黑名單關鍵字掃描（`女媧`/`花叔`/`蒸餾`/`Quick Tier`等殘留就`raise`中止）。輸出 `data/personas-source.json`。
2. **`build_persona_object()`**：套用腳本內人工維護的`PERSONA_META`常數（tagline/頭像縮寫/代表色/已故人物注記/特殊警語/語錄雙軌標註旗標），組裝`systemPrompt`與`disclaimerShort`/`disclaimerFull`，輸出 `personas-data.js`。

**執行時機**：只在7位人物的SKILL.md被`nuwa-skill`重新蒸餾更新後才需要重跑 `python scripts/build_personas.py`；重跑後請 diff `data/personas-source.json` 與 `personas-data.js`，確認沒有覆蓋掉已經人工微調過的內容（例如`PERSONA_META`裡手調的措辭）才commit。若未來要新增第8位人物，記得同步在`PERSONA_IDS`與`PERSONA_META`各加一筆。

**特殊處理**（不要在重構時弄丟）：
- 賈伯斯、香奈兒的`PERSONA_META.deceased`會在systemPrompt結尾額外附加「已故人物僅能反映生前言論」提醒，即使SKILL.md本文已經寫過類似的話也會重複附加一次——這是刻意的雙重保險，不是bug。
- 香奈兒的`quoteTiering=True`會額外附加一句要求LLM延續「已查證原話 vs 廣泛流傳但存疑」雙軌標註的指示（她的SKILL.md本身就有這個機制，語錄真偽考據過，很多網傳「香奈兒名言」其實查無實證）。
- 郭台銘的`specialCaution`會顯示在人物卡的ⓘ說明與首次選取的modal裡，警語原文取自其SKILL.md的誠實邊界章節。

## 前端行為重點

- 資料載入用 `<script src="personas-data.js?v=YYYYMMDD">`（比照 `課程平台/ai-course-hub` 的`courses-data.js`模式，避免`file://`下`fetch()`的CORS限制）。修改`personas-data.js`後記得提高`?v=`版本，否則瀏覽器可能吃快取顯示舊資料。
- 每輪對話`buildMessages(personaId, round)`只組裝**該人物自己**過去成功回答過的問答歷史，不含其他人物的回覆——避免互相污染思維框架、也控制prompt長度。
- 並行呼叫`selectedIds`時，每個`callLLM()`各自獨立`.then()`更新對應卡片DOM（`updateReplyCard()`用`data-round`+`data-persona`屬性定位），不等全部完成才一起渲染；`error`狀態的「重試」只重打該張卡片，不影響其他已完成的。
- 免責聲明三層呈現：人物卡上永遠顯示的`disclaimerShort`小字＋首次選取跳出的一次性完整modal（`localStorage` key `mentorsSeenDisclaimers`記錄已看過的角色）＋每則回覆卡片下方也重複`disclaimerShort`。ⓘ圖示可隨時重開完整說明（`mode:"info"`），此模式下不會觸發選取。

## 已知限制

選滿7位人物對同一供應商同時發出7個請求，可能撞到該供應商的並發限流；`callLLM`內建的429重試多半能吸收，目前未做請求間隔stagger，若使用者反映經常性失敗可考慮加入150~300ms的請求間隔。

## 指令

無建置/測試指令。修改`index.html`後直接用瀏覽器開啟驗證，或 `python -m http.server 8785 --directory "AI人物顧問/mentors-panel"` 暫起伺服器（已註冊於根目錄`.claude/launch.json`，名稱`mentors-panel`）。

重新產生人物資料：
```bash
python scripts/build_personas.py
```

驗證`personas-data.js`格式：
```bash
node -e "global.window={};require('./personas-data.js');const P=window.PERSONAS;console.log(P.length,'personas');const ids=P.map(p=>p.id);console.log('dup ids:',ids.length-new Set(ids).size);"
```
