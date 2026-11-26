# CLAUDE.md — mentors-panel（AI 思維顧問團，原名 AI人物顧問團）

**2026-11-25 智財權調整（使用者同意）**：原本 12 位真實人物（第一人稱扮演）全部移除，改成 12 個自行撰寫的**虛構思考角色**，與 `行銷內容工具/content-workflow-studio-cf/node-packs/pack-a.js` 的 `MENTORS_PERSONAS` 同一套（id、名稱、systemPrompt 相同，改一邊要同步另一邊）。**不可加入真實人物的姓名、語錄、生平，也不可要求 AI 以真實人物身分發言**（姓名權／人格權／代言誤認風險）。`scripts/build_personas.py`、`data/personas-source.json` 已刪除；舊角色的 localStorage 勾選會因 id 不存在自動略過。`mentors-panel-api` 仍是自己的舊版 `data/personas.json`（真實人物，未同步），重跑它的 `sync_personas.py` 就會換成新角色——但 `line-cs-bot` 依顧問姓名辨識訊息，換之前要一起檢查。

單檔前端網站：使用者可勾選 12 個虛構思考角色，針對人生規劃/工作任務/工作計畫等問題提問，被選中的角色各自以其思維框架獨立回覆、並列呈現。無建置步驟、無框架，直接開啟 `index.html`（`file://`）或以靜態伺服器託管即可，響應式支援桌機/平板/手機。

## 架構

- `index.html`：單檔，內嵌CSS/JS，無外部資源（`personas-data.js`除外）。
- `personas-data.js`：`window.PERSONAS = [...]`，手寫維護（合法 JSON 外包 `window.PERSONAS = …;`，`mentors-panel-api` 的同步腳本靠這個格式）。欄位：id／name／tagline／avatarText／color／disclaimerShort／disclaimerFull／systemPrompt。
- `manual.html`：操作手冊。

## API 金鑰處理（重要）

**使用者自備金鑰（BYOK）**，純靜態網站，不經任何開發者控制的後端：
- 金鑰只存於使用者瀏覽器 `localStorage`（key `mentorsApiConfig`），前端直接 `fetch()` 打 Claude/OpenAI/Gemini/OpenRouter 官方API，不會、也不可能在開發者這邊洩漏。
- CORS處理與 `政府補助認證產生器/sbir-generator`、`行銷內容工具/Prompt`、`行銷內容工具/SocialPost` 同一套：Claude需`anthropic-dangerous-direct-browser-access: true` header；Gemini金鑰放`x-goog-api-key` header（不放URL query）；OpenAI/OpenRouter用`Authorization: Bearer`。429/500/503/529自動重試2次（間隔8s/16s），180秒逾時。
- **與上述3個專案的差異**：本專案的 `callLLM(provider, model, apiKey, systemPrompt, messages, onRetry)` 支援多輪`messages`陣列（每位角色各自記得自己的問答歷史，但看不到其他角色的回覆），而非其他專案用的單輪`prompt`字串。這是本專案內獨立複製的版本，不是共用檔案；三個來源專案的`callLLM`若有安全性修正（例如CORS header變動），需要手動同步過來。

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

## 標準五件套（2026-11-26 補齊）

- **訪客數**：改用工作區標準的 visitor-badge（`https://visitor-badge.laobi.icu/badge?page_id=m255525.mentorspanel`，`<img>` 放頁尾 `#visitCounter` 與 ⚙「關於本工具」），`tool-usage-analytics` 才掃得到；原本的 countapi.mileshilliard（及更早的 CounterAPI）腳本與 `mentorsVisitCount` 快取已移除。測試時要 route 擋掉 visitor-badge 請求，避免灌數字。
- **使用警語**：`#warnOverlay`（`z-index:110`，要高於設定面板的 100，否則從 ⚙ 開會被蓋住）；首次造訪自動跳出一次（`mentorsWarnSeen`），頁面上看得到的入口：顧問區下方 `.warn-line`、頁尾、⚙「關於本工具」。所有 `data-act="warn|install|download|clear"` 走 document 事件委派。
- **⚙ 常用設定**：頂列按鈕原「⚙ API 設定」改名，仍是 `#apiOverlay`／`openAiPanel()`；內容分三個 `<details class="set-sec">`：🤖 AI 服務與金鑰（`#ssvAi` 顯示服務商與是否填金鑰）、💬 對話與本機資料（下載／清除）、ℹ 關於本工具（創作者、手冊、警語、加入主畫面、訪客數）；展開狀態記在 `mentorsSettingsFold`（預設只展開 ai），「全部展開／收合」鈕；沒金鑰送出時用 `openAiPanel({section:"ai"})` 只展開 AI 區。跑馬燈必備，不放開關。
- **創作者**：頁尾「👤 創作者 Mark Tsai（蔡豐全）」連 `manual.html#creator`（完整版證照／經歷）；手冊另有 `#warning` 使用警語、⚙ 常用設定說明。

