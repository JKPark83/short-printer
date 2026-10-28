# YouTube Shorts performance metrics and topic trendiness (24h / 7d) from public data

Research date: 2026-10-19. Each claim below is dated where the source date matters. "Official" means YouTube/Google staff or docs; "industry" means third-party tool vendors or analysts; "folklore" means creator advice with no data behind it.

## Q1. Which Shorts metrics YouTube and creators treat as signals of a good Short (official, 2023–2026)

### Takeaway
The only Shorts-specific ranking signal YouTube has named officially is whether people **watch or swipe away** (shown in Analytics as "Viewed vs. swiped away"). Each Short is tested on a small seed audience first, and its reach then grows or shrinks. View counting changed twice. In March 2025 a Shorts view started counting on first play or replay, and on Aug 24, 2026 that rule was applied to every format. The old metric survives as "engaged views", which is what monetization and analytics use. Since Oct 1, 2026, original Shorts get more reach and re-uploads get less. Specific weightings for likes, shares, loops and subscriber gain have **not** been officially published.

### Cited Findings
- Todd Sherman, Shorts product lead, on Creator Insider (Aug 2023): Shorts views come mostly from the feed, not from a viewer choosing a video. The system therefore tests a Short on a seed set of people who "may enjoy your video, and depending on how that goes, it may get a lot more traffic or it may kind of taper off". The "viewed vs. swiped away" metric was added to Analytics so creators can see this. — [TechCrunch, 2023-08-25](https://techcrunch.com/2023/08/25/youtube-demystifies-the-shorts-algorithm-views-and-answers-other-creator-questions/); [Search Engine Journal](https://www.searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953/)
- Same source: Shorts and long-form are recommended differently. Long-form viewers tap to pick a video, which makes CTR meaningful. Shorts viewers swipe without knowing what comes next, so watch-vs-swipe takes the place of CTR. — [Search Engine Journal](https://www.searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953/)
- Things YouTube staff have said are **not** ranking factors (summarized by a third party from the same Q&A): an ideal length, posting time or day, a daily upload quota, and hashtags. — [OutlierKit summary of official statements](https://outlierkit.com/resources/youtube-shorts-algorithm/) (secondary source)
- Rene Ritchie (YouTube Creator Liaison) with Todd Beaupré (Sr. Director, Growth & Discovery), Shorts FAQ series, Aug 2024: "The algorithm follows the audience, so please the audience." Their advice is to check the Audience tab for which videos grow the audience and make more like those. — [Tubefilter, 2024-08-26](https://www.tubefilter.com/2024/08/26/rene-ritchie-shorts-creator-faqs/)
- **View counting change, Mar 31, 2025 (official):** announced by TeamYouTube (Meaghan) on the Help Community on 2025-03-26. A Shorts view now counts "as soon as a Short starts to play or is replayed, with no minimum watch time". The old metric was renamed "engaged views" and stays in Analytics Advanced Mode. Monetization and YPP eligibility still use engaged views (YPP: 1,000 subs plus 10M valid public Shorts views in 90 days). YouTube's stated reason was to match how TikTok and Instagram count. — [PPC Land](https://ppc.land/youtube-changes-how-shorts-views-are-counted-from-march-31/); [RouteNote](https://routenote.com/blog/how-are-views-counted-shorts-tiktok-reels/)
- The API is affected too: `videos.statistics.viewCount` and `channels.statistics.viewCount` now follow the new Shorts definition from 2025-03-31. — [YouTube Data API revision history](https://developers.google.com/youtube/v3/revision_history)
- **Change across all formats, Aug 24, 2026:** a view now counts from the first frame on VOD, Shorts and Live. An "engaged view" is a play the viewer chose, by clicking or by watching past the first few seconds. CTR, AVD, retention and YPP earnings still run on engaged views. Agentio estimates public long-form counts now run about 30% above engaged views (35,800 long-form videos, Jun–Jul 2026). — [PPC Land](https://ppc.land/youtube-counts-views-from-the-first-frame-across-all-formats-on-august-24/); [Agentio](https://www.agentio.com/blog/youtube-view-vs-engaged-view); [Emplifi docs](https://docs.emplifi.io/platform/latest/home/youtube-metric-update-august-2026)
- **Originality change, Oct 1, 2026 (official, Help Community):** YouTube updated its systems "to further prioritize original content and reduce the reach of content re-uploaded from other creators". A reused clip can still surface if it adds real commentary, editing or storytelling. Voice-over narration, minor technical edits and template-based bulk changes do not make a clip original (as reported). YouTube published no dashboard and no timescale. — [Android Authority](https://www.androidauthority.com/youtube-shorts-promoting-original-content-reposts-3718668/); [PPC Land](https://ppc.land/re-uploaded-shorts-lose-reach-as-youtube-favours-original-clips/)
- Shorts can be up to 3 minutes long for uploads from 2024-10-15 (square or taller). YouTube said it would tune recommendations for longer Shorts over the following months. — [PetaPixel, 2024-10-04](https://petapixel.com/2024/10/04/youtube-shorts-expands-video-length-to-three-minutes/)
- vidIQ, not official: lists retention, likes, comments and shares as signals, and reports Nate Black's analysis of 35B Shorts views (13s or 60s lengths did best; channels with 200+ Shorts grew more steadily; the first 3 seconds matter). This is vendor research and the method is not public. — [vidIQ blog](https://vidiq.com/blog/post/youtube-shorts-algorithm/)

### Inferences
- In public data, `viewCount` after Mar 2025 counts *impressions that started playing*, so it partly mixes swipe-aways with real watching. Views alone overstate a topic's appeal. Likes and comments per view (which the API still returns) are a cleaner public stand-in for "watched and cared".
- Loops/replays inflate the public `viewCount` because a replay counts as a view. A Short with high views and low likes per view may be short and looping, not a topic people want.
- What we can say officially: the signal that counts is how the seed audience reacts (watch vs. swipe). A topic predicts good performance when the target audience will **not swipe in the first second**. In practice that means the title or hook promises something they already care about.

### Gaps
- There is no official ranking weight for shares, likes, comments, subscribe-from-Short or loops. Claims that "shares are the strongest signal" are folklore or inference. I found no primary YouTube statement.
- I could not get a Creator Insider transcript from 2025–2026 that discusses the Shorts ranking signals in detail. The 2023 Sherman Q&A is still the primary source most often cited.

## Q2. Which topic-level properties (not editing) go with low swipe-away and high shares (industry data)

### Takeaway
Hard public data on topic vs. swipe-away is thin. Most of what exists covers engagement rates at the platform or industry level. Tools mostly judge a topic by **outlier performance**, meaning views relative to the channel's own baseline: a topic that over-performs across many unrelated channels is "demanded", not just liked by one channel's fans.

### Cited Findings
- Socialinsider 2025 (brand accounts): the average YouTube Shorts engagement rate is **0.40%** (TikTok 3.15%, Reels 0.65%). The formula is (likes + comments + shares) / views, with about 20 comments per Short on average. — [Socialinsider benchmarks](https://www.socialinsider.io/ja/social-media-benchmarks/all-social-media-platforms) (via search snippet; brand accounts only, not creators)
- Dash Hudson / Dash Social H2 2025 industry benchmarks: average views per Shorts post fell about 20% vs. six months earlier while on-demand video rose about 121%, and Shorts drew relatively more likes, comments and shares. — [Dash Social media & entertainment PDF](https://pages.dashsocial.com/hubfs/social-media-benchmark/2025/H2/media-entertainment-industry.pdf) (via search snippet; not verified in full)
- vidIQ Outliers groups outlier scores into bands: <2x (black), 2–5x (blue), 5–10x (purple), 10x+ (red). The score is a video's views divided by the channel's average views "within a similar timeframe". The exact baseline and age normalization are not disclosed. — [vidIQ Help: Outliers](https://support.vidiq.com/en/articles/9660010-outliers)
- OutlierKit defines its outlier score the same way, as a multiple of the channel's average views (5x = five times the typical video). — [OutlierKit: outlier scores](https://outlierkit.com/resources/outlier-scores/)

### Inferences
- What a topic can predict here: (1) the hook is understandable in under a second, (2) it touches the viewer's own body, money or daily life, which makes it shareable as "send this to someone", (3) there is a surprising claim or a counterintuitive answer. These are creator heuristics consistent with the watch-vs-swipe mechanism. No dataset I found measures them directly.
- Likes per view and comments per view from `videos.list` are the best public stand-in for "high engagement" across topics. Shares are **not** in the public API.

### Gaps
- I found no public dataset from vidIQ, TubeBuddy, OpusClip or Tubular that ties *topic category* to swipe-away rate or share rate for Shorts.
- I found no source for Korean body or health Shorts engagement benchmarks.

## Q3. Measuring trend velocity (24h vs. 7d) with the YouTube Data API and public signals

### Takeaway
Use `search.list` (`type=video`, `videoDuration=short`, `publishedAfter=now-24h` or `now-7d`, `order=viewCount`, `regionCode=KR`, `relevanceLanguage=ko`) and then `videos.list` with `part=statistics,contentDetails` to get views, likes, comments and duration. Raw views per hour is **biased toward young videos**: Shorts get most of their views on day 1 and the rate falls quickly. Compare videos only against peers of a similar age, or divide by an expected cumulative-views curve, and add an outlier ratio against the channel's baseline.

### Cited Findings
- `search.list` per the current docs: `videoDuration=short` means **under 4 minutes** (so a duration filter picks up non-Shorts too, and Shorts can now run to 3 min). `order=viewCount` sorts highest to lowest. `publishedAfter` takes RFC 3339. `regionCode` defaults to US. `relevanceLanguage` takes an ISO 639-1 code. `maxResults` is 0–50. `totalResults` is an approximation. — [YouTube Data API: search.list](https://developers.google.com/youtube/v3/docs/search/list)
- **Quota (changed 2026-06-01):** `search.list` and `videos.insert` now have their own quota buckets, and `search.list` gets 10,000 units/day by default. The current page says a call costs "1 unit in the Search Queries quota bucket". — [API revision history](https://developers.google.com/youtube/v3/revision_history); [search.list](https://developers.google.com/youtube/v3/docs/search/list). Older material, and some third-party docs still, say **100 units per search** from the shared 10,000-unit pool, so treat any pre-June-2026 quota math as out of date. — e.g., [Apify actor docs](https://apify.com/seemuapps/google-youtube-data)
- The public API has no Shorts flag. A duration ≤180s is the usual proxy, and OverseerOS says outright that duration "does not guarantee that YouTube internally classified" a video as a Short. — [OverseerOS](https://www.overseeros.com/blog/why-youtube-views-stop-after-24-hours)
- **Shorts growth curve, 72h (OverseerOS, 144 short-form videos ≤180s across 36 channels, published Aug 20–30, 2026):** by 24h, **64.3%** of the 72h views had arrived; by 48h, **87.2%**; the median 72h total was **1.56×** the 24h total. The day-2 view rate was **0.38×** the day-1 rate, and day 3 was **0.19×**. Only **4.2%** viewed faster after day 1; **16.0%** doubled their day-1 total by 72h; 4.2% tripled it. — [OverseerOS](https://www.overseeros.com/blog/why-youtube-views-stop-after-24-hours) (small sample, mostly small channels)
- Measure Studio (reported 2025-08-07): Shorts get about **60% of total views in the first day**; TikTok gets about 72% in 24h and 95% within 35 days. Sample size and method were not disclosed, and the summary's line about "peak at 35 days" looks garbled. — [Quasa summary of Measure Studio](https://quasa.io/media/measure-studio-analyzes-lifespan-of-long-form-content-and-shorts-on-youtube)
- Vendor and blog claims (low confidence): Shorts often reach their first distribution peak within 2–6h and may be re-tested over 24–48h. Completion in the first 100–200 views decides whether a Short gets pushed wider. — [TubeCore guide](https://tubecore.xpanddigital.io/blog/youtube-shorts-analytics-guide) (search snippet; not official)
- **YouTube Trending page removed on 2025-07-21** (announced 2025-07-11). It was replaced by category charts (Trending Music Videos, Trending Movie Trailers, Weekly Top Podcast Shows), and YouTube says popular content now reaches viewers through personalized recommendations. There is no general KR Trending list to scrape any more. `videos.list chart=mostPopular` is the closest public API stand-in (its current behavior after the page was removed is not verified). — [9to5Google](https://9to5google.com/2025/07/10/youtube-trending-page-removal/); [PPC Land](https://ppc.land/youtube-closes-trending-page-after-a-decade-of-operation/)
- **Google Trends API (alpha), announced 2025-07-24:** consistently scaled interest data for 1,800 days (5 years) at daily, weekly, monthly and yearly granularity, with region and sub-region filters. Data lags about **48h**, there is no 5-term limit, and access is by application. Nothing I found says it exposes the "YouTube Search" property the website offers. — [Google Search Central blog](https://developers.google.com/search/blog/2025/07/trends-api)
- **Naver DataLab search-trend API:** returns a ratio time series, not counts, where the highest value in the chosen period = 100. It covers daily, weekly and monthly periods with filters for gender, age and device (PC/mobile), up to 5 keyword groups per request. Without knowing it is relative, people misread it. — [digitalmarketer.co.kr](https://www.digitalmarketer.co.kr/insights/naver-datalab-api-data-for-non-developers); [NCloud API docs](https://api.ncloud-docs.com/docs/naver-api-hub-search-trend)

### Inferences
- **Why raw views/hour is unfair across ages:** the day-2 rate is about 0.38× day 1 and day 3 is about 0.19×. So a Short that is 6 days old has a lifetime views/hour well below what it had at 12h, even if it was a hit. Comparing a 12h-old video's VPH to a 6-day-old video's VPH systematically favors the young one. On the other hand, videos under ~3–6h can show deflated or noisy VPH while the seed test is still running.
- **Fair normalization, simple version:** estimate the eventual reach as `views / f(age)`, where `f` is the expected fraction of 72h (or 7d) views reached by that age. From OverseerOS: f(24h) ≈ 0.64, f(48h) ≈ 0.87, f(72h) = 1.0. By extrapolation, f(7d) is about 1.1–1.2 times the 72h total (inferred, not measured). Then compare the projected values. Or, simpler, rank only within age buckets (0–24h, 1–3d, 3–7d).
- **Outlier ratio beats absolute views for topics:** `views ÷ the channel's median views for recent Shorts` (or ÷ subscribers when the median isn't available) separates "this topic pulled an audience" from "this channel is just big". A topic that appears as a ≥3–5× outlier on **two or more unrelated channels** within 7 days is a strong trend signal. This is an inference following the vidIQ/OutlierKit idea; the thresholds are my choice and not validated.
- **24h vs. 7d velocity:** a topic is *rising* when the number of new uploads on it and their projected reach in the last 24h are at least what you'd expect from the 7-day daily average. It is *fading* when the 7-day set has hits but the 24h set doesn't. Google Trends and Naver DataLab daily ratios give a check outside YouTube, but both lag (Trends API by 48h) and are relative.
- Quota: if the 2026 bucket change holds (1 unit/search), a daily scan over a dozen keywords is cheap. Each `videos.list` call costs 1 unit for up to 50 IDs.

### Gaps
- No public data on the Shorts view curve out to 7 days at large sample size. The 72h numbers come from 144 videos and the 1-day share from an undisclosed sample.
- No vidIQ, 1of10 or Viewstats documentation says how they age-normalize outlier scores. 1of10's method was not found.
- Not verified: whether `videos.list?chart=mostPopular&regionCode=KR` still works or includes Shorts after the Trending page was removed.

## Q4. Pitfalls

### Takeaway
The main traps are: viral-but-off-niche topics that the channel's seed audience will swipe past, copying (now penalized directly since Oct 2026), and drawing conclusions from 1–3 data points or from very young uploads.

### Cited Findings
- Since 2026-10-01, re-uploads and lightly modified clips (voice-over, minor edits, templates) lose Shorts reach. — [Android Authority](https://www.androidauthority.com/youtube-shorts-promoting-original-content-reposts-3718668/)
- Seed-audience mechanism: reach depends on how "a set of people that may enjoy your video" react, so a topic only goes far if *that* audience watches. — [TechCrunch](https://techcrunch.com/2023/08/25/youtube-demystifies-the-shorts-algorithm-views-and-answers-other-creator-questions/)
- Only 4.2% of Shorts in the OverseerOS sample sped up after day 1, so a slow start rarely recovers. A large share of a Short's 72h total is already visible at 24h. — [OverseerOS](https://www.overseeros.com/blog/why-youtube-views-stop-after-24-hours)
- After Mar 2025 (Shorts) and Aug 2026 (all formats), public view counts include near-zero-second plays, so view-based comparisons across that date are not like-for-like. — [PPC Land](https://ppc.land/youtube-changes-how-shorts-views-are-counted-from-march-31/); [PPC Land Aug 2026](https://ppc.land/youtube-counts-views-from-the-first-frame-across-all-formats-on-august-24/)

### Inferences
- A trend from outside the niche, such as a celebrity meme on a body-facts channel, only counts if the channel can give it a real angle that fits the niche. Otherwise score it down for fit even when trendiness is high.
- One mega-viral Short from a huge channel is weak evidence. Several mid-size outliers on different channels is strong evidence.
- Results tied to news (e.g., a health scare) fade fast and are sensitive under `sensitive_gate`. Weigh freshness against the risk of getting facts wrong.

### Gaps
- No quantified data on how often off-niche trend-jacking helps or hurts small Shorts channels.

## Recommendation: 화제성 (trendiness) 1–5 rubric for an LLM

This is an inference, built from the findings above. Input per candidate topic: a list of recent related Shorts with `title, views, views_per_hour, age_hours` (and channel median or subscribers if available).

**Preprocessing the LLM should do (or code should do first):**
1. Drop Shorts that are clearly unrelated in meaning to the candidate topic (same keyword, different subject).
2. Put each Short in an age bucket: **A = <6h** (too young: don't trust VPH, only note that it exists), **B = 6–24h**, **C = 1–3d**, **D = 3–7d**. Ignore anything older than 7d for trendiness.
3. Use projected reach, not raw VPH: `proj = views / f(age)` with f ≈ 0.30 at 6h (rough guess), 0.64 at 24h, 0.87 at 48h, 1.0 at 72h, ~1.15 at 7d. Or, simpler, compare VPH only against other Shorts in the **same bucket**.
4. If channel baseline data is available, outlier = views ÷ channel median (≥3× counts as a hit).

**Scores:**
- **5 (hot now):** at least 2 related Shorts from **different channels** in bucket B (6–24h) whose VPH is in the top quarter of the whole list (or outlier ≥5×), **and** the 7d set also shows the topic (it is rising, not a one-off). Optionally confirmed by a news or search spike in the last 48h.
- **4 (rising):** 1 strong B-bucket hit (top-quarter VPH or ≥3× outlier) plus supporting C/D-bucket hits, or ≥3 C-bucket hits across channels.
- **3 (steady evergreen):** related Shorts exist across C/D with ordinary performance (median VPH for the list), with no 24h acceleration. People want it, but it isn't "now".
- **2 (cooling or thin):** hits only in the D bucket (3–7d) with nothing new in 24h, or only 1 related Short in total, or all hits from one big channel.
- **1 (no signal):** no related Shorts in 7d, or related Shorts all clearly under-perform (bottom quarter of VPH, and likes/views well below the list's typical ratio).

**Rules for Shorts under 24h old:**
- Under 6h: never score 5 based only on these. They raise confidence if ≥2 appear across channels ("people are uploading on this now"), but their VPH is noisy while the seed test runs.
- 6–24h: the most informative bucket for "now". Compare VPH only against other 6–24h videos, or use projected reach (÷0.64 at 24h). Raw VPH would favor them unfairly over 3–7d videos.
- One young viral hit from a channel with a huge baseline counts as at most 4 unless it is an outlier relative to that channel.

**Fallback when no popular-Shorts list is supplied (web/news based):**
- Base the score on news and search freshness. **5:** several independent news reports, or a sharp Naver DataLab / Google Trends rise, within the last 24–48h, directly about the topic. **4:** coverage in the last 7 days, or a seasonal peak happening now (e.g., a heatwave for heat-illness topics). **3:** an evergreen topic with steady search interest and no recent news. **2:** last notable coverage weeks ago. **1:** no recent coverage and no search interest.
- Cap the fallback score at **4** unless at least two independent sources in the last 48h confirm it. The LLM should also say "근거: 뉴스 기반(쇼츠 데이터 없음)" (basis: news only, no Shorts data) so a person knows how confident to be.
- Remember that Naver DataLab and Google Trends values are relative (max = 100) and the Trends API lags about 48h. Look at the *shape* (rising or falling), not the absolute level.

**Always add these notes (not part of the score):** whether the topic fits the channel niche (off-niche means a lower fit score, not lower trendiness), whether doing it would mean copying a viral Short (penalized for originality since Oct 2026), and whether it is a sensitive or health-news topic.
