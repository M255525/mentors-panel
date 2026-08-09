# CLAUDE.md — mentors-panel

單檔前端網站：使用者可勾選 `nuwa-skill` 蒸餾出的11位人物視角思維顧問（黃仁勳、郭台銘、周杰倫、賈伯斯、科特勒、香奈兒、卡帕西、孫正義、史蒂芬·史匹柏、戴爾·卡內基、華倫·巴菲特），針對人生規劃/工作任務/工作計畫等問題提問，被選中的角色各自以其思維框架獨立回覆、並列呈現。無建置步驟、無框架，直接開啟 `index.html`（`file://`）或以靜態伺服器託管即可，響應式支援桌機/平板/手機。

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

**執行時機**：只在既有人物的SKILL.md被`nuwa-skill`重新蒸餾更新後才需要重跑 `python scripts/build_personas.py`；重跑後請 diff `data/personas-source.json` 與 `personas-data.js`，確認沒有覆蓋掉已經人工微調過的內容（例如`PERSONA_META`裡手調的措辭）才commit。若未來要新增第12位人物，記得同步在`PERSONA_IDS`與`PERSONA_META`各加一筆（2026-08-09新增第11位華倫·巴菲特的做法可參考：先用`nuwa-skill`蒸餾出`~/.claude/skills/<person-id>-perspective/`，再補`PERSONA_IDS`與`PERSONA_META`兩筆，跑腳本即完成，網站前端因完全data-driven不需改`index.html`；記得同步更新`README.md`與`manual.html`裡手打的人數/人物表格，這兩處不是data-driven）。**卡內基那次的重要改進沒有自動延續**：2026-08-08新增卡內基時曾把「若當前環境無工具存取權限」的處理直接寫進Phase 3初版；但2026-08-09蒸餾巴菲特時這個做法沒被自動記住，Phase 3初版又漏寫了同一件事，直到Phase 5雙agent精煉才補回來——顯示這個做法目前只存在個別SKILL.md裡、沒有寫回`nuwa-skill`本身的模板，日後每次新蒸餾人物都可能重蹈覆轍，若要根治應該考慮把這條規則加進`nuwa-skill`的`references/skill-template.md`或Phase 3指引本身。

**`SECTION_PREFIX_MAP`踩坑**：2026-08-08升級7位人物SKILL.md新增「回答工作流（Agentic Protocol）」章節時，一度忘記同步這張對照表，導致該章節被`extract_sections()`當成「未歸類章節」靜默捨棄、完全沒進到`systemPrompt`——8位人物裡有7位的「先查證再回答」指示因此在網站上實際失效過一段時間（腳本仍執行成功、無報錯，只在stdout印警告，非常容易被忽略）。日後SKILL.md模板若新增章節（不只是這次的Agentic Protocol），務必同步檢查`SECTION_PREFIX_MAP`與`build_system_prompt()`，並留意執行`build_personas.py`時的`[警告] 未歸類的章節標題`輸出。

**特殊處理**（不要在重構時弄丟）：
- 賈伯斯、香奈兒的`PERSONA_META.deceased`會在systemPrompt結尾額外附加「已故人物僅能反映生前言論」提醒，即使SKILL.md本文已經寫過類似的話也會重複附加一次——這是刻意的雙重保險，不是bug。
- 香奈兒的`quoteTiering=True`會額外附加一句要求LLM延續「已查證原話 vs 廣泛流傳但存疑」雙軌標註的指示（她的SKILL.md本身就有這個機制，語錄真偽考據過，很多網傳「香奈兒名言」其實查無實證）。
- 郭台銘的`specialCaution`會顯示在人物卡的ⓘ說明與首次選取的modal裡，警語原文取自其SKILL.md的誠實邊界章節。
- 史蒂芬·史匹柏同時有`quoteTiering=True`（其SKILL.md表達DNA調研有做語錄真偽查證，網傳「史匹柏名言」多查無實據）與`specialCaution`（提醒其AI/串流產業立場仍在快速演變、且調研全程僅用英語來源）。
- 戴爾·卡內基（1888-1955）同時有`deceased`、`quoteTiering=True`與`specialCaution`三者並用：他過世早於播客/訪談時代，「對話」調研維度資訊確實稀薄（SKILL.md誠實標註）；`specialCaution`警語提醒他的核心原則（「讓對方覺得是他自己的主意」）曾被查爾斯·曼森用於操縱信眾犯下謀殺案，回覆時會誠實揭露此侷限而非美化成萬用技巧；改姓年份、初婚年份等多個生平細節在史料間本身有出入，未強行統一。

## 前端行為重點

- 資料載入用 `<script src="personas-data.js?v=YYYYMMDD">`（比照 `課程平台/ai-course-hub` 的`courses-data.js`模式，避免`file://`下`fetch()`的CORS限制）。修改`personas-data.js`後記得提高`?v=`版本，否則瀏覽器可能吃快取顯示舊資料。
- 每輪對話`buildMessages(personaId, round)`只組裝**該人物自己**過去成功回答過的問答歷史，不含其他人物的回覆——避免互相污染思維框架、也控制prompt長度。
- 並行呼叫`selectedIds`時，每個`callLLM()`各自獨立`.then()`更新對應卡片DOM（`updateReplyCard()`用`data-round`+`data-persona`屬性定位），不等全部完成才一起渲染；`error`狀態的「重試」只重打該張卡片，不影響其他已完成的。
- 免責聲明三層呈現：人物卡上永遠顯示的`disclaimerShort`小字＋首次選取跳出的一次性完整modal（`localStorage` key `mentorsSeenDisclaimers`記錄已看過的角色）＋每則回覆卡片下方也重複`disclaimerShort`。ⓘ圖示可隨時重開完整說明（`mode:"info"`），此模式下不會觸發選取。

