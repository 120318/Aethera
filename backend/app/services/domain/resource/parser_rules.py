from app.services.domain.resource.quality import (
    SOURCE_BLURAY,
    SOURCE_CAM,
    SOURCE_DVD,
    SOURCE_DVDRIP,
    SOURCE_HDCAM,
    SOURCE_HDTV,
    SOURCE_R5,
    SOURCE_REMUX,
    SOURCE_TC,
    SOURCE_TS,
    SOURCE_UHD_BLURAY,
    SOURCE_WEB_DL,
    SOURCE_WEBRIP,
)

GROUP_PATTERNS = [
    r"\[([^\[\]]+?)\]$",
    r"^\[([^\[\]]+?)\]",
    r"@([A-Za-z0-9_\-·]+)$",
    r"-([A-Za-z0-9_\-·]+)$",
]

SOURCE_PATTERNS = {
    SOURCE_UHD_BLURAY: r"\b(UHD|ULTRA[ ._-]*HD|4K).*(BLURAY|BLU[ ._-]?RAY|BD)\b",
    SOURCE_BLURAY: r"\b(BLURAY|BLU[ ._-]?RAY|BD|BDRIP|BD[ ._-]?RIP)\b",
    SOURCE_WEB_DL: r"\b(WEB[ ._-]?DL|WEBDL)\b",
    SOURCE_WEBRIP: r"\b(WEB[ ._-]?RIP|WEBRIP)\b",
    SOURCE_HDTV: r"\b(HDTV|HD[ ._-]?TV)\b",
    SOURCE_DVDRIP: r"\b(DVDRIP|DVD[ ._-]*RIP)\b",
    SOURCE_REMUX: r"\bREMUX\b",
    SOURCE_CAM: r"\b(CAM|CAMRIP|CAM[ ._-]?RIP)\b",
    SOURCE_TS: r"\b(TS|TELESYNC|TELE[ ._-]?SYNC)\b",
    SOURCE_TC: r"\b(TC|TELECINE|TELE[ ._-]?CINE)\b",
    SOURCE_R5: r"\bR5\b",
    SOURCE_HDCAM: r"\b(HDCAM|HD[ ._-]?CAM)\b",
}

ISO_IMAGE_PATTERN = r"(?i)(?:^|[ ._\-[\]()])(?:BDISO|DVDISO|ISO)(?:$|[ ._\-\[\]()]|$)|\.iso(?:$|[ ._\-\[\]()])"
BLURAY_DISC_PATTERN = (
    r"(?i)\b(?:BDMV|BDISO|CERTIFICATE|INDEX\.BDMV|MOVIEOBJECT\.BDMV|BDJO|BD25|BD50|BD66|BD100|"
    r"FULL[ ._-]*BLU[ ._-]*RAY|UNTOUCHED[ ._-]*BLU[ ._-]*RAY|DIY[ ._-]*BLU[ ._-]*RAY|"
    r"BLU[ ._-]*RAY[ ._-]*DISC|ULTRA[ ._-]*HD[ ._-]*BLU[ ._-]*RAY)\b"
)
UHD_BLURAY_DISC_PATTERN = r"(?i)\b(?:BD66|BD100|UHD|ULTRA[ ._-]*HD|4K|2160P)\b"
BLURAY_DISC_CODEC_PATTERN = r"(?i)\b(?:AVC|HEVC|MPEG[ ._-]*2|MPEG2)\b"
BLURAY_LOSSLESS_AUDIO_PATTERN = r"(?i)\b(?:DTS[ ._-]*HD(?:[ ._-]*MA)?|DTS[ ._-]*HDMA|TRUE[ ._-]*HD|LPCM|PCM)\b"
NON_DISC_RELEASE_PATTERN = (
    r"(?i)\b(?:REMUX|BDRIP|BD[ ._-]*RIP|X264|X265|H\.?264|H\.?265|WEB[ ._-]*DL|WEB[ ._-]*RIP|HDTV)\b"
    r"|\.(?:mkv|mp4|avi|mov|wmv|m4v|ts|m2ts|webm)(?:$|[ ._\-\[\]()])"
)
DVD_DISC_PATTERN = (
    r"(?i)\b(?:VIDEO_TS|AUDIO_TS|VIDEO_TS\.IFO|VTS_\d{2}_\d\.IFO|DVDISO|DVD5|DVD9|" r"FULL[ ._-]*DVD|UNTOUCHED[ ._-]*DVD)\b|\.VOB(?:$|[ ._\-\[\]()])"
)
DISC_PATTERNS = (
    r"(?i)\b(?:DISC|DISK)[ ._-]*(\d{1,2})[ ._-]*(?:OF|/)[ ._-]*(\d{1,2})\b",
    r"(?i)\b(?:DISC|DISK)[ ._-]*(\d{1,2})\b",
    r"(?i)\bS\d{1,2}D(\d{1,2})\b",
    r"(?i)(?:^|[ ._\-\[\]()])D(\d{1,2})(?:$|[ ._\-\[\]()])",
    r"(?:碟|盘)(\d{1,2})",
    r"(?:第)?(\d{1,2})(?:碟|盘)",
)