## 共用頂部跑馬燈

比照工作區已推廣到多個專案的共用跑馬燈機制（`shared-widget-rollout` skill的既有做法，Google Sheet + Apps Script當後端，端點`https://script.google.com/macros/s/AKfycbwKX0DNNbY8y4nf90BFTHtxgfqJcHHcZasRrgycl4QAe52_hkjMWSkYk4xOsqU-JPCROw/exec`，全工作區共用同一個端點與Sheet，內容由該Sheet集中管理、跟mentors-panel本身無關）：
- **direct-call模式**（本站沒有序號登入機制，POST空`serial`只取`marquee`陣列，忽略`valid`/`reason`）。
- 版面採用`政府補助認證產生器`外的`行銷內容工具/Prompt`那套「fixed-overlay」整合模式（而非`flex-item`模式），因為本站`.topbar`是`position:sticky`而非包在`100vh`flex殼裡：`#marqueeBar`用`position:fixed;z-index:50`（高於`.topbar`的`z-index:40`），`body.has-marquee`把`body`推下30px、把`.topbar`的`top`也推到30px，避免跑馬燈蓋住或被蓋住。
- `localStorage` key用本專案專屬的`mentorsMarquee`（各專案各自獨立key）。
- 若這個共用端點未來換掉或Sheet內容調整，**跟mentors-panel程式碼無關**，不需要改本專案的程式；只有端點URL本身失效才需要更新。
- **2026-08-20更新（`Code.gs`未改動、不需重新部署）**：`render()`新增`lastKey`（`JSON.stringify(items)`）比對，內容沒變就不重繪，CSS animation不再被重置歸零重跑；新增`appendParsedText()`／`buildTrackContent()`支援`[文字](https://...)`連結語法（`createTextNode`組DOM，避免XSS），資料格式仍是純字串陣列，向下相容。已commit＋push（GitHub Pages自動重新部署）。

## 頁尾與操作手冊的創作者資訊

`index.html`頁尾與`manual.html`都有「製作：Mark Tsai」的署名與信箱連結。`manual.html`的完整「創作者資料」卡片（證照/經歷）內容與`政府補助認證產生器/sbir-generator`、`phoenix-loan-generator`、`icap-generator`三份`manual.html`的同一區塊**逐字相同**，屬於那組「更新一邊要同步其餘各邊」的同步集合（見那三個專案的CLAUDE.md）；mentors-panel是這組同步集合裡目前唯一的**公開GitHub Pages網站**，因此「授權與使用限制」文字刻意改寫過，不是照抄那三個私有教學工具的「禁止公開發布」措辭（因為本站本身就是公開發布的）。

## 加入主畫面（PWA，2026-08-14 新增）

比照工作區 `expense-tracker-pwa` 的做法：`manifest.json`＋`icons/`（米色 `#f4f1ec` 背景、棕金 `#b8763f`「思」字圖示）＋`service-worker.js`（network-first＋同源快取備援，不需要每次改動升版 `CACHE_NAME`）。**安裝腳本刻意放在檔案最尾端**（`</body>` 前），不是跟頂部跑馬燈那個 IIFE放一起——頂部跑馬燈的 `<script>` 在 `<body>` 一開頭就執行，那時候 `.topbar-inner` 裡的 `#installBtn` 還沒被瀏覽器解析出來，`getElementById` 會抓 `null`。安裝按鈕放在 `.topbar-inner`（跟「操作手冊」「⚙ 常用設定」同排、同 `.btn` 樣式）。已用 Playwright 實測 Chromium 觸發 `beforeinstallprompt`、SW 註冊成功。


