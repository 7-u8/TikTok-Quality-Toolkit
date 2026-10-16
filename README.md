# TikTok Quality Toolkit: free 60 / 120 FPS and sharp 1080p uploads for TikTok

**أداة جودة تيك توك: ارفع مقاطعك على تيك توك بـ 60 و 120 إطار وجودة 1080p واضحة، مجاناً ومفتوحة المصدر**

A free, open-source Windows app (English and Arabic) that prepares your videos so TikTok keeps their **smoothness (60/120 fps)**, **sharpness** and **colours**. Some people sell this "60fps / 120fps TikTok method" for money. Here it is free, with the full source code, so anyone can use it and learn how it works.

> Unofficial project. Not affiliated with, endorsed by or connected to TikTok or ByteDance.

[English](#english) · [العربية](#العربية)

---

## English

### Download

Get **`TikTok Quality Toolkit Setup.exe`** from the [**Releases**](../../releases/latest) page and run it. It installs per user with no admin rights needed. FFmpeg, RIFE AI and Real-ESRGAN AI are included. A portable folder is also attached if you'd rather not install.

Requirements: Windows 10/11 64-bit. The AI features (RIFE frames, Real-ESRGAN upscale) need a Vulkan-capable GPU (NVIDIA, AMD or Intel).

### How to use

1. Drop a video on the phone preview, or click it to choose one.
2. Pick the **Orientation** (detected from the video automatically), the **Quality** (Original · 1080p · 2K · 4K) and the **Frame rate** (Original · 30 · 60 · 120).
3. Pick the **Video type**: *Real footage* for realistic games and camera video, or *Anime & games* for cartoon/stylised content (faster).
4. Read **What will happen**, which lists every step before you export.
5. Press **Export**, then **UPLOAD TO TIKTOK**. That opens TikTok Studio in your browser and the folder with your file selected, so you can drag it into the upload box.

**Recommended settings:** Quality 2K, Frame rate *Original* if your recording is already 60/120 fps (or 60 otherwise), smoothness trick on, sharpen on, and colours left at 1.0. *Advanced settings → Reset to recommended* restores all of this in one click.

### What it does

| Feature | Details |
|---|---|
| **Upload spec, always applied** | Your video is first converted to **1080p · H.264 High · 50,000 kbps CBR · MP4**, every enhancement runs on that, and the export is encoded to the same spec again. |
| **Smoothness trick (60/120 fps)** | Rewrites the MP4 `mvhd`/`mdhd` timing headers (the community "120 FPS method") so TikTok's transcoder keeps the high frame rate. Only header fields change; the video data is untouched. |
| **2K / 4K supersampling** | TikTok downscales anything above 1080p, so 2K/4K are rendered by Real-ESRGAN AI at that size and delivered as a sharper 1080p. |
| **AI frames** | RIFE (GPU) creates in-between frames for 60 → 120 fps and similar. |
| **Colour & HDR fix** | Detects HDR (HDR10/PQ, HLG from iPhone and Android) and converts it to SDR with the ITU-R BT.2390 tone curve. It also fixes full-range and BT.601 video, so colours don't look washed out. |
| **Sharpen for TikTok** | CAS sharpening after the final scaling, so edges survive TikTok's compression. |
| **Motion blur** | Frame blending in the style of [f0e/blur](https://github.com/f0e/blur), including `.cfg` import. |
| **Check TikTok link** | Reads what TikTok actually serves for a posted video (fps, resolution, bitrate per quality level) and tells you whether the trick worked. |
| **Inspect** | Codec, real fps, CFR/VFR, bitrate, and a readiness checklist. |

### Good to know

- **Get the best source you can.** If an editor such as CapCut exported your clip at 60 fps, the real 120 frames are gone and the AI has to invent them. Export at 120 fps with a high bitrate, or load the raw recording directly.
- **Keep saturation near 1.0.** Boosting it on a scene that is already tinted, such as a green-lit map, turns it neon. The app limits colour values to 0.7–1.3.
- TikTok decides the final processing and can change it at any time. Use the *Check TikTok link* tab to verify your post. **Use at your own risk.**

### Command line

```
python tiktok_toolkit.py inspect video.mp4
python tiktok_toolkit.py run clip.mp4                                  # smoothness trick only
python tiktok_toolkit.py run clip.mp4 --prepare --interpolation ai --prep-fps 120
python tiktok_toolkit.py run lowres.mp4 --prepare --upscale real
python tiktok_toolkit.py check https://www.tiktok.com/@user/video/123 --download
```

### Build from source

1. Install Python 3.12, then run `pip install pyinstaller pillow`.
2. Put the tools next to the project. They're not in git because of their size:
   - `ffmpeg/`: `ffmpeg.exe`, `ffprobe.exe` from the [GyanD FFmpeg essentials build](https://www.gyan.dev/ffmpeg/builds/)
   - `rife/`: [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan/releases) with the `rife-v4` and `rife-v4.6` models
   - `esrgan/`: [realesrgan-ncnn-vulkan v0.2.5.0](https://github.com/xinntao/Real-ESRGAN/releases) with the `realesrgan-x4plus` and `realesr-animevideov3` models
3. Run from source with `python tiktok_toolkit.py`.
4. Run the tests with `python -m unittest discover -s tests -v`. Set `TT_NETWORK_TESTS=1` to include the live TikTok check.
5. Build the installer with `python build_tools/build.py "<output folder>"`, which writes the portable folder and `Setup.exe`.

### Contributing

Issues and pull requests are welcome, whether that's bug reports, TikTok changes that break the trick, or translations.

---

## العربية

### التحميل

حمّل **`TikTok Quality Toolkit Setup.exe`** من صفحة [**Releases**](../../releases/latest) وشغّله. يثبّت بدون صلاحيات مدير، ويجي معه FFmpeg و RIFE و Real-ESRGAN. وفيه بعد نسخة محمولة (portable) بدون تثبيت.

المتطلبات: ويندوز 10 أو 11 (64 بت). مزايا الذكاء الاصطناعي تحتاج كرت شاشة يدعم Vulkan (NVIDIA أو AMD أو Intel).

### طريقة الاستخدام

1. اسحب المقطع على شكل الجوال، أو اضغط عليه واختر المقطع.
2. اختر **الاتجاه** (يتحدد تلقائياً) و**الجودة** (الأصلي · 1080p · 2K · 4K) و**الإطارات** (الأصلي · 30 · 60 · 120).
3. اختر **نوع الفيديو**: *تصوير حقيقي* للألعاب الواقعية والكاميرا، أو *أنمي وألعاب* للرسوم الكرتونية (أسرع).
4. اقرأ قائمة **ماذا سيحدث**، فيها كل خطوة قبل التصدير.
5. اضغط **تصدير**، وبعدها **UPLOAD TO TIKTOK**. يفتح لك تيك توك ستوديو في متصفحك، ويفتح المجلد والمقطع محدد فيه، وتسحبه إلى خانة الرفع.

**الإعدادات المقترحة:**
- الجودة: 2K
- الإطارات: *الأصلي* إذا تسجيلك 60 أو 120 أصلاً، وإلا 60
- حيلة النعومة: شغالة
- التوضيح: شغال
- الألوان: 1.0

وزر *الإعدادات المتقدمة ← رجوع للإعدادات المقترحة* يرجّع كل هذا بضغطة وحدة.

### المزايا

- **مواصفات الرفع دايماً:** يتحول المقطع أولاً إلى **1080p · H.264 High · 50,000 kbps ثابت · MP4**، وبعدها تنطبق عليه كل التحسينات، ويتصدّر بنفس المواصفات.
- **حيلة النعومة (60 و 120 إطار):** تعديل معلومات التوقيت في ملف MP4، فيحافظ تيك توك على الإطارات العالية. بيانات الفيديو نفسها ما تتغير.
- **2K و 4K:** تيك توك يصغّر أي شي فوق 1080، فالبرنامج يرسم المقطع بالذكاء الاصطناعي بدقة 2K أو 4K ويسلّمه 1080p أوضح.
- **إطارات بالذكاء الاصطناعي (RIFE):** يصنع إطارات وسطية، مثلاً من 60 إلى 120.
- **إصلاح الألوان و HDR:** يحوّل مقاطع HDR (الآيفون والأندرويد) لألوان صحيحة، عشان ما تطلع باهتة.
- **توضيح لتيك توك:** حواف أوضح بعد ضغط تيك توك.
- **فحص رابط تيك توك:** يبين لك وش الإطارات والجودة اللي يعرضها تيك توك فعلياً بعد النشر.

### نصائح مهمة

- **صدّر من محرر الفيديو على 120 إطار وبمعدل بت عالي**، أو حط التسجيل الخام مباشرة. إذا صدّرت من CapCut على 60، تضيع الإطارات الحقيقية.
- **خلّ التشبّع قريب من 1.0.** رفعه على ماب إضاءته ملونة يخرّب الألوان.
- تيك توك ممكن يغيّر طريقة المعالجة في أي وقت. **الاستخدام على مسؤوليتك.**

---

## Credits / الشكر

- FPS-patch technique: [ut0ku/120fps-method](https://github.com/ut0ku/120fps-method) (GPL-3.0) and [EditingNews EN-TikTok-60FPS](https://github.com/lamle25/EN-TikTok-60FPS) (MIT).
- Ghost frames ported from [BastienGimbert/tiktok-quality](https://github.com/BastienGimbert/tiktok-quality) (MIT).
- Link checker and inspector ideas from [HaiYTB/TikTok-Tweaks](https://github.com/HaiYTB/TikTok-Tweaks) (MIT).
- Motion-blur approach and `.cfg` format from [f0e/blur](https://github.com/f0e/blur) (GPL-3.0).
- [FFmpeg](https://ffmpeg.org) (GPL) build by [GyanD](https://github.com/GyanD/codexffmpeg). Source code is at ffmpeg.org; the licence ships in `ffmpeg/LICENSE.txt`.
- [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) by nihui (MIT), with RIFE models by hzwer.
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) ncnn-vulkan by Xintao Wang (BSD-3-Clause).

## License / الرخصة

[GPL-3.0](LICENSE). You're free to use, study, change and share this project. If you share a modified version, it has to stay open source under the same licence, so nobody can take it closed and sell it.

حر للاستخدام والتعديل والمشاركة، وأي نسخة معدّلة تنتشر لازم تبقى مفتوحة المصدر بنفس الرخصة. يعني ما أحد يقدر يقفلها ويبيعها.
