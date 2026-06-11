import os
import datetime as dt
import requests
import feedparser
from openai import OpenAI

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_PARENT_PAGE_ID = os.environ["NOTION_PARENT_PAGE_ID"]
SERENITY_X_HANDLE = os.getenv("SERENITY_X_HANDLE", "")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

RSS_FEEDS = [
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", # reuters，国际商业/金融新闻
    "https://www.scmp.com/rss/92/feed",                                                # SCMP，南华早报，偏中国、亚洲、地缘和商业
    "https://www.nasdaq.com/feed/rssoutbound?category=Markets",                        # Nasdaq Markets，美股市场新闻
]

def beijing_today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")

def fetch_rss():
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                items.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:600],
                })
        except Exception as exc:
            print(f"Warning: failed to fetch RSS feed {url}: {exc}")
            continue
    return items

def fetch_serenity():
    if not SERENITY_X_HANDLE:
        return "未配置 SERENITY_X_HANDLE，今日无法核验 Serenity 发帖。"

    if not X_BEARER_TOKEN:
        return (
            f"已配置 Serenity handle: {SERENITY_X_HANDLE}，"
            "但未配置 X_BEARER_TOKEN，暂无法通过 X API 拉取最新发帖。"
        )

    # 这里保留 X API 接入位。不同 X API 权限层级可用端点不同，
    # 建议确认账号与套餐后再启用正式抓取逻辑。
    return (
        f"已配置 Serenity handle: {SERENITY_X_HANDLE}，"
        "但 X API 抓取逻辑尚未启用。请在后续版本接入 tweets endpoint。"
    )

def generate_brief(news_items, serenity_text):
    source_text = "\n".join(
        f"- 标题：{item['title']}\n  摘要：{item['summary']}\n  链接：{item['link']}"
        for item in news_items
    )

    prompt = f"""
今天日期：{beijing_today()}

请生成一份中文晨间投资简报，面向关注中国科技类股票和黄金的投资者。

Serenity 来源：
{serenity_text}

新闻来源：
{source_text}

输出结构：
1. 一句话总览：今天最重要的市场线索。
2. Serenity 观察：只总结可核验发帖；不可核验则明确说明缺口。
3. 科技股关键新闻/政策/事件：
   覆盖芯片、CPO、先进封装、存储、AI硬件、半导体设备、算力基础设施、国产替代、出口管制、产业补贴、十五五规划相关方向。
   每条说明影响方向、相关产业链、潜在受益/受压环节。
4. 黄金关键线索：
   覆盖美元指数、美债收益率、实际利率、央行购金、地缘政治、通胀与降息预期、避险需求。
   判断对黄金偏多、偏空或中性。
5. 股票候选清单：
   推荐几支最符合中国十五五规划方向、且尽量贴近 Serenity 选股逻辑的股票。
   每支说明所属市场、核心逻辑、催化剂、主要风险。
   不要写成确定性收益承诺。
6. 今日关注：
   列出当天或近期需要跟踪的事件、数据、公司公告或政策节点。

要求：
- 使用中文。
- 保持简洁但有判断力。
- 对未经证实的消息标注“未证实”。
- 保留关键来源链接。
- 不要提供投资收益承诺。
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": "你是严谨的中文投研助理，重视来源、逻辑、风险和不确定性。"
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )

    return response.choices[0].message.content

def create_notion_page(markdown):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2026-03-11",
        "Content-Type": "application/json",
    }
    payload = {
        "parent": {"page_id": NOTION_PARENT_PAGE_ID},
        "properties": {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": f"晨间投资简报 {beijing_today()}"
                        }
                    }
                ]
            }
        },
        "markdown": markdown,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["url"]

def main():
    news_items = fetch_rss()
    serenity_text = fetch_serenity()
    brief = generate_brief(news_items, serenity_text)
    notion_url = create_notion_page(brief)
    print(f"Created Notion page: {notion_url}")

if __name__ == "__main__":
    main()