**iOS／iPadOS／macOS 相容性補強（2026-08-14 同日追加）**：Safari（含 iOS 上的 Chrome/Firefox，底層都是 WebKit）**永遠不會觸發 `beforeinstallprompt`**，原本的按鈕邏輯在這些瀏覽器上一律落入「瀏覽器不支援」這句話，其實是誤導——蘋果裝置本來就能加入主畫面，只是要透過分享選單手動操作，不像 Chrome/Edge 有自動彈窗。修法：安裝腳本新增 `isIOSDevice`（`/iPad|iPhone|iPod/` 或 `navigator.platform==='MacIntel' && maxTouchPoints>1`——後者是因為 iPadOS 13+ 預設偽裝成 Mac 桌面版 UA，要用觸控點數才分得出來是 iPad 還是真的 Mac）與 `isMacDesktop && isSafariEngine`（macOS 桌面版 Safari 17+ 是「檔案→加入 Dock」，跟手機的分享選單操作不同）兩種判斷，各自顯示對應的操作指引文字，不再顯示「不支援」；`isStandalone`（`matchMedia('(display-mode: standalone)')` 或 iOS 專有的 `navigator.standalone`）為真時直接隱藏按鈕（已經是安裝後開啟，不需要再顯示安裝按鈕）。`<head>` 同步補上 `apple-touch-icon`（180×180 專用尺寸，`icons/apple-touch-icon.png`，純色不透明背景）＋ `apple-mobile-web-app-capable`／`mobile-web-app-capable`（兩個都要，前者給 Safari、後者是 Chrome 主張的新標準，只寫一個 Chrome 會在主控台噴 deprecation warning）＋ `apple-mobile-web-app-status-bar-style`／`apple-mobile-web-app-title`。這五個判斷/訊息字串在全部 9 個已加裝 PWA 的專案裡是逐字複製的同一段邏輯，日後若要調整任一處的措辭或判斷式，建議九個一起改，避免各專案的安裝體驗不一致。

**回饋機制與快取踩坑修正（2026-08-14，使用者實測回報「加入主畫面沒有功能」才發現兩層問題）**：(1) 原本無 `showToast` 時用「暫時置換按鈕文字」當提示，在工具列裡太不明顯，使用者完全沒注意到訊息出現過——改成 `window.alert(fallbackMessage())`，`deferredPrompt.prompt()` 也包 try/catch。(2) 改完使用者仍回報沒反應，追查發現 `service-worker.js` 的 `fetch(event.request)` 沒有繞過瀏覽器 HTTP 快取——GitHub Pages 對回應下 `Cache-Control: max-age=600`，10 分鐘內「network-first」名不符實，可能吃到舊版內容重新存進 Cache Storage。改成 `fetch(event.request, {cache:'reload'})` 強制略過 HTTP 快取，`CACHE_NAME` 同步升版 v1→v2 清掉已污染的快取。這是跟 `expense-tracker-pwa` 那次「install 階段 `cache.addAll()` 忘記加 `{cache:'reload'}`」同一個 bug class 的 runtime 版本，細節見 [[pwa-install-rollout]]。

## 虛擬董事會辯論模式（2026-09-21 新增）

既有設計刻意讓各角色互相隔離（`buildMessages()`只組裝該人物自己的問答歷史，看不到其他角色的回覆），避免思維框架互相污染。這個新功能是使用者主動觸發的**例外情境**：任何一個回合只要有 2 位以上顧問成功回答完成，該回合下方就會出現「🗣️ 讓顧問們互相回應」按鈕，按下去會另開一個新回合（`round.isDebate=true`），讓每位顧問各自看到「除了自己以外」其他顧問剛才針對同一問題的回答，並要求他們維持自己的思維框架對這些觀點做出回應（認同或反駁皆可）。

