"""Project-owned language registry. Capability labels are conservative defaults."""

LANGUAGE_ROWS = [
    ("as", "Assamese", "অসমীয়া", "Beng"), ("bn", "Bengali", "বাংলা", "Beng"),
    ("brx", "Bodo", "बड़ो", "Deva"), ("doi", "Dogri", "डोगरी", "Deva"),
    ("en", "English", "English", "Latn"), ("gu", "Gujarati", "ગુજરાતી", "Gujr"),
    ("hi", "Hindi", "हिन्दी", "Deva"), ("kn", "Kannada", "ಕನ್ನಡ", "Knda"),
    ("ks", "Kashmiri", "कॉशुर", "Arab"), ("kok", "Konkani", "कोंकणी", "Deva"),
    ("mai", "Maithili", "मैथिली", "Deva"), ("ml", "Malayalam", "മലയാളം", "Mlym"),
    ("mni", "Manipuri", "মৈতৈলোন্", "Beng"), ("mr", "Marathi", "मराठी", "Deva"),
    ("ne", "Nepali", "नेपाली", "Deva"), ("or", "Odia", "ଓଡ଼ିଆ", "Orya"),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", "Guru"), ("sa", "Sanskrit", "संस्कृतम्", "Deva"),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Olck"), ("sd", "Sindhi", "سنڌي", "Arab"),
    ("ta", "Tamil", "தமிழ்", "Taml"), ("te", "Telugu", "తెలుగు", "Telu"),
    ("ur", "Urdu", "اردو", "Arab"), ("bho", "Bhojpuri", "भोजपुरी", "Deva"),
    ("raj", "Rajasthani", "राजस्थानी", "Deva"), ("tcy", "Tulu", "ತುಳು", "Knda"),
    ("kha", "Khasi", "Ka Ktien Khasi", "Latn"), ("lus", "Mizo", "Mizo", "Latn"),
    ("grt", "Garo", "A·chik", "Latn"), ("mwr", "Marwari", "मारवाड़ी", "Deva"),
    ("awa", "Awadhi", "अवधी", "Deva"), ("hne", "Chhattisgarhi", "छत्तीसगढ़ी", "Deva"),
    ("mag", "Magahi", "मगही", "Deva"), ("bgc", "Haryanvi", "हरियाणवी", "Deva"),
    ("har", "Haryanvi (alternate)", "हरियाणवी", "Deva"), ("kru", "Kurukh", "कुड़ुख", "Deva"),
    ("unr", "Mundari", "मुंडारी", "Deva"), ("hoc", "Ho", "हो", "Deva"),
    ("sck", "Sadri", "सादरी", "Deva"), ("gon", "Gondi", "गोंडी", "Deva"),
    ("mtr", "Mewari", "मेवाड़ी", "Deva"), ("kfy", "Kumaoni", "कुमाऊँनी", "Deva"),
]
LANGUAGES = [
    {"code": code, "name": name, "native_name": native, "script": script,
     "text_status": "supported", "speech_status": "unavailable", "translation_status": "unavailable"}
    for code, name, native, script in LANGUAGE_ROWS
]
LANGUAGE_BY_CODE = {row["code"]: row for row in LANGUAGES}