PLATFORM_PATTERNS = {
    "Netflix": r"\b(NF|NETFLIX)\b",
    "Amazon Prime Video": r"\b(AMAZON|AMZN)\b",
    "Disney+": r"\b(DISNEY|DSNP|DP)\b",
    "HBO Max": r"\b(HBO|HMAX)\b",
    "Hulu": r"\bHULU\b",
    "Apple TV+": r"\b(APPLE\s*TV\+?|ATVP)\b",
    "Paramount+": r"\b(PARAMOUNT\+?|PMTP)\b",
    "Peacock": r"\bPCOK\b",
    "YouTube": r"\b(YOUTUBE|YT)\b",
    "Crunchyroll": r"\b(CRUNCHYROLL|CR)\b",
    "iQIYI": r"(IQIYI|爱奇艺|奇艺)",
    "Tencent Video": r"(TENCENT|WETV|腾讯|腾讯视频|企鹅影视)",
    "Youku": r"(YOUKU|优酷|优酷视频)",
    "Mango TV": r"(MGTV|芒果TV|芒果|湖南卫视)",
    "Bilibili": r"(BILIBILI|哔哩哔哩|哔哩|B站)",
    "Sohu": r"(SOHU|搜狐|搜狐视频)",
    "LeTV": r"(LETV|乐视|乐视视频)",
    "PPTV": r"PPTV",
    "CCTV": r"(CCTV|央视|中央电视台)",
    "Migu": r"(MIGU|咪咕)",
    "BesTV": r"(BESTV|百视通|东方明珠)",
}

VERSION_PATTERNS = {
    "Director's Cut": r"\b(DIRECTOR.?S?.?CUT|DC)\b",
    "Extended": r"\b(EXTENDED|EXT)\b",
    "Uncut": r"\b(UNCUT|UC)\b",
    "Unrated": r"\b(UNRATED|UR)\b",
    "Remastered": r"\b(REMASTERED|REMASTER)\b",
    "Criterion": r"\bCRITERION\b",
    "Limited": r"\b(LIMITED|LTD)\b",
    "Theatrical": r"\b(THEATRICAL|TC)\b",
    "IMAX Edition": r"\bIMAX.?(EDITION|ED)\b",
    "IMAX": r"\bIMAX\b(?!.?(?:EDITION|ED)\b)",
    "Special Edition": r"\b(SPECIAL.?EDITION|SE)\b",
    "Ultimate Edition": r"\b(ULTIMATE.?EDITION|UE)\b",
    "Anniversary": r"\bANNIVERSARY\b",
    "Collector's Edition": r"\b(COLLECTOR.?S?.?EDITION|CE)\b",
    "Final Cut": r"\b(FINAL.?CUT|FC)\b",
    "Complete": r"\b(COMPLETE|COMP)\b",
    "Proper": r"\b(PROPER|REAL.?PROPER)\b",
    "Repack": r"\b(REPACK|RERIP)\b",
    "Internal": r"\b(INTERNAL|INT)\b",
}

SEASON_PATTERNS = [
    r"\bS(\d{1,2})\b",
    r"S(\d{1,2})(?=E)",
    r"S(\d{1,2})(?=D\d{1,2}\b)",
    r"\bSeason\s+(\d{1,2})\b",
    r"第(\d{1,2})季",
    r"Season(\d{1,2})\b",
]

EPISODE_PATTERNS = [
    r"(?:S\d{1,2})E(\d{1,3})E(\d{1,3})",
    r"(?:S\d{1,2})E(\d{1,3})-(?:E|EP)?(\d{1,3})",
    r"\b(?:E|EP)(\d{1,3})-(?:E|EP)?(\d{1,3})\b",
    r"(?:S\d{1,2})E(\d{1,3})",
    r"\bE(\d{1,3})\b",
    r"\bEP(\d{1,3})\b",
    r"\bEpisode\s+(\d{1,3})\b",
    r"第(\d{1,3})集",
    r"Episode(\d{1,3})\b",
]