## 回覆截斷接續（重要）

`callLLM`的`extract()`會回傳`{text, truncated}`而非純字串——`truncated`依供應商判斷是否因`max_tokens`被腰斬：Claude看`stop_reason==="max_tokens"`、OpenAI/OpenRouter看`choices[0].finish_reason==="length"`、Gemini看`candidates[0].finishReason==="MAX_TOKENS"`。`round.replies[pid]`多存`truncated`與`continueCount`兩個欄位；`truncated===true`時卡片顯示「接續完整回覆」按鈕，觸發`continueReply()`——重用`buildMessages()`組出的歷史，額外附加`{role:"assistant", content: 已生成的部分文字}` + `{role:"user", content: 接續指示}`，把新呼叫回傳的文字直接串接在舊文字後面（不加分隔符，因為要求模型從斷句處自然接續）。`MAX_CONTINUE_ROUNDS`（目前5）只是防呆上限，不是強制值——使用者可以持續點按鈕接續到滿足為止。`MAX_REPLY_TOKENS`（目前2048）調高可降低觸發頻率，但無法完全避免，接續機制才是根本解法。

## 對話操作功能

- **清除對話**（`clearRounds()`）：`confirm()`二次確認後清空`state.rounds`並隱藏`#roundsSection`；只清對話內容，不影響已選人物與API設定。
- **下載txt**（`downloadTranscript()`）：把`state.rounds`組成純文字逐輪記錄（比照`小工具/SN-maker`、`行銷內容工具/Prompt`的Blob+`<a download>`寫法），檔名帶時間戳記。
- 兩個按鈕都在`#roundsSection`的`.rounds-header`裡，只有送出過至少一輪對話後才會出現（`roundsSection`預設`display:none`）。

## 瀏覽次數計數器

`#visitCounter`（頁尾）用免費第三方服務 [CounterAPI](https://counterapi.dev)（`api.counterapi.dev/v1/mentors-panel/pageviews/up`）記錄**累計頁面載入次數**，不是去重後的訪客數。純展示用途、無認證、匿名可寫，理論上任何人都能對這個公開的counter端點灌水，可接受風險（純虛榮數字，非安全或計費用途）。選這個而非工作區慣用的Google Apps Script後端，是因為需求極簡（只要一個會累加的數字），另起一個Sheet+Script部署的維運成本不划算；若之後這個免費服務停用或不穩定，換成別的counter API或自建都只需要改`COUNTER_URL`這一行。有`localStorage`（key `mentorsVisitCount`）快取上次讀到的數字，網路請求失敗時靜默顯示快取值或留空，不會拋錯影響頁面其他功能。

## 共用頂部跑馬燈

比照工作區已推廣到多個專案的共用跑馬燈機制（`shared-widget-rollout` skill的既有做法，Google Sheet + Apps Script當後端，端點`https://script.google.com/macros/s/AKfycbwKX0DNNbY8y4nf90BFTHtxgfqJcHHcZasRrgycl4QAe52_hkjMWSkYk4xOsqU-JPCROw/exec`，全工作區共用同一個端點與Sheet，內容由該Sheet集中管理、跟mentors-panel本身無關）：
- **direct-call模式**（本站沒有序號登入機制，POST空`serial`只取`marquee`陣列，忽略`valid`/`reason`）。
- 版面採用`政府補助認證產生器`外的`行銷內容工具/Prompt`那套「fixed-overlay」整合模式（而非`flex-item`模式），因為本站`.topbar`是`position:sticky`而非包在`100vh`flex殼裡：`#marqueeBar`用`position:fixed;z-index:50`（高於`.topbar`的`z-index:40`），`body.has-marquee`把`body`推下30px、把`.topbar`的`top`也推到30px，避免跑馬燈蓋住或被蓋住。
- `localStorage` key用本專案專屬的`mentorsMarquee`（各專案各自獨立key）。
- 若這個共用端點未來換掉或Sheet內容調整，**跟mentors-panel程式碼無關**，不需要改本專案的程式；只有端點URL本身失效才需要更新。

## 頁尾與操作手冊的創作者資訊

`index.html`頁尾與`manual.html`都有「製作：Mark Tsai」的署名與信箱連結。`manual.html`的完整「創作者資料」卡片（證照/經歷）內容與`政府補助認證產生器/sbir-generator`、`phoenix-loan-generator`、`icap-generator`三份`manual.html`的同一區塊**逐字相同**，屬於那組「更新一邊要同步其餘各邊」的同步集合（見那三個專案的CLAUDE.md）；mentors-panel是這組同步集合裡目前唯一的**公開GitHub Pages網站**，因此「授權與使用限制」文字刻意改寫過，不是照抄那三個私有教學工具的「禁止公開發布」措辭（因為本站本身就是公開發布的）。

## 已知限制

選滿10位人物對同一供應商同時發出10個請求，可能撞到該供應商的並發限流；`callLLM`內建的429重試多半能吸收，目前未做請求間隔stagger，若使用者反映經常性失敗可考慮加入150~300ms的請求間隔。

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
