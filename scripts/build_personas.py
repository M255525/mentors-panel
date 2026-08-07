#!/usr/bin/env python3
"""
把 nuwa-skill 蒸餾出的 7 位人物 SKILL.md 轉換成網站用的 personas-data.js。

管線：
  ~/.claude/skills/<id>-perspective/SKILL.md
    -> extract_sections()      機械切段、去除版權區塊、黑話翻譯
    -> data/personas-source.json   （進 git 的唯一真實來源，因為 SKILL.md 在家目錄不會進這個 repo）
    -> build_persona_object()  套用 PERSONA_META 中繼資料、組裝 systemPrompt
    -> personas-data.js        （window.PERSONAS，不要手改，改 PERSONA_META 或重蒸餾後重跑本腳本）

用法：
    python scripts/build_personas.py
"""

import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SKILLS_ROOT = Path.home() / ".claude" / "skills"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = PROJECT_ROOT / "data" / "personas-source.json"
OUTPUT_JS = PROJECT_ROOT / "personas-data.js"

PERSONA_IDS = [
    "jensen-huang",
    "terry-gou",
    "jay-chou",
    "steve-jobs",
    "philip-kotler",
    "coco-chanel",
    "andrej-karpathy",
]

# 前綴比對表：header_line.startswith(prefix) -> section key
# 用前綴而非完全相等，因為部分標題後面帶括號附註（如「智識譜系（快速檔：證據薄弱...）」）
SECTION_PREFIX_MAP = [
    ("角色扮演規則", "role_rules"),
    ("身份卡", "identity_card"),
    ("核心心智模型", "mental_models"),
    ("決策啟發式", "heuristics"),
    ("表達DNA", "expression_dna"),
    ("人物時間線", "timeline"),
    ("關鍵節點", "timeline"),
    ("價值觀與反模式", "values_antipatterns"),
    ("智識譜系", "intellectual_lineage"),
    ("誠實邊界", "honesty_boundary"),
    ("附錄", None),  # 明確捨棄：調研來源清單對終端使用者無意義，且占15-20%篇幅
]

COPYRIGHT_MARKER = "\n---\n\n> 本Skill由"

# 片語級黑話替換（依序套用，較長/較特定的樣式排前面，避免被短樣式先吃掉破壞語意）
JARGON_REPLACEMENTS = [
    ("快速檔（Quick Tier）", "快速版"),
    ("快速檔(Quick Tier)", "快速版"),
    ("快速檔", "快速版"),
    ("Quick Tier", "快速版"),
    ("蒸餾", "整理"),
    ("女媧 · Skill造人術", ""),
    ("造人術", ""),
    ("女媧", ""),
    ("花叔", ""),
    # 附錄（調研來源）整節已被捨棄，內文中指向附錄的懸空引用要一併改寫，
    # 否則LLM會被要求「見附錄」卻拿不到對應內容
    ("已查證確切出處，見附錄", "已查證確切出處"),
    ("見附錄「已查證」vs「廣泛流傳但存疑」", "已在上方引用時以「已查證」／「廣泛流傳但存疑」標記區分"),
]

# 轉換完成後的安全網：這些字串理論上都應該已被上面的規則清除，
# 若仍殘留代表 SKILL.md 格式或措辭已變動，需要人工補替換規則，寧可讓腳本失敗也不要靜默漏掉。
BLACKLIST_TERMS = ["Quick Tier", "快速檔", "蒸餾", "女媧", "花叔", "造人術"]

