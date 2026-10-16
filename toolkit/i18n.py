"""English / Arabic interface strings."""

LANGUAGES = {"en": "English", "ar": "العربية"}
NL = chr(10)
RLE, PDF = chr(0x202B), chr(0x202C)  # right-to-left embedding / pop directional formatting

_STRINGS = {
    "title": ("TikTok Quality Toolkit", "أداة جودة تيك توك"),
    "language": ("Language", "اللغة"),
    "subtitle": ("Make TikTok keep your video quality", "اجعل تيك توك يحافظ على جودة فيديوهاتك"),
    "nav_export": ("Export", "التصدير"),
    "nav_check": ("Check TikTok link", "فحص رابط تيك توك"),
    "export_title": ("Export settings", "إعدادات التصدير"),
    "orientation": ("Orientation", "الاتجاه"),
    "o_vertical": ("Vertical", "عمودي"),
    "o_horizontal": ("Horizontal", "أفقي"),
    "orient_auto": ("Matches your video", "مطابق للفيديو تلقائياً"),
    "orient_changed": ("Different from your video - it will be reframed", "مختلف عن الفيديو - سيُعاد تأطيره"),
    "res_title": ("Quality", "الجودة"),
    "content_type": ("Video type (for AI upscale)", "نوع الفيديو (لرفع الدقة)"),
    "ct_real": ("Real footage", "تصوير حقيقي"),
    "ct_anime": ("Anime / games", "أنمي وألعاب"),
    "ct_real_note": ("Most natural result · slow", "أفضل نتيجة طبيعية · بطيء"),
    "ct_anime_note": ("Sharp graphics · fast", "رسومات حادة · سريع"),
    "fps_title": ("Frame rate", "الإطارات"),
    "original": ("Original", "الأصلي"),
    "orig_of": ("Original · {v}", "الأصلي · {v}"),
    "crf_label": ("Encoding quality (CRF, lower = sharper)", "جودة الترميز (CRF، الأقل = أوضح)"),
    "colour_switch": ("Fix colours & HDR", "إصلاح الألوان و HDR"),
    "colour_desc": ("Accurate HDR to SDR and correct colour space", "تحويل HDR بدقة وألوان صحيحة"),
    "trick_switch": ("TikTok smoothness trick", "حيلة النعومة في تيك توك"),
    "trick_desc": ("Keeps 60 / 120 fps after you upload", "يحافظ على 60 / 120 إطاراً بعد الرفع"),
    "plan_title": ("What will happen", "ماذا سيحدث"),
    "plan_empty": ("Add a video to see what will happen", "أضف فيديو لترى ما سيحدث"),
    "pl_hdr": ("HDR video → natural colours (BT.2390 tone mapping)", "فيديو HDR ← ألوان طبيعية (تحويل BT.2390)"),
    "pl_colour": ("Colours corrected to standard BT.709", "تصحيح الألوان إلى المعيار BT.709"),
    "pl_size_ai": ("Quality {a} → {b} with AI upscale", "الجودة {a} ← {b} برفع الدقة بالذكاء الاصطناعي"),
    "pl_size_up": ("Quality {a} → {b} (standard resize)", "الجودة {a} ← {b} (تكبير عادي)"),
    "pl_size_down": ("Quality {a} → {b}", "الجودة {a} ← {b}"),
    "pl_size_same": ("Quality stays {a}", "الجودة تبقى {a}"),
    "pl_fps_ai": ("Frame rate {a} → {b} fps with AI frames (RIFE)", "الإطارات {a} ← {b} بإطارات الذكاء الاصطناعي (RIFE)"),
    "pl_fps_motion": ("Frame rate {a} → {b} fps with motion interpolation", "الإطارات {a} ← {b} باستيفاء الحركة"),
    "pl_fps_blend": ("Frame rate {a} → {b} fps (blended frames)", "الإطارات {a} ← {b} (دمج الإطارات)"),
    "pl_fps_down": ("Frame rate {a} → {b} fps", "الإطارات {a} ← {b}"),
    "pl_fps_same": ("Frame rate stays {a} fps", "الإطارات تبقى {a}"),
    "pl_reframe_blur": ("Reframed to {o} with a blurred background", "إعادة تأطير إلى {o} مع خلفية ضبابية"),
    "pl_reframe_crop": ("Reframed to {o} by cropping the sides", "إعادة تأطير إلى {o} بقص الأطراف"),
    "pl_size_super": ("Quality {a} → AI-rendered at {b}, delivered as 1080p (TikTok's maximum)",
                      "الجودة {a} ← تُرسم بالذكاء الاصطناعي بدقة {b} وتُسلَّم بدقة 1080p (أقصى دقة لتيك توك)"),
    "pl_size_cap": ("Delivered as 1080p - TikTok's maximum (higher gets downscaled by TikTok)",
                    "تُسلَّم بدقة 1080p - أقصى دقة لتيك توك (الأعلى منها يقلّلها تيك توك)"),
    "pl_blur": ("Motion blur {a} - AI frames at {i} fps blended to {b} fps",
                "ضبابية الحركة {a} - إطارات ذكاء اصطناعي بمعدل {i} تُدمج إلى {b}"),
    "pl_sharpen": ("Sharpened for TikTok (CAS) so edges survive compression",
                   "توضيح الحواف لتيك توك (CAS) كي تبقى واضحة بعد الضغط"),
    "pl_grade": ("Colour grade: saturation / contrast / brightness adjusted",
                 "تعديل الألوان: التشبّع / التباين / السطوع"),
    "pl_grade_vals": ("Colour grade: saturation {s} · contrast {c} · brightness {b}",
                      "تعديل الألوان: التشبّع {s} · التباين {c} · السطوع {b}"),
    "pl_enhance": ("Enhance filter ({e}): denoise + sharpen + colour boost",
                   "فلتر التحسين ({e}): إزالة تشويش + توضيح + تقوية ألوان"),
    "pl_warn_grade": ("Strong colour grade - values above 1.1 often look blown out on TikTok (Advanced settings)",
                      "تعديل ألوان قوي - القيم فوق 1.1 تطلع محروقة غالباً في تيك توك (الإعدادات المتقدمة)"),
    "pl_warn_blur_hfr": ("Motion blur at {b} fps softens edges - it's meant for 60 fps or less",
                         "ضبابية الحركة على {b} إطار تنعّم الحواف - مصممة لـ 60 أو أقل"),
    "pl_warn_small": ("Your horizontal video will fill only about 1/3 of the phone - try Crop, or keep Horizontal",
                      "الفيديو الأفقي سيملأ ثلث الشاشة فقط - جرّب القص أو أبقِه أفقياً"),
    "pl_warn_fps": ("{a} → {b} fps is mostly AI frames - 60 usually looks sharper on TikTok",
                    "{a} ← {b} يعني إطارات مصنوعة غالباً - 60 أوضح عادة في تيك توك"),
    "sharpen_switch": ("Sharpen for TikTok", "توضيح لتيك توك"),
    "sharpen_desc": ("Crisper edges after TikTok's compression", "حواف أوضح بعد ضغط تيك توك"),
    "motion_blur": ("Motion blur (like blur)", "ضبابية الحركة (مثل blur)"),
    "blur_amount": ("Blur amount", "مقدار الضبابية"),
    "blur_interp": ("Interpolated fps", "الإطارات الوسيطة"),
    "blur_weighting": ("Blur weighting", "طريقة الدمج"),
    "grade": ("Saturation / contrast / brightness", "التشبّع / التباين / السطوع"),
    "import_cfg": ("Import blur .cfg", "استيراد ملف blur ‎.cfg"),
    "cfg_imported": ("Settings imported from {name}", "تم استيراد الإعدادات من {name}"),
    "cfg_failed": ("Could not read this config file:\n{msg}", "تعذّرت قراءة ملف الإعدادات:\n{msg}"),
    "pl_trick": ("TikTok trick keeps {b} fps after upload", "حيلة تيك توك تحافظ على {b} إطاراً بعد الرفع"),
    "pl_trick_na": ("TikTok trick not needed at 30 fps", "حيلة تيك توك غير لازمة عند 30 إطاراً"),
    "pl_ghost": ("Ghost frames (1080p60 trick)", "الإطارات الوهمية (حيلة 1080p60)"),
    "upload_hint": ("TikTok Studio is open - drag the selected file from the folder into its upload box",
                    "فُتح تيك توك ستوديو - اسحب الملف المحدد من المجلد إلى خانة الرفع"),
    "upload_no_file": ("Export a video first, then upload it.", "صدّر المقطع أولاً ثم ارفعه."),
    "reset_recommended": ("Reset to recommended", "رجوع للإعدادات المقترحة"),
    "pl_normalize": ("First: your video is converted to 1080p · H.264 High · 50,000 kbps CBR · MP4",
                     "أولاً: يتحول مقطعك إلى 1080p · H.264 High · 50,000 kbps ثابت · MP4"),
    "pl_spec": ("Export: MP4 · H.264 High · 1080p · 50,000 kbps CBR",
                "التصدير: MP4 · H.264 High · 1080p · 50,000 kbps ثابت (CBR)"),
    "pl_encode": ("Re-encoded in high quality (H.264)", "إعادة ترميز بجودة عالية (H.264)"),
    "pl_time": ("Estimated time: about {m} min on your graphics card",
                "الوقت المتوقع: حوالي {m} دقيقة على كرت الشاشة"),
    "pl_time_short": ("Estimated time: under a minute", "الوقت المتوقع: أقل من دقيقة"),
    "export_failed": ("Export failed", "فشل التصدير"),
    "pl_instant": ("Instant - no re-encoding, no quality loss", "فوري - بدون إعادة ترميز وبدون فقد جودة"),
    "export_btn": ("Export", "تصدير"),
    "preview_short": ("Preview", "معاينة"),
    "advanced": ("Advanced settings", "إعدادات متقدمة"),
    "add_videos": ("Add videos", "إضافة فيديو"),
    "drop_here": ("Drop a video here\nor click to choose", "أفلت الفيديو هنا\nأو اضغط للاختيار"),
    "analyzing": ("Reading video…", "جارٍ قراءة الفيديو…"),
    "show_details": ("Show details", "عرض التفاصيل"),
    "hide_details": ("Hide details", "إخفاء التفاصيل"),
    "status_ready": ("Ready", "جاهز"),
    "status_working": ("Exporting {n} of {total}…", "جارٍ التصدير {n} من {total}…"),
    "status_done": ("Done - saved next to the original", "تم - حُفظ بجانب الملف الأصلي"),
    "status_done_dir": ("Done - saved to {path}", "تم - حُفظ في {path}"),
    "status_failed": ("Finished with errors - see details", "انتهى مع أخطاء - راجع التفاصيل"),
    "of": ("{i} of {n}", "{i} من {n}"),
    "all_videos": ("Settings apply to all {n} videos", "الإعدادات تُطبّق على كل الفيديوهات ({n})"),
    "fill": ("When reframing", "عند إعادة التأطير"),
    "fl_blur": ("Blurred background", "خلفية ضبابية"),
    "fl_crop": ("Crop to fill", "قص لملء الشاشة"),
    "trick_mode": ("TikTok trick mode", "نوع حيلة تيك توك"),
    "close": ("Done", "تم"),
    "open_output": ("Open folder", "فتح المجلد"),
    "col_stream": ("Stream", "النسخة"),
    "col_res": ("Resolution", "الدقة"),
    "col_codec": ("Codec", "الترميز"),
    "col_rate": ("Bitrate", "معدل البت"),
    "col_size": ("Size", "الحجم"),
    "videos_title": ("Videos", "الفيديوهات"),
    "videos_hint": ("Drag & drop videos here, or click Add files", "اسحب الفيديوهات وأفلتها هنا، أو اضغط إضافة ملفات"),
    "steps_title": ("Steps", "الخطوات"),
    "st1": ("Prepare", "التجهيز"),
    "st2": ("FPS patch", "تعديل الإطارات"),
    "st3": ("Ghost frames", "الإطارات الوهمية"),
    "s1_desc": ("Re-encodes the video: colour fix, AI upscale, extra frames, 9:16, trim.",
                "يعيد ترميز الفيديو: إصلاح الألوان، رفع الدقة، إطارات إضافية، 9:16، القص."),
    "s2_desc": ("Instant. Rewrites the timing so TikTok keeps all frames (60/120 fps).",
                "فوري. يعدّل توقيت الفيديو كي يحتفظ تيك توك بكل الإطارات (60/120)."),
    "s3_desc": ("Instant. Declares extra frames so TikTok serves 1080p60. H.264 only.",
                "فوري. يصرّح بإطارات إضافية ليعرض تيك توك 1080p60. يعمل مع H.264 فقط."),
    "enable_step": ("Enable this step", "تفعيل هذه الخطوة"),
    "sec_frames": ("FRAMES & SIZE", "الإطارات والدقة"),
    "sec_picture": ("PICTURE", "الصورة"),
    "sec_encoding": ("ENCODING", "الترميز"),
    "sec_trim": ("TRIM", "القص"),
    "will_run": ("Will run: {steps}", "سيتم تنفيذ: {steps}"),
    "nothing": ("No step selected - enable at least one step", "لم تُحدد أي خطوة - فعّل خطوة واحدة على الأقل"),
    "log_title": ("Log", "السجل"),
    "output_title": ("Save to", "مكان الحفظ"),
    "output_hint": ("Empty = next to the original video", "فارغ = بجانب الفيديو الأصلي"),
    "tab_process": ("Process videos", "معالجة الفيديو"),
    "tab_check": ("Check TikTok link", "فحص رابط تيك توك"),
    "videos": ("Videos - drag & drop files here", "الفيديوهات - اسحب الملفات وأفلتها هنا"),
    "add": ("Add files…", "إضافة ملفات…"),
    "remove": ("Remove", "حذف"),
    "clear": ("Clear", "مسح الكل"),
    "inspect": ("Inspect", "فحص"),
    "preset": ("Preset", "الإعداد المسبق"),
    "custom": ("Custom", "مخصص"),
    "help": ("Help", "مساعدة"),
    "p_method": ("60/120 FPS method (recommended)", "طريقة 60/120 إطاراً (مُوصى بها)"),
    "p_ghost": ("1080p60 ghost frames", "إطارات وهمية 1080p60"),
    "p_interp": ("30 fps clip -> AI interpolate to 60 + method", "مقطع 30 إطاراً ← رفع بالذكاء الاصطناعي إلى 60 + الطريقة"),
    "p_gaming": ("Landscape gameplay -> 9:16 + enhance + method", "لعب أفقي ← 9:16 + تحسين + الطريقة"),
    "p_clean": ("Clean re-encode 60 fps + method", "إعادة ترميز نظيفة 60 إطاراً + الطريقة"),
    "p_all": ("Everything (experimental)", "كل الخطوات (تجريبي)"),
    "step1": ("Step 1 - Prepare with FFmpeg (re-encode)", "الخطوة ١ - التجهيز عبر FFmpeg (إعادة ترميز)"),
    "step2": ("Step 2 - FPS patch (instant, no re-encode)", "الخطوة ٢ - تعديل معدل الإطارات (فوري، بدون إعادة ترميز)"),
    "step3": ("Step 3 - Ghost frames, 1080p60 trick (H.264 only)", "الخطوة ٣ - الإطارات الوهمية، حيلة 1080p60 (H.264 فقط)"),
    "enable": ("Enable", "تفعيل"),
    "fps": ("FPS", "الإطارات"),
    "short_side": ("Short side", "الضلع القصير"),
    "quality": ("Quality (lower = better)", "الجودة (الأقل = أفضل)"),
    "frames": ("New frames", "الإطارات الجديدة"),
    "encoder": ("Encoder", "المُرمِّز"),
    "enhance": ("Enhance", "تحسين الصورة"),
    "fit": ("9:16 vertical", "عمودي 9:16"),
    "color": ("Colour fix", "إصلاح الألوان"),
    "c_auto": ("Auto: HDR to SDR + fix (recommended)", "تلقائي - تحويل HDR وإصلاح الألوان (مُوصى به)"),
    "c_off": ("Off", "إيقاف"),
    "upscale": ("AI upscale", "رفع الدقة بالذكاء الاصطناعي"),
    "u_off": ("Off", "إيقاف"),
    "u_real": ("Real footage (best quality, slow)", "تصوير حقيقي (أفضل جودة، بطيء)"),
    "u_anime": ("Anime / games (fast)", "أنمي وألعاب (سريع)"),
    "esrgan_missing": ("Real-ESRGAN not found - the AI upscale option needs the full (installer) version.",
                       "Real-ESRGAN غير موجود - خيار رفع الدقة يحتاج النسخة الكاملة (المثبّت)."),
    "p_hdr": ("HDR phone video -> correct colours + method", "فيديو جوال HDR ← ألوان صحيحة + الطريقة"),
    "p_upscale": ("Low-res clip -> AI upscale to 1080p + method", "مقطع بدقة منخفضة ← رفع الدقة إلى 1080p + الطريقة"),
    "trim": ("Trim", "قص"),
    "trim_from": ("from", "من"),
    "trim_to": ("to", "إلى"),
    "trim_hint": ("(seconds or mm:ss, empty = whole video)", "(ثوانٍ أو دقيقة:ثانية، فارغ = الفيديو كامل)"),
    "preview": ("Preview before/after", "معاينة قبل/بعد"),
    "i_none": ("Duplicate/drop (fast)", "تكرار/حذف (سريع)"),
    "i_blend": ("Blend (fast, soft)", "دمج (سريع، ناعم)"),
    "i_motion": ("Motion interpolation (slow, smooth)", "استيفاء الحركة (بطيء، ناعم)"),
    "i_ai": ("AI - RIFE (best, uses GPU)", "ذكاء اصطناعي RIFE (الأفضل، يستخدم كرت الشاشة)"),
    "e_auto": ("Auto (GPU if available)", "تلقائي (كرت الشاشة إن وُجد)"),
    "e_cpu": ("CPU - x264 (best quality)", "المعالج x264 (أفضل جودة)"),
    "e_nvidia": ("NVIDIA GPU (fast)", "كرت NVIDIA (سريع)"),
    "e_amd": ("AMD GPU (fast)", "كرت AMD (سريع)"),
    "e_intel": ("Intel GPU (fast)", "كرت Intel (سريع)"),
    "en_off": ("Off", "إيقاف"),
    "en_light": ("Light", "خفيف"),
    "en_strong": ("Strong", "قوي"),
    "f_none": ("Keep shape", "إبقاء الشكل"),
    "f_blur": ("Blurred background", "خلفية ضبابية"),
    "f_crop": ("Crop to fill", "قص لملء الشاشة"),
    "m_method": ("120 FPS method - plays normally (recommended)", "طريقة 120 إطاراً - سرعة طبيعية (مُوصى بها)"),
    "m_slowmo": ("Slow-motion - speed up 2x inside TikTok", "حركة بطيئة - تسرّعه ×2 داخل تيك توك"),
    "source_fps": ("Source FPS", "إطارات المصدر"),
    "declare_as": ("Declare as", "التصريح كـ"),
    "patch_audio": ("Patch audio too", "تعديل الصوت أيضاً"),
    "auto": ("auto", "تلقائي"),
    "multiplier": ("Frame multiplier", "مضاعف الإطارات"),
    "tag": ("Tag", "الوسم"),
    "output": ("Output folder (empty = next to the original)", "مجلد الحفظ (فارغ = بجانب الأصلي)"),
    "browse": ("Browse…", "استعراض…"),
    "same": ("Same as source", "نفس مجلد المصدر"),
    "start": ("Start", "ابدأ"),
    "cancel": ("Cancel", "إلغاء"),
    "paste": ("Paste a TikTok video link:", "الصق رابط فيديو تيك توك:"),
    "check": ("Check", "افحص"),
    "download": ("Download best stream + inspect", "تنزيل أفضل نسخة + فحصها"),
    "open_folder": ("Open folder", "فتح المجلد"),
    "check_intro": (
        "After uploading, paste the link here to see which frame rates and resolutions TikTok really serves.",
        "بعد الرفع، الصق الرابط هنا لترى معدل الإطارات والدقة التي يعرضها تيك توك فعلاً."),
    "checking": ("Checking…", "جارٍ الفحص…"),
    "streams": ("Streams TikTok serves:", "النسخ التي يعرضها تيك توك:"),
    "best_fps": ("Best frame rate: {fps} fps", "أعلى معدل إطارات: {fps}"),
    "v_smooth": ("SMOOTH - TikTok kept the high frame rate. The trick worked!",
                 "ناعم - تيك توك حافظ على معدل الإطارات العالي. الحيلة نجحت!"),
    "v_normal": ("NORMAL - TikTok serves 30 fps only. Try another preset.",
                 "عادي - تيك توك يعرض 30 إطاراً فقط. جرّب إعداداً آخر."),
    "v_unknown": ("Frame rate not listed by TikTok - use Download + inspect.",
                  "تيك توك لم يذكر معدل الإطارات - استخدم التنزيل + الفحص."),
    "via": ("Source: {src}", "المصدر: {src}"),
    "downloading": ("Downloading {name}…", "جارٍ تنزيل {name}…"),
    "saved_to": ("Saved to {path}", "تم الحفظ في {path}"),
    "need_video": ("Add a video first.", "أضف فيديو أولاً."),
    "need_one": ("Add at least one video.", "أضف فيديو واحداً على الأقل."),
    "need_step": ("Enable at least one step.", "فعّل خطوة واحدة على الأقل."),
    "no_outdir": ("Output folder does not exist.", "مجلد الحفظ غير موجود."),
    "need_ffmpeg": ("This needs FFmpeg (winget install Gyan.FFmpeg).", "هذا يحتاج برنامج FFmpeg (winget install Gyan.FFmpeg)."),
    "need_prepare": ("Preview shows Step 1 - enable it first.", "المعاينة تعرض الخطوة ١ - فعّلها أولاً."),
    "ffmpeg_missing": ("FFmpeg not found - Step 1 and Preview need it.", "لم يتم العثور على FFmpeg - الخطوة ١ والمعاينة تحتاجانه."),
    "rife_missing": ("RIFE AI not found - the AI option needs the full (installer) version.",
                     "RIFE غير موجود - خيار الذكاء الاصطناعي يحتاج النسخة الكاملة (المثبّت)."),
    "invalid": ("Invalid value for {name}.", "قيمة غير صالحة في {name}."),
    "running_quit": ("A job is running. Cancel it and quit?", "توجد عملية قيد التنفيذ. إلغاؤها والخروج؟"),
    "quit": ("Quit", "خروج"),
    "done": ("Done", "تم"),
    "done_msg": ("{ok} of {total} video(s) processed.\nSee the log for details.",
                 "تمت معالجة {ok} من {total} فيديو.\nراجع السجل للتفاصيل."),
    "finished": ("Finished: {ok}/{total} succeeded.", "انتهى: نجح {ok} من {total}."),
    "saved": ("-> saved {path}", "← تم الحفظ {path}"),
    "error": ("ERROR: {msg}", "خطأ: {msg}"),
    "cannot_inspect": ("{name}: cannot inspect - {msg}", "{name}: تعذّر الفحص - {msg}"),
    "rendering_preview": ("Rendering a {s}-second preview…", "جارٍ إنشاء معاينة مدتها {s} ثوانٍ…"),
    "preview_ready": ("Preview ready (left = before, right = after): {path}",
                      "المعاينة جاهزة (اليسار = قبل، اليمين = بعد): {path}"),
    "help_text": (
        """How to use
1. Add videos (Add files, or drag them onto this window or the .exe).
2. Pick a preset, or tick the steps you want.
3. Press Start. Output files are saved as <name>_tiktok.mp4.

Steps
- Prepare (FFmpeg): H.264, constant frame rate, 1080p. Can turn 30 fps into
  60/120 fps (AI RIFE is the best), fix HDR / wrong colours, upscale
  low-resolution clips with AI (Real-ESRGAN), enhance the picture, make
  landscape videos 9:16, trim, and use your graphics card to encode faster.
- FPS patch: rewrites the MP4 timing headers so TikTok keeps all frames.
- Ghost frames: declares extra frames so TikTok serves 1080p60.

Uploading
- Upload from a PC (tiktok.com/upload), not from the phone app.
- Patched files may look wrong on PC players / TikTok web but play
  smoothly in the phone app. Do not edit the clip inside TikTok.
- Then use the "Check TikTok link" tab to see what TikTok really serves.

TikTok can change its processing at any time - use at your own risk.""",
        """طريقة الاستخدام
١. أضف الفيديوهات (زر إضافة ملفات، أو اسحبها إلى هذه النافذة أو إلى ملف exe).
٢. اختر إعداداً مسبقاً أو فعّل الخطوات التي تريدها.
٣. اضغط ابدأ. تُحفظ الملفات باسم name_tiktok.mp4.

الخطوات
- التجهيز (FFmpeg): ترميز H.264 بمعدل إطارات ثابت ودقة 1080p. يمكنه رفع
  30 إطاراً إلى 60/120 (الذكاء الاصطناعي RIFE هو الأفضل)، وإصلاح ألوان HDR،
  ورفع دقة المقاطع الضعيفة بالذكاء الاصطناعي (Real-ESRGAN)، وتحسين الصورة،
  وتحويل الفيديو الأفقي إلى 9:16، والقص، واستخدام كرت الشاشة للتسريع.
- تعديل معدل الإطارات: يعيد كتابة ترويسات التوقيت كي يحتفظ تيك توك بكل الإطارات.
- الإطارات الوهمية: يصرّح بإطارات إضافية ليعرض تيك توك 1080p60.

الرفع
- ارفع من الكمبيوتر (tiktok.com/upload) وليس من تطبيق الجوال.
- قد يظهر الملف بشكل غريب على الكمبيوتر لكنه يعمل بنعومة في تطبيق الجوال.
  لا تعدّل المقطع داخل تيك توك.
- بعد النشر استخدم تبويب "فحص رابط تيك توك" لترى ما يعرضه تيك توك فعلاً.

تيك توك قد يغيّر طريقة المعالجة في أي وقت - الاستخدام على مسؤوليتك."""),
}


class Translator:
    def __init__(self, lang="en"):
        self.lang = lang if lang in LANGUAGES else "en"

    @property
    def rtl(self):
        return self.lang == "ar"

    def __call__(self, key, **kw):
        en, ar = _STRINGS[key]
        text = ar if self.lang == "ar" else en
        text = text.format(**kw) if kw else text
        if self.lang == "ar":
            # right-to-left embedding per line keeps mixed Arabic/Latin text in order
            text = NL.join(RLE + line + PDF if line else line for line in text.split(NL))
        return text
