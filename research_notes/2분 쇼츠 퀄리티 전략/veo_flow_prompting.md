# Google Flow / Veo 3.1 / Gemini Omni Flash: prompting and workflow for consistent explainer clips (as of Oct 2026)

Context: the user generates 9:16, 360p, 8s, x1 clips with "Omni 1.1 Flash" in Flow at 6 credits per clip (720p = 12). As of Oct 2026, Flow's video models are Veo 3.1 (Lite / Fast / Quality) and Gemini Omni Flash 1.1 (released Aug 27, 2026). Most published "Veo 3" prompt advice dates from 2025 and was written for Veo 3/3.1. Advice specific to Omni (May–Sep 2026) is marked as such. Veo 2-era Flow features (Jump To, the old Extend) are marked as older.

## Q1. Official prompt structure (Veo 3.1 and Omni), prompt length, negative prompts

### Takeaway
Google's official Veo 3.1 formula is **[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]**, with audio described separately (quoted dialogue, "SFX:", "Ambient noise:"). For Omni Flash (2026), the guidance shifts to "director's brief" prose: describe the whole shot, name one camera move, say whether you want one continuous shot, always direct the audio, and state what must stay unchanged. Length matters less than precision: Google's own Omni examples range from 4 words to a full paragraph. The failure mode is cramming many goals into one prompt, not word count as such.

