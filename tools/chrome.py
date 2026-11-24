"""站点外壳的公共件：页面工具条 + 静态资源指纹。

三个生成器（build_section / research / build_pages）都往页面上挂同一条工具条，
所以它只能有一份实现 —— 否则改一次漏一处，下一版就出现两条长得不一样的栏。

约定：
  * 工具条的配色在 assets/css/pagebar.css 里（--pb-*），与皮肤无关；
  * 皮肤令牌在 assets/css/skin.css 里，排在页面自己的样式之后；
  * skinboot.js 必须在 <head> 里同步执行（先挂 data-skin，避免闪一下默认皮）；
  * pagebar.js 的 defer 版放页尾。
"""

from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def asset(name: str) -> str:
    """给静态资源带上内容指纹。

    GitHub Pages 按路径缓存，改了 CSS / JS 不加参数，回访的人会继续用旧的，
    看到的就是「DOM 更新了、样式没更新」的错位。
    """
    try:
        h = hashlib.md5((ROOT / "assets" / name).read_bytes()).hexdigest()[:8]
    except OSError:
        return "assets/" + name
    return "assets/%s?v=%s" % (name, h)


PB_ICON = {
    "theme": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4.4"/>'
             '<path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4'
             'M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/></svg>',
    "reload": '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.6-5.9"/>'
              '<path d="M20 4.5V10h-5.5"/></svg>',
    "setup": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/>'
             '<path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
             'a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1'
             'a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1'
             'a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
             'a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1'
             'a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1'
             'a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1'
             'a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1'
             'a1.6 1.6 0 0 0-1.5 1z"/></svg>',
}


def pbar_html(title: str, sum_html: str = "") -> str:
    """标题 · 摘要 —— 右侧 深浅 / 刷新 / 外观设置。

    标题用 <span> 不用 <h1>：板块页自己已经有 <h1>，这里再放一个就有两个主标题。
    """
    return ('<div class="pbar"><div class="pb-in">\n'
            '  <span class="pb-t">%s</span>\n'
            '  <div class="pb-sum">%s</div>\n'
            '  <div class="pb-sp"></div>\n'
            '  <button class="pb-i" data-pb="theme" type="button" title="切换深浅色" '
            'aria-label="切换深浅色">%s</button>\n'
            '  <button class="pb-i" data-pb="reload" type="button" title="刷新这一页" '
            'aria-label="刷新这一页">%s</button>\n'
            '  <button class="pb-i" data-pb="setup" type="button" title="外观设置" '
            'aria-label="外观设置" aria-haspopup="dialog" aria-expanded="false">%s</button>\n'
            '</div></div>'
            % (title, sum_html, PB_ICON["theme"], PB_ICON["reload"], PB_ICON["setup"]))


def head_assets(prefix: str = "") -> str:
    """<head> 里的三行：先挂皮肤，再叠皮肤令牌与工具条样式。

    顺序不能反：skinboot 要在首帧前跑完，skin.css 要排在页面自己的样式之后
    （属性选择器压变量），pagebar.css 最后。
    """
    return "\n".join([
        '<script src="%s%s"></script>' % (prefix, asset("js/skinboot.js")),
        '<link rel="stylesheet" href="%s%s">' % (prefix, asset("css/skin.css")),
        '<link rel="stylesheet" href="%s%s">' % (prefix, asset("css/pagebar.css")),
    ])


def foot_assets(prefix: str = "") -> str:
    return '<script src="%s%s" defer></script>' % (prefix, asset("js/pagebar.js"))
