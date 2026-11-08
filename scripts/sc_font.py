"""Find a licensed, local Simplified Chinese font without network access."""
import os
from pathlib import Path
from PIL import ImageFont

ENV_NAME='SWIM_BUDDY_SC_FONT'
STANDARD=[
    str(Path(__file__).resolve().parents[1]/'assets/fonts/NotoSansCJKsc-Regular.otf'),
    'C:/Windows/Fonts/NotoSansSC-VF.ttf',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf',
    '/System/Library/Fonts/PingFang.ttc',
]

def _sc(path,index):
    try:
        face=ImageFont.truetype(str(path),20,index=index).getname()[0]
        return 'SC' in face or 'Simplified Chinese' in face
    except (OSError,ValueError):return False

def find_sc_font(explicit=None,preferred_index=0):
    candidates=[explicit] if explicit else [os.environ.get(ENV_NAME)]+STANDARD
    for name in candidates:
        if not name:continue
        path=Path(name)
        if not path.is_file():continue
        for index in [preferred_index]+[i for i in range(16) if i!=preferred_index]:
            if _sc(path,index):return str(path),index
    raise ValueError('未找到简体中文SC字体：请用--font或SWIM_BUDDY_SC_FONT提供合法本地字体，字体集需含SC face')