### Cited Findings
- Official Veo 3.1 formula: "[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]". Example: "Medium shot, a tired corporate worker, rubbing his temples in exhaustion, in front of a bulky 1980s computer in a cluttered office late at night. The scene is lit by the harsh fluorescent overhead lights and the green glow of the monochrome monitor. Retro aesthetic, shot as if on 1980s color film, slightly grainy." — [Google Cloud blog, Ultimate prompting guide for Veo 3.1 (Oct 15, 2025)](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Official vocabulary lists. Movement: dolly shot, tracking shot, crane shot, aerial view, slow pan, POV shot. Composition: wide shot, close-up, extreme close-up, low angle, two-shot. Lens/focus: shallow depth of field, wide-angle lens, soft focus, macro lens, deep focus. — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Negative prompting (official): describe the exclusion as a positive scene description, not a bare "no X". Write "a desolate landscape with no buildings or roads" rather than "no buildings". — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Timestamp prompting (official, Veo 3.1): one 8s clip can be scripted as `[00:00-00:02] … [00:02-00:04] …` sub-shots, each with its own camera and SFX. — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Omni Flash official tips, as summarized by third parties: describe the whole scene (subject, action, setting, lighting, camera); **specify whether you want one continuous shot or allow Omni Flash to add its own cuts**; direct the audio; keep edit prompts short with "keep everything else the same". — [OpenArt Omni Flash guide](https://openart.ai/blog/gemini-omni-flash-prompt-guide/) (search summary)
- Google AI's five official Omni tips (May 26, 2026): leverage real-world knowledge, take control of text rendering, direct the camera like a pro, edit iteratively, change action on the fly. A third-party five-part framework: Goal, Input role (how to use uploaded content), Scene, Motion, Constraints (what must not change and what to avoid). — [pasqualepillitteri.it summary of the official Google AI guide](https://pasqualepillitteri.it/en/news/3513/mastering-gemini-omni-flash-video-prompting-guide) (summary only; the page failed to load in full)
- Omni prompts read "like direction given to a crew, not like descriptions of a finished frame". "Google's examples run from four words up to a full paragraph, and both extremes appear in the same announcement." Brevity matters less than precision. — [fal.ai, How to use Gemini Omni Flash 1.1](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Suggested order: "subject, action, camera, style, lighting, constraints, and final-frame instructions". Avoid "giant paragraph prompts with ten goals." — [Sagnik Bhattacharya, Gemini Omni in Google Flow](https://sagnikbhattacharya.com/blog/gemini-omni-google-flow)
- Common mistakes listed for Omni: omitting audio; over-cramming details into one prompt; asking for more than ~10s; vague edits ("make it better"); expecting consistency without reference images during big changes. Formula: "[Subject + look] doing [action] in [setting]. [Camera movement + framing]. [Lighting + atmosphere]. [Style + film reference]. [Audio + on-screen text]." — [Atlabs, Ultimate Gemini Omni Flash prompting guide 2026](https://www.atlabs.ai/blog/ultimate-gemini-omni-flash-prompting-guide-2026)
- Ordering debate: some community guides put camera first ("placing camera mechanics at the start gives the renderer immediate spatial rules"). — [LTX Studio Veo 3.1 prompt guide](https://ltx.studio/blog/veo-prompt-guide) (community claim, not from Google)
- English prompts give the most predictable results with Omni, although it accepts many languages. — [veo3ai.io, Omni text rendering](https://www.veo3ai.io/blog/gemini-omni-text-rendering-prompts-ai-video-text) (search summary)

### Inferences
- A 90+ word prompt is not harmful in itself. The risk is goal count: two subjects, two camera moves and three actions in one 8s clip. For an explainer channel, use one subject, one action, one camera move, a style block (which can be long and fixed), and an audio line.
- Because Omni may insert its own cuts, explicitly write "single continuous shot, no cuts" in every scene prompt when each clip should be one shot.
- Put "what must not change" (constraints) at the end of the prompt. That is where Google's edit-style guidance puts it, and it doubles as the de facto negative prompt, since Flow has no separate negative-prompt field. That last point is inferred: I found no Flow UI documentation of a negative-prompt field.

### Gaps
- Could not load the full text of the official Google AI "Mastering Gemini Omni" post (May 26, 2026). Its wording comes only from third-party summaries.
- The official Vertex AI Veo prompt-guide page now redirects to `docs.cloud.google.com/gemini-enterprise-agent-platform/...`, and its body did not render. The Google Cloud blog was used instead.
- No controlled test was found that measures the effect of prompt length on quality.

## Q2. Consistency across many 8s clips (Ingredients, Frames to Video, Extend, Scene Builder, style reference)

### Takeaway
In Flow as of Oct 2026, Omni Flash 1.1 supports Text-to-Video, Frames to Video (first frame, or first and last), and Ingredients/References. Extend is "coming soon" for Omni; Veo 3.1 Lite supports it at 8s only. The most reliable consistency recipe is from Google's own guide: generate a reference still with Nano Banana (Gemini Flash Image / Nano Banana Pro or 2.1), then either (a) attach it as an Ingredient in every clip or (b) use it or its edits as the first frame (and optionally last frame). Seeds and style locking are not exposed in Flow.

### Cited Findings
- Flow feature matrix (official). Veo 3.1 Lite: T2V, first frame, first+last frame, Ingredients (8s only), Extend (8s only), no V2V editing. Veo 3.1 Fast: same but no Extend. Veo 3.1 Quality: no Ingredients, no Extend. **Omni Flash 1.1: T2V, first frame, first+last frame, Ingredients/References, Extend "coming soon", video-to-video editing**. All models support both aspect ratios. Omni offers 4/6/8/10s; Veo 3.1 offers 4/6/8s. — [Google Flow Help, models & supported features](https://support.google.com/flow/answer/16352836?hl=en)
- Image models in Flow: Nano Banana Pro, Nano Banana 2 Lite, Nano Banana 2.1. — [Google Flow Help](https://support.google.com/flow/answer/16352836?hl=en)
- Official consistency workflow: generate character and setting reference images with Gemini 2.5 Flash Image (Nano Banana) first, then use them in Ingredients to Video. Each shot prompt starts "Using the provided images for the detective, the woman, and the office setting, create a …". — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Official first/last-frame workflow: make start and end stills with the image model, then prompt Veo with the camera move that connects them ("smooth 180-degree arc shot, starting with … to seamlessly end on …"). — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Veo 3.1 Ingredients to Video (Jan 2026): better identity consistency "even as the setting changes". You can "reuse an object, backgrounds or textures across scenes", and it is built for the mobile (vertical) format. — [Google blog, Veo 3.1 Ingredients to Video](https://blog.google/innovation-and-ai/technology/ai/veo-3-1-ingredients-to-video/)
- The Veo 3.1 Ingredients system allows up to 3 reference images. Community advice: avoid text-only character prompts and use Ingredient slots to stop facial drift. — [Google blog via search summary](https://blog.google/innovation-and-ai/technology/ai/veo-3-1-ingredients-to-video/); [veo3gen.app](https://www.veo3gen.app/blog/veo-31-ingredients-in-flow-a-creator-workflow-to-lock-characters-props-and-locat)
- Omni references: attach product images, charts, storyboards or base clips. List the "exact shape, colour, logo, or character details to keep". Ask for "stable first and final frames". Run "short controlled tests" first. — [Sagnik Bhattacharya](https://sagnikbhattacharya.com/blog/gemini-omni-google-flow)
- Omni references are addressed by explicit role in the prompt ("keep the character from image_0", "match the camera move in video_0"). Through the API: `<IMAGE_REF_0>` and up to 3 reference videos of 3s or less each. — [Atlabs](https://www.atlabs.ai/blog/ultimate-gemini-omni-flash-prompting-guide-2026); [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- First+last frame tip: "Generate both images from the same base file using editing tools to ensure consistency in lighting, materials, and positioning." — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Start and end frames for Omni 1.1 in Flow were announced Aug 27, 2026: "This helps keep the characters and narrative consistent as you thoughtfully transition between frames." — [Google blog, New creative controls in Google Flow](https://blog.google/innovation-and-ai/models-and-research/google-labs/new-creative-controls-google-flow/)
- Older (Veo 2-era) Flow: Scene Builder Extend used "the last 24 frames" of a clip to continue it, and "Jump To" moved a subject to a new setting while keeping its look. Both originally worked only with Veo 2. The recommended Veo 3 workaround was Scene Builder plus Frames-to-Video. — [eastondev Veo 3 long-video guide (Dec 2025)](https://eastondev.com/blog/en/posts/dev/20251207-veo3-long-video-guide); [Google blog, 5 tips for Flow](https://blog.google/technology/ai/flow-video-tips/)

### Inferences
- For this pipeline, the practical lock is: **one channel style still** generated once in Nano Banana, attached as an Ingredient or Reference to every scene, plus a **fixed, word-for-word style block** pasted into every prompt (the channel's `[video] style` prefix already does this).
- Seeds are not exposed in the Flow UI (no source documents them), so visual consistency must come from references and frames, not from the RNG.
- Ingredients and first-frame conditioning both cost the same credits as plain T2V in the cost table (no surcharge is listed), so consistency is a workflow cost, not a credit cost.

### Gaps
- Flow's exact Ingredient/Reference slot limit for Omni Flash 1.1 is not documented on the help page. The 3-image figure is for Veo 3.1.
- No authoritative source on whether Flow keeps any style or seed memory across generations in a project.

## Q3. Stylized 3D / miniature diorama / tilt-shift / clay look: keywords and drift into photoreal

### Takeaway
"Tilt-shift" and "diorama" mean different things to the model. Tilt-shift is a focus trick that makes a **real, full-size, photoreal** scene look small, so it pulls toward photorealism. Diorama, clay or physical-miniature language pulls toward the stylized model look. To stay stylized, describe a physical tabletop model (materials, scale cues, studio light), generate the look first as a still, and animate it with a slow single camera move and minimal figure motion.

### Cited Findings
- Recommended workflow (community): (1) make a macro still with Nano Banana Pro, (2) animate it with Veo 3.1 image-to-video using a single slow camera move. Restate the still's exact setup in the video prompt, or the scene drifts. — [Novoads, How to create miniature world videos with AI](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- Keywords for the miniature illusion: a focus band ("shallow focus, only the middle sharp, foreground and background softly blurred"), a high angle ("high-angle shot looking down" / bird's-eye), a scale anchor (tiny figures plus one oversized everyday object), "hyperrealistic macro photo", "hand-painted figures", "bright, soft natural light". — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- What breaks it: an eye-level camera with deep focus looks life-size; too many moving bodies with a fast camera make figures melt or multiply; a video prompt that describes a different layout from the still makes the scene drift mid-clip. — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- Claim: avoid "tilt-shift lens" or "miniature effect" because Google's Veo docs never list them. — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai) (community opinion; the official lists do include "macro lens" and "shallow depth of field")
- Distinction: "Diorama is a real model usually shot with enough depth of field to look large, while tilt-shift is a focus trick that makes a real full-size scene look small." For the diorama look, specify a physical miniature with fine surface scale and deep focus, and forbid tilt-shift shallow bands. — [Melies, Diorama technique](https://melies.co/cinematic-techniques/effects/diorama) (search summary)
- Official examples show that style words drive the look ("Retro aesthetic, shot as if on 1980s color film"), and the official style list starts with "Photorealistic, Cinematic". — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)

### Inferences
- Example prompt pattern for this channel (my synthesis, untested): "Single continuous shot. High-angle three-quarter view of a handcrafted miniature tabletop diorama of a Seoul city district: clay and painted-resin buildings, felt trees, tiny hand-painted figures, visible fingerprint texture on matte clay surfaces, model-railway scale. Slow push-in toward [landmark]. Soft diffused studio softbox light, gentle shadows, pastel palette, shallow depth of field like macro photography of a scale model. Stylized handmade miniature, not real footage. Audio: soft ambient room tone, light city murmur, no dialogue, no music."
- Things that likely cause drift into photoreal (inferred from the sources above): "cinematic", "photorealistic", "aerial drone shot", "4K footage", or naming real-world camera footage; eye-level street views; real-time human motion; long fast moves that reveal unmodelled "outside the table" space. Mention the table edge or backdrop, or keep the frame inside the model.
- The style still in the Ingredient or first frame does most of the work. Text alone is the weakest lock for material looks.

### Gaps
- No source specifically tested clay or diorama style stability on Omni Flash 1.1 versus Veo 3.1.
- No official Google guidance on "tilt-shift" as a keyword.

## Q4. Camera vocabulary and known failure modes (text, morphing, limbs, aspect ratio)

### Takeaway
Veo and Omni understand standard film terms (dolly, tracking, crane, pan, orbit/arc, whip pan, dolly zoom, aerial, POV, macro, shallow DOF). Name the move with its direction and its endpoints. The main failure modes: small or detailed generated text is messy; many moving figures melt; Omni may add cuts unless told not to. 9:16 is native in Flow (no crop needed).

### Cited Findings
- Omni camera language: dolly zoom, snap zoom, whip pan, 360-degree orbit. "Naming both ends of a move fixes the destination and leaves the middle negotiable." — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Camera moves can be set in plain language by naming the move and its direction ("pan left", "dolly in"). — [OpenArt Omni guide](https://openart.ai/blog/gemini-omni-flash-prompt-guide/) (search summary)
- Official example of an arc shot: "The camera performs a smooth 180-degree arc shot …". Crane example: "Crane shot starting low on a lone hiker and ascending high above, revealing …". — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Safest miniature moves: slow pan, slow dolly in, crane down, or a static camera with the world moving. — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- Text: Omni's generated text is "messy" when prompts ask for lots of small text. — [Sagnik Bhattacharya](https://sagnikbhattacharya.com/blog/gemini-omni-google-flow). Text rendering is one of Google's five official Omni tips: treat text as a physical object with material, location, lighting, timing, size and contrast. Supported languages include English, Chinese, Japanese and Korean. — [veo3ai.io](https://www.veo3ai.io/blog/gemini-omni-text-rendering-prompts-ai-video-text) (search summary; vendor claims of "pixel-perfect" lower thirds are unverified)
- For clean plates, explicitly exclude "titles or subtitles" and add "no on-screen text". — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Aspect ratio: every Flow video model supports both aspect ratios (16:9 and 9:16). — [Flow Help](https://support.google.com/flow/answer/16352836?hl=en). In the Omni API, 9:16 is selectable (default 16:9). "Vertical framing … naturally constrains subject movement, improving camera lock consistency." — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Edits keep the source clip's duration and aspect ratio (the API edit endpoint ignores those fields). — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)

### Inferences
- **Red route arrows or path lines over a model:** probably achievable as a *physical* object ("a thick glossy red painted line on the diorama ground tracing the route from A to B"), since Omni treats text and graphics best as in-scene objects. Precise geography (exact turns, labels) is not reliable. The robust approach is to overlay arrows and labels in post (ffmpeg/ASS, which this pipeline already uses for subtitles) on a clean plate prompted with "no on-screen text, no labels".
- Always add "no on-screen text, no captions, no logos" to scene prompts, because burned-in gibberish cannot be removed later.

### Gaps
- No source found that tested arrow or route-line legibility specifically.
- No quantitative failure-rate data (morphing, extra limbs) for Omni Flash 1.1.

## Q5. Audio prompting (SFX, "no dialogue")

### Takeaway
Both Veo 3.1 and Omni generate synced audio by default at no extra credit cost. Official syntax: quoted speech for dialogue, "SFX: …", "Ambient noise: …". For a narrated channel, state "no dialogue, no voice, no music" plus a soft ambient or SFX line, so the clip audio can sit under the voiceover. The project already normalizes clip SFX via `sfx_lufs`.

### Cited Findings
- Official: dialogue in quotation marks ("A woman says, 'We have to leave now.'"), "SFX: thunder cracks in the distance", "Ambient noise: the quiet hum of a starship bridge". — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Omni: describe audio such as "gentle breeze and distant birdsong" or "no dialogue". Audio is "part of the shot". Example: "Rubber gripping wet paint, breath, rain landing on the deck, one low bass note arriving as she plants, no voice." Audio is generated at no additional cost. — [OpenArt](https://openart.ai/blog/gemini-omni-flash-prompt-guide/); [Atlabs](https://www.atlabs.ai/blog/ultimate-gemini-omni-flash-prompting-guide-2026); [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)

### Inferences
- If you omit audio, the model invents it (possibly speech or music that clashes with the narration). Always include an explicit audio line.

### Gaps
- No source quantifies how reliably "no dialogue" suppresses random voices in Omni.

## Q6. Flow credits per clip, plans, limits, 9:16, and 360p vs 720p

### Takeaway
Official Flow Help (Oct 2026) confirms the user's figures: **Omni Flash 8s = 6 credits at 360p, 12 credits at 720p**. 1080p upscaling is free for Plus, Pro and Ultra subscribers; 4K costs 50 credits and is Ultra-only. Veo 3.1 is much pricier per clip (Fast 20, or 10 on Ultra; Quality 100). Native 9:16 is supported, so no crop is needed. 360p is a separately generated draft, not the 720p render scaled down, so it is good for composition but not for judging texture. Final 1080x1920 output from 360p is a 3x upscale and will look soft.

### Cited Findings
- **Official credit table** — [Google Flow Help, Manage your credits](https://support.google.com/flow/answer/16526234?hl=en):

| Model | 4s | 6s | 8s | 10s |
|---|---|---|---|---|
| Omni Flash 360p | 4 | 5 | **6** | 7 |
| Omni Flash 720p | 7 | 10 | **12** | 15 |
| Omni Flash video edit (any length/res) | 40 | | | |
| Veo 3.1 Lite | 10 (5 on Ultra); Lower Priority = 0 on Ultra only | | | |
| Veo 3.1 Fast | 20 (10 on Ultra) | | | |
| Veo 3.1 Quality (8s) | 100 | | | |
| Upscale 1080p | free (Plus/Pro/Ultra), not available to non-subscribers | | | |
| Upscale 4K | 50 (Ultra only) | | | |

- Plan allotments: everyone gets 50 credits/day. Monthly bonus: Plus 200; Pro 1,000; Ultra $100 tier 10,000; Ultra $200 tier 25,000. — [Flow Help](https://support.google.com/flow/answer/16526234?hl=en). Pro is about €19.99/mo. — [WaveSpeed, Omni Flash pricing (May 21, 2026)](https://wavespeed.ai/blog/de/posts/omni-flash-pricing/)
- **Conflicting or outdated figures:** at the May 2026 launch, Omni Flash cost 8s = 25 credits, 10s = 30, edit = 40. — [WaveSpeed (May 21, 2026)](https://wavespeed.ai/blog/de/posts/omni-flash-pricing/). That has been superseded by the current Flow Help table above. Novoads quotes "Veo 3.1: 72 credits", but those are Novoads' own platform credits, not Flow's. — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- Limits: non-subscribers may be blocked from video generation around 2–5 PM UTC at peak. Clip length is capped at 10s. Some multi-turn requests can create more than one generation (extra credit spend). — [Sagnik Bhattacharya](https://sagnikbhattacharya.com/blog/gemini-omni-google-flow); [WaveSpeed](https://wavespeed.ai/blog/de/posts/omni-flash-pricing/)
- Google (Aug 27, 2026): "Draft videos quickly and upscale for quality. Test out concepts and compositions at a faster, lower-credit 360p resolution before committing to a full-resolution render." 1080p and 4K export were added. — [Google blog, New creative controls in Flow](https://blog.google/innovation-and-ai/models-and-research/google-labs/new-creative-controls-google-flow/). Flow Help lists "Upscale Omni 360p videos" for Pro and Ultra. — [Flow Help, models](https://support.google.com/flow/answer/16352836?hl=en)
- 360p and 720p are each generated natively. "The version in 720p is generated à parte" (a separate generation, not a resize of the 360p clip). 360p is for composition, framing, rhythm and continuity, and "doesn't serve to judge fine texture detail". 1080p and 4K are upscales of the 720p render (the source reports 0.998+ correlation between them). — [Hora de Codar, 360p vs 720p in Omni 1.1 Flash](https://horadecodar.com.br/gemini-omni-1-1-flash-360p/); [Hora de Codar, upscale](https://horadecodar.com.br/upscale-gemini-omni-11-flash/) (based on the API; may differ from Flow UI behavior)
- Resolutions in the Omni API: 360p, 720p, 1080p, 4K. Durations in whole seconds, default 8. — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)

### Inferences
- The final render is 1080x1920. A 360p clip (640x360 landscape, or about 360x640 vertical) has to be scaled about 3x linearly, roughly 9x the pixels. 720p (720x1280) needs 1.5x, and Flow's free 1080p upscale gets it to native size. Expect a visible gain from 720p in edge sharpness, small miniature details (windows, figures, clay texture) and compression artifacts, especially in `full` and `clean` layouts where the clip fills the 9:16 frame. In the `band` layout the clip occupies only the middle band, so the gain is smaller.
- Cost math: 15 scenes for a 2-min short cost 90 credits at 360p and 180 at 720p, before retries. A Pro plan (1,000/mo + 50/day) covers about 5–9 such videos per month at 720p, or about twice that at 360p.
- Budget-aware option: draft at 360p, then for the approved shots either use Flow's "upscale 360p" (Pro/Ultra; whether this re-generates or super-resolves is unclear) or regenerate at 720p with the same prompt and first frame (it will not be an identical clip).

### Gaps
- Unclear whether Flow's "Upscale Omni 360p videos" re-renders at 720p (keeping composition) or only super-resolves the 360p frames, and what it costs (probably the 720p delta, but this is not documented). Hora de Codar's "separate generation" claim is API-based.
- Credit cost for Veo 3.1 Lite/Fast at shorter durations is not shown separately.

## Q7. Making 8s clips read as one continuous sequence

### Takeaway
Use the last frame of clip N as the first frame of clip N+1 (Frames to Video). Keep a word-for-word identical subject, style and lighting block across prompts. Prefer first+last-frame pairs derived from one base still. Give each clip one simple, continuous camera move whose direction carries into the next clip. Omni Extend is "coming soon"; until then, chaining frames is the main tool.

### Cited Findings
- Older Flow Extend used the last 24 frames to continue a shot seamlessly (Veo 2-era Scene Builder). For Veo 3 the recommended path was Scene Builder plus Frames-to-Video. — [eastondev (Dec 2025)](https://eastondev.com/blog/en/posts/dev/20251207-veo3-long-video-guide)
- Omni Extend is "Coming soon"; Veo 3.1 Lite has Extend at 8s only. — [Flow Help](https://support.google.com/flow/answer/16352836?hl=en)
- Start and end frames "keep the characters and narrative consistent as you … transition between frames". — [Google blog (Aug 27, 2026)](https://blog.google/innovation-and-ai/models-and-research/google-labs/new-creative-controls-google-flow/)
- Make both frames from the same base file with image-editing tools to match lighting, materials and positioning. — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Restate the still's exact setup in the video prompt to avoid mid-clip drift. — [Novoads](https://novoads.ai/blog/how-to-create-miniature-world-videos-with-ai)
- For edits: one sentence of change plus one sentence of preservation, e.g. "Keep the bag itself, key light, shadow direction and camera move exactly as they are." — [fal.ai](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)
- Specify "one continuous shot" rather than letting Omni add cuts. — [OpenArt](https://openart.ai/blog/gemini-omni-flash-prompt-guide/) (search summary)

### Inferences
- A practical recipe for an automated pipeline: (1) generate one master diorama still (Nano Banana), (2) per scene, either attach it as a Reference with a scene-specific prompt, or extract the last frame of the previous clip (ffmpeg `-sseof -0.1`) and upload it as the next first frame, (3) reuse a fixed lighting phrase ("soft diffused studio softbox light from top-left, warm 4500K") and palette in every prompt, (4) match motion direction across cuts (e.g. a continuous rightward truck).
- Chaining last frames compounds artifacts and resolution loss, worse at 360p. Re-anchoring to the master still every few clips limits drift.
- Since the narration already cuts every sentence, perfect continuity may be unnecessary. Consistent style across hard cuts usually reads as intentional editing.

### Gaps
- No source quantifies quality loss from repeated last-frame chaining in Omni.
- Couldn't find active 2026 Reddit threads (r/VeoAI, r/GoogleFlow) with tested Omni consistency tricks. Community evidence here comes mostly from vendor blogs.
