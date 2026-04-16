import streamlit as st
import feedparser
import urllib.parse
from html import unescape
import re
import time
import calendar
# ページ基本設定（全幅レイアウト）
st.set_page_config(page_title="AI News Dashboard", layout="wide", initial_sidebar_state="auto")

def fetch_google_news_rss(query):
    """Google News RSSから検索ワードに基づいてニュースを取得する"""
    encoded_query = urllib.parse.quote(query)
    # 日本語のニュースを取得するようにパラメータを設定 (hl=ja, gl=JP)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(url)
    return feed.entries

def is_event_announcement(entry):
    """タイトルや配信元から、単なるイベントの告知・募集か、記事（レポート等）かを判定する"""
    title = entry.get("title", "")
    source_title = entry.get("source", {}).get("title", "") if "source" in entry else ""
    
    # 明確に読み物（レポート等）であるものは告知から外す
    report_keywords = ["レポート", "まとめ", "報告", "感想", "潜入", "レポ", "アーカイブ", "振り返り"]
    if any(k in title for k in report_keywords):
        return False
        
    # 告知に使われやすいキーワード
    event_keywords = ["イベント", "セミナー", "カンファレンス", "ウェビナー", "登壇", "展示会", "ミートアップ", "フォーラム", "勉強会", "説明会"]
    announce_keywords = ["開催", "告知", "募集", "申込", "受付", "参加無料", "日程", "決定", "予定", "お知らせ", "迫る"]
    
    has_event = any(k in title for k in event_keywords)
    has_announce = any(k in title for k in announce_keywords)
    is_pr = "PR TIMES" in source_title or "アットプレス" in source_title or "プレスリリース" in title
    
    if has_event and (has_announce or is_pr):
        return True
        
    if "開催決定" in title or "登壇します" in title or "登壇予定" in title or title.endswith("開催") or title.endswith("開催へ"):
        return True
        
    return False

def render_news_cards(entries):
    """取得したニュースエントリをカード状にレンダリングする"""
    if not entries:
        st.warning("ニュースが見つかりませんでした。別の検索ワードをお試しください。")
        return
        
    # 記事を時系列（最新時刻が先頭になる降順）に並び替える
    entries = sorted(
        entries,
        key=lambda x: calendar.timegm(x.published_parsed) if "published_parsed" in x and x.published_parsed else 0,
        reverse=True
    )
        
    html_blocks = ['<div class="news-grid">']
    
    progress_text = "✨ ニュースを読み込み・描画中..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, entry in enumerate(entries):
        my_bar.progress((i) / len(entries), text=f"{progress_text} ({i}/{len(entries)}件完了)")
        
        title = entry.get("title", "No Title")
        link = entry.get("link", "#")
        
        # 記事の配信サイト名とURLを取得（Google Favicon取得に利用）
        site_name = "外部サイト"
        site_domain = ""
        if "source" in entry and "href" in entry.source:
            site_domain = urllib.parse.urlparse(entry.source.href).netloc
            if "title" in entry.source:
                site_name = entry.source.title
                # タイトル末尾に「 - サイト名」が含まれる場合は見栄えを良くするため削除
                if title.endswith(f" - {site_name}"):
                    title = title[:-(len(site_name) + 3)]
        else:
            # 代替処理：タイトルからサイト名を分割
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                site_name = parts[1]
        
        # サイトのサムネイル（Favicon）URLを取得（Googleの無料APIを利用）
        favicon_img = ""
        if site_domain:
            favicon_url = f"https://s2.googleusercontent.com/s2/favicons?domain={site_domain}&sz=128"
            favicon_img = f'<img src="{favicon_url}" alt="{site_name} icon" class="site-icon">'
        
        published = entry.get("published", "Unknown Date")
        
        # 新着判定 (24時間以内)
        is_new = False
        if "published_parsed" in entry and entry.published_parsed:
            article_ts = calendar.timegm(entry.published_parsed)
            if time.time() - article_ts < 24 * 3600:
                is_new = True
        
        new_tag_html = '<span class="new-badge">NEW ✨</span>' if is_new else ''
        
        # 有料記事（または会員登録必須）の可能性が高いドメインやキーワードで判定
        paywall_domains = ["nikkei.com", "asahi.com", "mainichi.jp", "yomiuri.co.jp", "diamond.jp", "newspicks.com", "wsj.com", "nytimes.com", "premium.toyokeizai.net"]
        is_paid = False
        if any(domain in site_domain for domain in paywall_domains):
            is_paid = True
        elif any(keyword in title for keyword in ["有料会員", "会員限定", "【有料】", "（有料）"]):
            is_paid = True
            
        paid_tag_html = '<span class="paid-badge">🔒 有料記事</span>' if is_paid else ''
        
        # 概要は表示させず、カードをflexコンテナ化しボタンを下揃えに
        # ☆Markdown誤認識を防ぐため、HTMLの字下げは一切行いません☆
        card_html = f"""<div class="news-card">
<div>
<div class="site-tag-container">
{favicon_img}
<span class="site-tag">{site_name}</span>{new_tag_html}{paid_tag_html}
</div>
<div class="news-title"><a href="{link}" target="_blank">{title}</a></div>
</div>
<div class="news-footer">
<div class="news-date">⏳ {published}</div>
</div>
</div>"""
        html_blocks.append(card_html)
        
    # ロードバーを完了状態にしてから隠す
    my_bar.progress(1.0, text="✨ 描画が完了しました！")
    time.sleep(0.5)
    my_bar.empty()
        
    html_blocks.append('</div>')
    
    # 1つのMarkdownとして書き出すことで、CSSグリッドの高さを完全に揃えます
    st.markdown("".join(html_blocks), unsafe_allow_html=True)