# 顯示層中繼資料：不用正則猜，人工維護，確保 tagline/警語措辭品質與口氣一致
PERSONA_META = {
    "jensen-huang": {
        "name": "黃仁勳",
        "nameEn": "Jensen Huang",
        "tagline": "輝達創辦人暨執行長：忍痛換護城河的長期主義者",
        "avatarText": "黃",
        "color": "#76b900",
        "sourceCount": 15,
        "deceased": None,
        "specialCaution": None,
        "quoteTiering": False,
    },
    "terry-gou": {
        "name": "郭台銘",
        "nameEn": "Terry Gou",
        "tagline": "鴻海精密創辦人：強勢談判與組織紀律的實踐者",
        "avatarText": "郭",
        "color": "#33475b",
        "sourceCount": 15,
        "deceased": None,
        "specialCaution": "本角色設定為快速版整理，未涵蓋他人評價、決策內幕細節、完整生平時間線，不適合用於需要嚴謹史實查核，或涉及郭台銘本人真實隱私立場推測的場合。",
        "quoteTiering": False,
    },
    "jay-chou": {
        "name": "周杰倫",
        "nameEn": "Jay Chou",
        "tagline": "創作歌手、音樂人、導演：原創性與跨界混搭的判斷框架",
        "avatarText": "周",
        "color": "#4b3f72",
        "sourceCount": 15,
        "deceased": None,
        "specialCaution": None,
        "quoteTiering": False,
    },
    "steve-jobs": {
        "name": "賈伯斯",
        "nameEn": "Steve Jobs",
        "tagline": "蘋果共同創辦人：產品與設計決策的簡潔尖銳視角",
        "avatarText": "賈",
        "color": "#1d1d1f",
        "sourceCount": 13,
        "deceased": {
            "year": 2011,
            "note": "已於西元2011年過世，本角色設定僅能反映其生前公開言論與著作，無法回應2011年後的事件與科技發展（例如生成式AI）。",
        },
        "specialCaution": None,
        "quoteTiering": False,
    },
    "philip-kotler": {
        "name": "菲利浦．科特勒",
        "nameEn": "Philip Kotler",
        "tagline": "現代行銷學之父：品牌定位與顧客價值主張的分析框架",
        "avatarText": "科",
        "color": "#1e3a5f",
        "sourceCount": 17,
        "deceased": None,
        "specialCaution": None,
        "quoteTiering": False,
    },
    "coco-chanel": {
        "name": "可可．香奈兒",
        "nameEn": "Coco Chanel",
        "tagline": "Chanel創辦人：讓身體更自由的設計判斷與敘事主導權",
        "avatarText": "香",
        "color": "#0a0a0a",
        "sourceCount": 19,
        "deceased": {
            "year": 1971,
            "note": "已於西元1971年過世，且生前刻意營造傳奇形象，網路上多句流傳語錄查無實證出處；本角色設定僅能反映其生前公開言論與已查證資料。",
        },
        "specialCaution": None,
        "quoteTiering": True,
    },
    "andrej-karpathy": {
        "name": "安德烈．卡帕西",
        "nameEn": "Andrej Karpathy",
        "tagline": "AI研究者、前特斯拉AI總監：技術現況判讀與自主權評估框架",
        "avatarText": "卡",
        "color": "#00b8a9",
        "sourceCount": 15,
        "deceased": None,
        "specialCaution": None,
        "quoteTiering": False,
    },
}


def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def strip_copyright_block(text: str) -> str:
    idx = text.find(COPYRIGHT_MARKER)
    if idx == -1:
        raise ValueError(
            "找不到預期的版權區塊標記，SKILL.md 格式可能已變動，需人工檢查後更新 COPYRIGHT_MARKER"
        )
    return text[:idx].rstrip() + "\n"


def apply_jargon_replacements(text: str) -> str:
    for old, new in JARGON_REPLACEMENTS:
        text = text.replace(old, new)
    # 收拾替換掉整個詞後可能留下的多餘空白/標點
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def check_blacklist(text: str, context: str):
    for term in BLACKLIST_TERMS:
        if term in text:
            raise ValueError(
                f"[{context}] 黑名單關鍵字殘留：「{term}」，請補上對應的 JARGON_REPLACEMENTS 規則"
            )


def extract_sections(skill_md_path: Path) -> dict:
    raw = skill_md_path.read_text(encoding="utf-8")
    body = strip_frontmatter(raw)
    body = strip_copyright_block(body)

    parts = re.split(r"^## (.+)$", body, flags=re.M)
    # parts[0] 是第一個 ## 之前的內容（H1 標題與開場引語），之後是 (header, section_body, header, section_body, ...)
    sections = {"intro": apply_jargon_replacements(parts[0].strip())}
    for i in range(1, len(parts), 2):
        header_line = parts[i].strip()
        section_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        key = None
        matched = False
        for prefix, mapped_key in SECTION_PREFIX_MAP:
            if header_line.startswith(prefix):
                key = mapped_key
                matched = True
                break
        if not matched:
            print(f"  [警告] 未歸類的章節標題：「{header_line}」（略過，不進 systemPrompt）")
            continue
        if key is None:
            continue  # 明確捨棄（附錄）
        sections[key] = apply_jargon_replacements(section_body)

    check_blacklist(json.dumps(sections, ensure_ascii=False), skill_md_path.stem)
    return sections


def build_disclaimers(name: str, source_count: int) -> tuple[str, str]:
    short = f"基於約{source_count}個公開資料來源整理的框架推斷，不代表{name}本人真實立場。"
    full = (
        f"本角色設定整理自約{source_count}個公開演講、訪談、著作或媒體報導等來源，"
        f"聚焦{name}的公開言論與表達風格，並非{name}本人審閱或授權。"
        f"未做逐案查證的他人評價、決策內幕細節，也未建立完整生平時間線，"
        f"回覆內容為AI基於這些公開資料的角色扮演與框架推斷，僅供啟發與練習用途參考，"
        f"不應作為對{name}本人真實立場或未來行為的可靠依據。"
    )
    return short, full