- **`buildDebateMessages(personaId, debateRound)`**：辯論回合專用的訊息組裝函式，取代一般的`buildMessages()`。透過`debateRound.baseRoundId`找到要引用的基準回合，組出「其他顧問回答＋辯論指示」的user訊息，前面仍接著`buildMessages(personaId, baseRound)`重建該角色自己的歷史脈絡＋`{assistant: 他自己在基準回合的回答}`，讓多輪對話結構維持完整。
- **`startDebateRound(baseRoundId)`**：建立新的辯論回合，只挑基準回合裡「已成功回答（status===done）」的顧問加入——沒答完的人自然沒有觀點可辯論、也沒立場回應別人。
- **可以連續辯論多輪（鏈式）**：辯論回合本身也符合「2位以上已完成回答」的條件，一樣會冒出「🗣️ 讓顧問們互相回應」按鈕，`baseRoundId`永遠指向使用者按下按鈕當下所在的那個回合（不論是一般回合或辯論回合），所以可以一直往下鏈接出多輪辯論。
- **`retryReply()`／`continueReply()`都改成先判斷`round.isDebate`**，是的話呼叫`buildDebateMessages()`而非`buildMessages()`，否則重試/接續辯論回合的失敗回覆時，會漏掉原本要引用的其他人觀點，變成一句沒頭沒尾的空泛回應。
- **`round.question`對辯論回合固定存`DEBATE_PROMPT_LABEL`常數**（`"🗣️ 顧問們互相回應"`），實際引用其他人回答的完整文字只在呼叫API當下動態組裝、不存進`round.question`——代價是若辯論回合本身又被當作更下一輪辯論的基準（鏈式辯論的第3輪以後），`buildMessages()`重建歷史時只會看到這個generic標籤而非完整引用內容，是刻意接受的簡化（維持「一個回合共用同一個question」的既有資料模型，不為了辯論模式改動整體架構）。
- **按鈕即時性**：因為個別卡片是用`updateReplyCard()`局部`outerHTML`替換更新（不會整段重跑`renderRounds()`），新增了`updateRoundActions(roundId)`在每次卡片更新後即時重新判斷「是否該顯示/隱藏辯論按鈕」，不必等到使用者送出下一題才會姍姍來遲地冒出來——這是實作過程中發現的真實邏輯漏洞，已修正並用Playwright驗證（stub `callLLM` 模擬回覆逐一完成，確認按鈕在達到2個done時即時出現）。
- **視覺區分**：辯論回合的`.round-question`改用`--accent`底色（跟一般回合的深灰底區隔），下方多一行斜體小字顯示「針對：〈基準回合的問題〉」。
- **匯出txt**：`buildTranscriptText()`辯論回合的提問行改顯示「【🗣️ 顧問們互相回應】針對：〈原問題〉」而非「【提問】」。
- 已用Playwright + stub `window.callLLM`（不需真實金鑰）驗證：一般回合三人皆完成後按鈕正確出現、辯論回合正確排除自己只引用其他人的回答文字、鏈式辯論（辯論回合再次辯論）正確運作、辯論回合的retry正確帶上完整引用內容、手機版(375px)無橫向溢出。
- **`mentors-panel-offline/`離線變體未同步套用此功能**（該子資料夾走服務代理/Ollama架構，跟本專案直連BYOK的`callLLM`實作不共用程式碼），如需要離線版也支援辯論模式，需另外移植。

## 已知限制

選滿10位人物對同一供應商同時發出10個請求，可能撞到該供應商的並發限流；`callLLM`內建的429重試多半能吸收，目前未做請求間隔stagger，若使用者反映經常性失敗可考慮加入150~300ms的請求間隔。

## 指令

無建置/測試指令。修改`index.html`後直接用瀏覽器開啟驗證，或 `python -m http.server 8785 --directory "AI人物顧問/mentors-panel"` 暫起伺服器（已註冊於根目錄`.claude/launch.json`，名稱`mentors-panel`）。

驗證`personas-data.js`格式：
```bash
node -e "global.window={};require('./personas-data.js');const P=window.PERSONAS;console.log(P.length,'personas');const ids=P.map(p=>p.id);console.log('dup ids:',ids.length-new Set(ids).size);"
```