def main():
    
    # === サイドバー：検索機能 ===
    st.sidebar.header("🔍 検索設定")
    search_keyword = st.sidebar.text_input("検索ワード", value="AI")
    
    # === カスタムCSSによるプレミアムなコンポーネントデザイン ===
    st.markdown("""
        <style>
        /* デフォルトの余白（特に上部h1付近の不要なスペース）を調整 */
        div.block-container {
            padding-top: 4rem !important;
        }
        h1 {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }

        /* CSSグリッドを利用してカードの高さを完璧に揃え、スマホでもはみ出さないようにする */
        .news-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }
        
        /* タブメニュー（すべて、デザイン等）をスクロール時に上部へ固定 */
        div[data-testid="stTabs"] {
            overflow: visible !important;
        }
        /* バージョンによるHTML構造の違いを吸収するため複数のセレクタを指定 */
        div[data-testid="stTabs"] > div:first-child,
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            position: -webkit-sticky !important; /* Safari対応 */
            position: sticky !important;
            top: 2.875rem !important; /* Streamlitの標準ヘッダーを回避する位置 */
            background-color: #ffffff !important; /* ライトモード固定のため背景を白に */
            z-index: 990 !important;
            padding-top: 1rem !important;
            padding-bottom: 0.5rem !important;
            border-bottom: 1px solid rgba(0,0,0,0.05) !important; /* スクロール時の境界線 */
        }

        /* カード側からホバーアニメーションを削除・影をすっきりと */
        .news-card {
            background-color: var(--secondary-background-color);
            padding: 26px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.05); /* 控えめな影 */
            border: 1px solid rgba(128, 128, 128, 0.15);
            /* 中身の配置設定（フレックスボックスで上下の空間を利用しボタンを下揃えに） */
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        
        /* 記事サイトを分かりやすくするためのタグデザイン */
        .site-tag-container {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 12px;
        }
        .site-icon {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 8px;
            object-fit: cover;
            border: 1px solid rgba(128, 128, 128, 0.2);
            background-color: #FFF;
        }
        .site-tag {
            display: inline-block;
            background-color: rgba(74, 144, 226, 0.15);
            color: #4A90E2;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 700;
        }
        
        /* 新着用バッジのデザインとアニメーション */
        .new-badge {
            display: inline-block;
            background: linear-gradient(135deg, #FF4B2B, #FF416C);
            color: #FFFFFF;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 800;
            letter-spacing: 0.5px;
            animation: pulse-glow 2s infinite;
            box-shadow: 0 0 8px rgba(255, 75, 43, 0.4);
        }
        
        @keyframes pulse-glow {
            0% { transform: scale(1); box-shadow: 0 0 8px rgba(255, 75, 43, 0.4); }
            50% { transform: scale(1.05); box-shadow: 0 0 12px rgba(255, 75, 43, 0.7); }
            100% { transform: scale(1); box-shadow: 0 0 8px rgba(255, 75, 43, 0.4); }
        }

        .news-title {
            color: var(--text-color);
            font-size: 1.35em;
            font-weight: 700;
            margin-bottom: 12px;
            line-height: 1.4;
            margin-top: 4px;
        }
        
        .news-date {
            color: var(--text-color);
            opacity: 0.6;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            min-width: 0;
            margin-right: 8px;
        }
        
        .news-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: auto;
            padding-top: 16px;
            overflow: hidden; /* コンテナからはみ出さないように */
        }
        

        .news-title a {
            color: inherit;
            text-decoration: none;
        }
        .news-title a:hover {
            color: #4A90E2;
        }

        /* 有料記事用バッジのデザイン */
        .paid-badge {
            display: inline-block;
            background: linear-gradient(135deg, #718096, #4A5568);
            color: #FFFFFF;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 700;
            letter-spacing: 0.5px;
            box-shadow: 0 0 6px rgba(0, 0, 0, 0.15);
        }
        </style>
    """, unsafe_allow_html=True)
    
    if search_keyword:
        # 情報の性質（総合、デザイン、イベント等）ごとにタブを分割
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📰 すべて", "🎨 デザイン", "📅 イベント", "📓 note", "🖼️ AI画像生成", "💼 フリーランス"])
        
        with tab1:
            st.subheader(f"「{search_keyword}」の最新ニュース")
            with st.spinner("総合ニュースを検索中..."):
                # 普通に検索し、単なる告知記事だけPython側で除外する（レポートは残す）
                general_entries = fetch_google_news_rss(search_keyword)
                general_entries = [e for e in general_entries if not is_event_announcement(e)]
            render_news_cards(general_entries)
            
        with tab2:
            st.subheader(f"「{search_keyword}」の【デザイン】最新情報")
            with st.spinner("デザイン関連情報を検索中..."):
                design_query = f"{search_keyword} デザイン OR {search_keyword} UI OR {search_keyword} UX OR {search_keyword} デザイナー"
                design_entries = fetch_google_news_rss(design_query)
                design_entries = [e for e in design_entries if not is_event_announcement(e)]
            # 再利用しやすいよう別関数にしたレンダリング処理を実行
            render_news_cards(design_entries)
            
        with tab3:
            st.subheader(f"「{search_keyword}」の【イベント・セミナー】情報")
            with st.spinner("イベント情報を検索中..."):
                event_query = f"{search_keyword} イベント OR {search_keyword} セミナー OR {search_keyword} カンファレンス OR {search_keyword} ウェビナー OR {search_keyword} 登壇"
                event_entries = fetch_google_news_rss(event_query)
                # ここは「告知・募集」記事のみを抽出する
                event_entries = [e for e in event_entries if is_event_announcement(e)]
            render_news_cards(event_entries)
            
        with tab4:
            st.subheader(f"「{search_keyword}」の note 記事")
            with st.spinner("noteの記事を検索中..."):
                # site: 演算子を使って note.com 内の記事に限定して検索する
                note_query = f"{search_keyword} site:note.com"
                note_entries = fetch_google_news_rss(note_query)
                note_entries = [e for e in note_entries if not is_event_announcement(e)]
            render_news_cards(note_entries)

        with tab5:
            st.subheader("【AI画像生成】情報（デザイナー向け）")
            with st.spinner("デザイナー向けAI画像生成記事を検索中..."):
                ai_image_query = "画像生成 デザイン OR 画像生成 デザイナー OR 画像生成 UI OR Midjourney OR Stable Diffusion"
                ai_image_entries = fetch_google_news_rss(ai_image_query)
                ai_image_entries = [e for e in ai_image_entries if not is_event_announcement(e)]
            render_news_cards(ai_image_entries)
            
        with tab6:
            st.subheader("【フリーランス】情報（悩み解決・独立）")
            with st.spinner("フリーランスの悩み解決に関する記事を検索中..."):
                freelance_query = "フリーランス 悩み OR フリーランス 解決 OR フリーランス 独立 OR フリーランス 案件 OR 個人事業主 悩み"
                freelance_entries = fetch_google_news_rss(freelance_query)
                freelance_entries = [e for e in freelance_entries if not is_event_announcement(e)]
            render_news_cards(freelance_entries)

if __name__ == "__main__":
    main()