def build_system_prompt(entry: dict, meta: dict) -> str:
    name = meta["name"]
    sec = entry["sections"]

    quote_lines = [
        line for line in sec.get("intro", "").splitlines() if line.strip().startswith(">")
    ]
    opening_quote = "\n".join(quote_lines)

    parts = [
        f"你現在要扮演{name}（{meta['nameEn']}）。請完全以第一人稱「我」回應，"
        f"不要用「{name}會怎麼看」這種第三人稱轉述，也不要跳出角色做 meta 分析。",
    ]
    if opening_quote:
        parts += ["", "最能代表你思維方式的一句話：", opening_quote]
    parts += [
        "",
        sec.get("role_rules", ""),
        "",
        "## 身份卡",
        sec.get("identity_card", ""),
        "",
        "## 核心心智模型",
        sec.get("mental_models", ""),
        "",
        "## 決策啟發式",
        sec.get("heuristics", ""),
        "",
        "## 表達DNA",
        sec.get("expression_dna", ""),
    ]

    if sec.get("timeline"):
        parts += ["", "## 人物時間線", sec["timeline"]]

    parts += [
        "",
        "## 價值觀與反模式",
        sec.get("values_antipatterns", ""),
        "",
        "## 智識譜系",
        sec.get("intellectual_lineage", ""),
        "",
        "## 這個角色設定的侷限（請誠實遵守，不要對使用者隱瞞）",
        sec.get("honesty_boundary", ""),
    ]

    if meta["deceased"]:
        parts.append(meta["deceased"]["note"])

    if meta["quoteTiering"]:
        parts.append(
            "引用你的語錄時，請延續「已查證原話」與「廣泛流傳但存疑」的雙軌標註習慣，"
            "不確定出處的說法要明確標註「流傳但存疑」，不要當成確鑿的本人原話使用。"
        )

    parts += [
        "",
        "## 本次對話情境",
        "使用者正在「多位人物AI思維顧問」網站上，同時徵詢你與其他幾位人物的意見，"
        "各自獨立作答，你不需要提及其他人物的存在。請針對使用者的問題，"
        "用你的思維框架給出具體看法或建議；回覆長度抓在300~500字，避免流水帳。"
        "若問題超出你的公開已知立場範圍，仍要如實標註「這是框架推斷，非本人真實立場」。"
        "免責聲明已在網站介面顯示過，不需要每次在回覆裡重複。",
    ]

    prompt = "\n".join(p for p in parts if p is not None)
    prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip() + "\n"
    return prompt


def main():
    print("=== 階段一：解析 SKILL.md ===")
    source_entries = []
    for pid in PERSONA_IDS:
        skill_md = SKILLS_ROOT / f"{pid}-perspective" / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"找不到 {skill_md}")
        sections = extract_sections(skill_md)
        source_entries.append({"id": pid, "sections": sections})
        print(f"  {pid}: {len(sections)} 個章節")

    SOURCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_JSON.write_text(
        json.dumps(source_entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已寫入 {SOURCE_JSON}")

    print("\n=== 階段二：組裝 personas-data.js ===")
    personas = []
    for entry in source_entries:
        pid = entry["id"]
        meta = PERSONA_META[pid]
        system_prompt = build_system_prompt(entry, meta)
        check_blacklist(system_prompt, f"{pid} systemPrompt")

        disclaimer_short, disclaimer_full = build_disclaimers(meta["name"], meta["sourceCount"])

        persona = {
            "id": pid,
            "name": meta["name"],
            "nameEn": meta["nameEn"],
            "tagline": meta["tagline"],
            "avatarText": meta["avatarText"],
            "color": meta["color"],
            "deceased": meta["deceased"],
            "specialCaution": meta["specialCaution"],
            "quoteTiering": meta["quoteTiering"],
            "sourceCount": meta["sourceCount"],
            "disclaimerShort": disclaimer_short,
            "disclaimerFull": disclaimer_full,
            "systemPrompt": system_prompt,
        }
        personas.append(persona)

        has_timeline = "timeline" in entry["sections"]
        print(
            f"  {pid}: systemPrompt {len(system_prompt)} 字元，"
            f"timeline={'有' if has_timeline else '無'}"
        )

    js_content = "window.PERSONAS = " + json.dumps(personas, ensure_ascii=False, indent=2) + ";\n"
    OUTPUT_JS.write_text(js_content, encoding="utf-8")
    print(f"\n已寫入 {OUTPUT_JS}")
    print(f"\n完成：共 {len(personas)} 位人物，無黑名單關鍵字殘留。")


if __name__ == "__main__":
    main()
